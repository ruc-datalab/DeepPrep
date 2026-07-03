import uuid, os

from src.tools.helper import Config
from src.agent import *
from src.data import Task, Trial, DataPool
from src.tools.helper import Logger
from src.tools.utils import parse_any_string, save_pickle, get_benchmark_from_task_id
from src.physicalop import auto_parse_op, BaseOp, Terminate
from app.client import ApiClient

class TrainMode:
    EVALUATE = 'evaluate'
    TRAIN = 'rl_training'

class MultiTurnOps:
    def __init__(self, cfg=None, log_file='_MAIN'):
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.multiturn_agent = MultiTurnAgent(cfg=self.cfg, log_file=log_file)
        self.logger = Logger(name = 'MultiTurnsGenChain', cfg=self.cfg, log_file=log_file)
        self.mode = self.cfg.get('execute_mode')
        self.client = ApiClient()

    def implement_physical_op_with_processed_trial(self, trial: Trial):
        trial_id, message = self.client.create_trial_with_task_id(task_id=trial.task.id, split=trial.task.split)
        trial.exp_id = trial_id

        if 'solution' in trial.recording:
            sol = None
            for solution in trial.recording['solution']:
                if solution:
                    sol = solution
                    break
            if sol:
                ops = [auto_parse_op(op) for op in sol.split('-->') if op.strip()]
                for op in ops:
                    op = str(op)
                    self.client.add_step(trial_id=trial.exp_id, op=op, mode=self.mode)
                matched, message = self.client.evaluate_trial(trial_id=trial.exp_id)
                self.client.delete_trial(trial_id=trial.exp_id)
                return matched
                
        return None

    def run(self, task: Task):
        benchmark = get_benchmark_from_task_id(task.id)
        if task.split in DataPool.ground_truth[benchmark] and task.id in DataPool.ground_truth[benchmark][task.split]:
            ground_truth_str = "\n".join([str(op) for op in DataPool.ground_truth[benchmark][task.split][task.id]])
            self.multiturn_agent.logger.log(f'Current processing task: {task.id}. With ground truth to be:\n\n{ground_truth_str}')
        else:
            self.multiturn_agent.logger.log(f'Current processing task: {task.id}. No ground truth.')
        trial = self._initialize_trial(task)
        self.trial = trial

        try:
            solution = self.multiturn_agent.multiturn_step(trial)
        except Exception as e:
            self.logger.log(f'Error: {e}')
            trial.error_message = str(e)
            return self.trial
        
        # Execute the solution step by step
        for op in solution.split('-->'):
            op = op.strip()
            message = self.client.add_step(trial_id=trial.exp_id, op=op, mode=self.mode)
            if message != 'Step added successfully.':
                self.logger.log(f'Error when adding step {op}: {message}')
                trial.error_message = message
                return self.trial
            
        # Evaluate the trial
        matched, message = self.client.evaluate_trial(trial_id=trial.exp_id)
        self.client.delete_trial(trial_id=trial.exp_id)
        if matched:
            self.logger.log(f'Trial {trial.exp_id} matched.')
            self.trial.matched = True
        else:
            self.logger.log(f'The target table is:', self.trial.tgt_tbl, sep='\n')
            self.logger.log(f'Trial {trial.exp_id} did not match, the message is: {message}')
            self.trial.matched = False

        save_path = os.path.join(self.cfg.get('filecachedir'), f"versions", self.cfg.get_version(), 'saved_trials', f"{self.trial.task.id}.pkl")
        if task.split == 'train' and \
            not self.trial.matched:
            save_path = os.path.join(self.cfg.get('filecachedir'), f"versions", self.cfg.get_version(), 'saved_trials_unmatched', f"{self.trial.task.id}.pkl")
            
        save_pickle(self.trial, save_path)

        return self.trial

    def _initialize_trial(self, task: Task) -> Trial:
        trial_id, message = self.client.create_trial(
            input_tables=task.inp_tbl_names, target_description=Trial.generate_schema_description(task), 
            tgt_tbl_path=task.tgt_tbl_name, task_id=task.id, split=task.split)
        exp_id = trial_id
        trial = Trial(exp_id=exp_id, task=task)
        self.trial = trial
        trial.load(task)
        return trial
