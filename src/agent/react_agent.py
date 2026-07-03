from .base_agent import BaseAgent
from src.data import Trial
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import parse_any_string, parse_tag_wrapped_string
from src.tools.helper import GPTPOOL
from src.physicalop import *
from app.client import ApiClient
import httpx

class ReactAgent(BaseAgent):
    def __init__(self, name: str='React Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.llm = GPTPOOL(self.cfg)
        self.mode = self.cfg.get('execute_mode')
        self.client = ApiClient()
        self.tol_inputs, self.tol_outputs = [], []

    def select_inverse_op_for_table(self, df: pd.DataFrame, candidate_dc_op: List[BaseOp] = None):
        self._clear_state()
        op2desc = {op.__name__: INVERSE_DESC_DICT[op.__name__] for op in candidate_dc_op}
        desc2op = {v: k for k, v in op2desc.items()}
        total_inverse_op = list(desc2op.keys())
        self.MAX_ERR_CNT = 5
        while True:
            try:
                shuffle(total_inverse_op)
                ops_str = ', '.join(total_inverse_op)
                prompt = PromptGenerator.select_inverse_op_for_table(cfg=self.cfg, df=df, last_error=self.last_log, ops_str=ops_str)

                self.logger.log(prompt)
                response = self.llm.query(prompt)
                self.logger.log(response)

                self.tol_inputs.append(prompt)
                self.tol_outputs.append(response)

                out_op_str = parse_any_string(response, code_type='python', hard_replace=['your_operator_here']).strip()
                for inverse_op in total_inverse_op:
                    if inverse_op in out_op_str:
                        return eval(desc2op[inverse_op])
                raise Exception(f'You should output one invervse operation we offer. But you output {out_op_str}, which is not in {ops_str}. Please output correct one.')
            except Exception as e:
                self.logger.log(f'Error during selecting inverse operation: {e}')
                self._raise_error(e)


    def _generate(self, trial: Trial, cur_turn: int) -> str:
        prompt = PromptGenerator.react_agent_generate(cfg=self.cfg, trial=trial, last_error=self.last_log, cur_turn=cur_turn)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)

        self.tol_inputs.append(prompt)
        self.tol_outputs.append(out)
        return out

    def generte_op_to_restore_table(self, dirty_table: pd.DataFrame, target_table: pd.DataFrame, message: str, op_class: BaseOp):
        self._clear_state()
        self.MAX_ERR_CNT = 2
        while True:
            try:
                prompt = PromptGenerator.react_agent_restore_clean_table(cfg=self.cfg, dirty_table=dirty_table, target_table=target_table, difference=message, op_class=op_class, last_error=self.last_log)
                self.logger.log(prompt)
                out = self.llm.query(prompt)
                self.logger.log(out)

                self.tol_inputs.append(prompt)
                self.tol_outputs.append(out)
                if '[FailToSolve]' in out:
                    return None
                op_str = parse_tag_wrapped_string(rsp=out, tag='operator', hard_replace=['your_operator_here'])
                op_obj = auto_parse_op(op_str)
                return op_obj
            except Exception as e:
                self._raise_error(e)


    def reactop_step(self, trial: Trial):
        done = False
        self.tol_inputs, self.tol_outputs = [], []
        for i in range(self.cfg.get('max_explore_turn')):
            cur_turn = i + 1
            self._clear_state()
            while True:
                try:
                    cur_op = self._step(trial, cur_turn)
                    op, obs = self.client.execute_operator(trial_id=trial.exp_id, op=str(cur_op), mode=self.mode)
                    self.client.add_step(trial_id=trial.exp_id, op=str(cur_op), mode=self.mode)
                    trial.add_op(auto_parse_op(op), obs)
                    break
                except httpx.HTTPStatusError as e:
                    error_msg = e.response.json()['detail']
                    self._raise_error(error_msg)
                except Exception as e:
                    error_msg = str(e)
                    self._raise_error(error_msg)
        
            if isinstance(cur_op, Terminate):
                done = True
                break
        
        solution = trial.ops

        if not done:
            raise Exception(f'The Agent failed to generate a solution within {self.cfg.get("max_explore_turn")} turns!')
        
        return solution

    def _step(self, trial: Trial, cur_turn: int):
        output = self._generate(trial, cur_turn)
        op = self._parse_action_result(output)
        op = self._post_process(trial, op)
        return op

    def _generate(self, trial: Trial, cur_turn: int) -> str:
        prompt = PromptGenerator.react_agent_generate(cfg=self.cfg, trial=trial, last_error=self.last_log, cur_turn=cur_turn)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        self.tol_inputs.append(prompt)
        self.tol_outputs.append(out)
        return out

    def _parse_action_result(self, output: str) -> str:
        """
        Parse the output of the ds agent.
        """
        # Parse the output to get the action
        action = parse_tag_wrapped_string(rsp=output, tag='operator', hard_replace=['your_operator_here'])
        op = auto_parse_op(action)
        return op
    
    def _post_process(self, trial: Trial, cur_op: BaseOp):
        return cur_op
    