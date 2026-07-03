import os
import uuid
from app.client import ApiClient

from src.module.api_caller import APICaller
from src.tools.helper import Config
from src.agent.mcts_agent import MCTSAgent
from src.module import Executor, Evaluator
from src.data import Task, Trial
from src.tools.helper import Logger
from src.tools.utils import save_pickle

class MCTSFramework:
    def __init__(self, cfg=None, log_file='_MAIN'):
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.agent = MCTSAgent(cfg=self.cfg, log_file=log_file)
        self.client = ApiClient()
        self.logger = Logger(name='[MAS] MCTSFramework', cfg=self.cfg, log_file=log_file)
        self.max_steps = self.cfg.get('mcts_max_steps', 50)

    def run(self, task: Task):
        self.logger.log(f'Current processing task: {task.id}...')
        trial = self._initialize_trial(task)
        self.trial = trial
        # MCTS search for best operator chain
        try:
            total_chains, best_chain, best_score, root = self.agent.mcts_search(trial)
        except Exception as e:
            self.logger.log(f"Error in MCTS search: {e}")
            total_chains, best_chain, best_score, root = self.agent.total_chains, self.agent.best_chain, self.agent.best_score, self.agent.root
        trial.record('total_chains', total_chains)
        trial.record('best_chain', best_chain)
        trial.record('best_score', best_score)
        trial.record('tol_inputs', self.agent.tol_inputs)
        trial.record('tol_outputs', self.agent.tol_outputs)
        trial.record('mct', self.agent.mct_to_json(root))
        
        # Execute the best chain
        if best_chain:
            matched = self.execute_op_chain(best_chain, trial)
        else:
            matched = False
            self.logger.log("No valid operator chain found by MCTS")

        trial.matched = matched
        self.logger.log(f'Successful processing task: {task.id} done.')
        self.client.delete_trial(trial_id=trial.exp_id)
        save_pickle(trial, os.path.join(self.cfg.get('filecachedir'), 'versions', self.cfg.get_version(), 'saved_trials', f"{trial.task.id}.pkl"))
        return trial

    def execute_op_chain(self, op_chain, trial: Trial):
        """Execute a chain of operators on the trial"""
        for op in op_chain:
            if hasattr(op, 'op') and op.op == 'Terminate':
                trial.add_op(op, "Terminated")
                break
            try:
                op, obs = self.client.execute_operator(trial.exp_id, op=str(op))
                message = self.client.add_step(trial.exp_id, op)
                trial.add_op(op, obs)
            except Exception as e:
                self.logger.log(f"Error executing operator {op}: {e}")
                trial.add_op(op, f"Error: {e}")
        
        matched, _ = self.client.evaluate_trial(trial.exp_id)
        return matched

    def _initialize_trial(self, task: Task) -> Trial:
        trial_id, message = self.client.create_trial(
            input_tables=task.inp_tbl_names, target_description=Trial.generate_schema_description(task), 
            tgt_tbl_path=task.tgt_tbl_name, task_id=task.id, split=task.split)
        exp_id = trial_id
        trial = Trial(exp_id=exp_id, task=task)
        self.trial = trial
        trial.load(task)
        return trial