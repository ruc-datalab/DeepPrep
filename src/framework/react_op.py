import uuid, os
import httpx

from src.tools.helper import Config
from src.agent import *
from src.data import Task, Trial, DataPool
from src.tools.helper import Logger
from src.tools.utils import save_pickle, get_benchmark_from_task_id
from app.client import ApiClient

class ReactOp:
    def __init__(self, cfg=None, log_file='_MAIN'):
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.react_agent = ReactAgent(cfg=self.cfg, log_file=log_file)
        self.logger = Logger(name = 'ReactOp', cfg=self.cfg, log_file=log_file)
        self.client = ApiClient()

    def run(self, task: Task):
        benchmark = get_benchmark_from_task_id(task.id)
        if task.split in DataPool.ground_truth[benchmark] and task.id in DataPool.ground_truth[benchmark][task.split]:
            ground_truth_str = "\n".join([str(op) for op in DataPool.ground_truth[benchmark][task.split][task.id]])
            self.react_agent.logger.log(f'Current processing task: {task.id}. With ground truth to be:\n\n{ground_truth_str}')
        else:
            self.react_agent.logger.log(f'Current processing task: {task.id}. No ground truth.')
        trial = self._initialize_trial(task)
        self.trial = trial

        try:
            solution = self.react_agent.reactop_step(trial)
        except Exception as e:
            self.logger.log(f'Error: {e}')
            trial.error_message = str(e)
            return self.trial
        
        # Evaluate the trial
        trial.record('tol_inputs', self.react_agent.tol_inputs)
        trial.record('tol_outputs', self.react_agent.tol_outputs)
        
        matched, message = self.client.evaluate_trial(trial_id=trial.exp_id)
        if matched:
            self.logger.log(f'Trial {trial.exp_id} matched.')
            self.trial.matched = True
        else:
            self.logger.log(f'Trial {trial.exp_id} did not match.')
            self.trial.matched = False

        save_pickle(self.trial, os.path.join(self.cfg.get('filecachedir'), f"versions", self.cfg.get_version(), 'saved_trials', f"{self.trial.task.id}.pkl"))
        
        self.client.delete_trial(trial_id=trial.exp_id)
        
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