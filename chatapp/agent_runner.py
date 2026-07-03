from __future__ import annotations

import copy
import threading
from typing import List, Optional

from app.client import ApiClient
from src.agent.multiturn_agent import MultiTurnAgent
from src.tools.helper import Config
from src.physicalop import auto_parse_op
from src.module.executor import Executor

from chatapp.operator_tree import OperatorTree
from chatapp.state import InMemoryStore, TrialEventHub


def _split_chain(chain: str) -> List[str]:
    return [x.strip() for x in chain.split("-->") if x.strip()]


class InteractiveMultiTurnRunner:
    """Runs MultiTurnAgent turn-by-turn and publishes events for UI."""

    def __init__(
        self,
        *,
        cfg: dict,
        store: InMemoryStore,
        hub: TrialEventHub,
        trial_id: str,
    ):
        self.cfg = cfg
        self.store = store
        self.hub = hub
        self.trial_id = trial_id
        self.tree = OperatorTree()

        # MultiTurnAgent internally creates ApiClient(), which will use DS_AGENT_API_BASE_URL
        self.agent = MultiTurnAgent(cfg=cfg, log_file=f"CHATAPP_{trial_id}")

    def _publish_tree(self):
        self.hub.publish(self.trial_id, {"type": "tree", "tree": self.tree.to_dict()})

    def _publish_chat(self, role: str, content: str):
        self.hub.publish(self.trial_id, {"type": "chat", "role": role, "content": content})

    def _publish_status(self, status: str):
        self.hub.publish(self.trial_id, {"type": "status", "status": status})

    def _enrich_chain_via_simulate(self, trial_id: str, ops: List[str]) -> List[dict]:
        """Re-run /simulate to collect per-op outputs (table name + preview).

        MultiTurnAgent internally calls /simulate but only returns text observations.
        Here we call it again to get structured metadata used by the operator tree UI.
        """
        try:
            hist = self.agent.client.simulate_trial(
                trial_id=trial_id,
                operators=ops,
                mode=self.cfg.get("execute_mode", "rule"),
            )

            # ApiClient implementations vary: some return a list of rows, others return {"history": [...]}.
            rows = hist
            if isinstance(hist, dict):
                rows = hist.get("history")

            if not isinstance(rows, list):
                rows = []

            # Ensure the minimum keys exist
            steps: List[dict] = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                steps.append(
                    {
                        "op": r.get("op"),
                        "out_table": r.get("out_table"),
                        "out_preview": r.get("out_preview"),
                    }
                )

            # If simulate didn't return anything, fall back to bare ops.
            return steps if steps else [{"op": x} for x in ops]
        except Exception:
            return [{"op": x} for x in ops]

    def _execute_solution_locally(self, solution: str):
        state = self.store.get_trial(self.trial_id)
        base_trial = state.trial
        tmp = copy.deepcopy(base_trial)
        executor = Executor(cfg=Config.load_current_config(), debug=False, log_file=f"CHATAPP_{self.trial_id}")

        last_df = None
        last_table_name = None
        for op_str in _split_chain(solution):
            op = auto_parse_op(op_str)
            out_name, out_df = executor.execute_op(op, tmp, mode=self.cfg.get("execute_mode", "rule"))
            executor.step_op(op, tmp, out_name, out_df)
            last_df = out_df
            last_table_name = out_name

        state.result_df = last_df
        state.result_table_name = last_table_name

    def run(self):
        state = self.store.get_trial(self.trial_id)
        trial = state.trial

        messages = []
        try:
            max_turn = int(self.cfg.get("max_explore_turn", 5) or 5)
        except Exception:
            max_turn = 5

        self._publish_status("running")
        self._publish_chat("assistant", "Agent started. Generating operator chains...")
        self._publish_tree()

        final_solution: Optional[str] = None

        for i in range(max_turn + 1):
            cur_turn = i + 1
            self.agent._clear_state()
            while True:
                try:

                    # Let UI know we are actively waiting on the LLM for this turn.
                    self._publish_status(f"thinking (turn {cur_turn})")
                    think, operator_chain, solution, obs, messages = self.agent._multiturn_step(trial, cur_turn, messages)
                    trial.record("think", think)
                    trial.record("operator", operator_chain)
                    trial.record("solution", solution)
                    trial.record("observation", obs)

                    # Back to running once we have a response.
                    self._publish_status("running")
                    break
                except Exception as e:
                    # MultiTurnAgent internally retries on some HTTP errors; we keep it simple here.
                    self.agent._raise_error(str(e))
                    continue

            # Emit assistant content
            if think:
                self._publish_chat("assistant", f"<think> {think} </think>")

            if operator_chain:
                ops = _split_chain(operator_chain)
                steps = self._enrich_chain_via_simulate(trial.exp_id, ops)

                for s in steps:
                    s["turn"] = cur_turn
                self.tree.add_chain(steps, is_solution=False)
                self._publish_chat("assistant", f"<operator> {operator_chain} </operator>")
                self._publish_tree()

            if solution:
                final_solution = solution
                ops = _split_chain(solution)
                steps = self._enrich_chain_via_simulate(trial.exp_id, ops)

                for s in steps:
                    s["turn"] = cur_turn
                path_ids = self.tree.add_chain(steps, is_solution=True)
                self._publish_chat("assistant", f"<solution> {solution} </solution>")
                self._publish_tree()
                self.hub.publish(self.trial_id, {"type": "highlight", "path": path_ids})
                break

        if not final_solution:
            self._publish_status("failed")
            self._publish_chat("assistant", f"Agent failed to generate a solution within {max_turn} turns.")
            return

        # Execute to produce target table
        try:
            self._publish_status("executing")
            self._execute_solution_locally(final_solution)
            state = self.store.get_trial(self.trial_id)
            preview = {
                "columns": list(state.result_df.columns.astype(str))[:50] if state.result_df is not None else [],
                "rows": state.result_df.head(20).fillna("").astype(str).values.tolist() if state.result_df is not None else [],
                "shape": [int(state.result_df.shape[0]), int(state.result_df.shape[1])] if state.result_df is not None else [0, 0],
            }
            self.hub.publish(
                self.trial_id,
                {
                    "type": "result",
                    "tableName": state.result_table_name,
                    "preview": preview,
                },
            )
            self._publish_status("done")
        except Exception as e:
            self._publish_status("failed")
            self._publish_chat("assistant", f"Failed to execute final solution: {e}")


def start_runner_in_background(*, cfg: dict, store: InMemoryStore, hub: TrialEventHub, trial_id: str) -> threading.Thread:
    runner = InteractiveMultiTurnRunner(cfg=cfg, store=store, hub=hub, trial_id=trial_id)
    t = threading.Thread(target=runner.run, daemon=True)
    t.start()
    return t
