import uuid, os
import httpx

from src.tools.helper import Config
from src.agent import *
from src.data import Task, Trial, DataPool
from src.tools.helper import Logger
from src.module import Evaluator
from src.tools.utils import save_pickle, get_benchmark_from_task_id
from app.client import ApiClient

class CodeGenerationFramework:
    def __init__(self, cfg=None, log_file='_MAIN'):
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.code_agent = CodeGen(cfg=self.cfg, log_file=log_file)
        self.evaluator = Evaluator(cfg=self.cfg, log_file=log_file)
        self.logger = Logger(name = 'ReactOp', cfg=self.cfg, log_file=log_file)

    def run(self, task: Task):
        benchmark = get_benchmark_from_task_id(task.id)
        if task.split in DataPool.ground_truth[benchmark] and task.id in DataPool.ground_truth[benchmark][task.split]:
            ground_truth_str = "\n".join([str(op) for op in DataPool.ground_truth[benchmark][task.split][task.id]])
            self.code_agent.logger.log(f'Current processing task: {task.id}. With ground truth to be:\n\n{ground_truth_str}')
        else:
            self.code_agent.logger.log(f'Current processing task: {task.id}. No ground truth.')
            
        trial = Trial.load_trial(task_id=task.id, split=task.split)
        self.trial = trial

        try:
            trial = self.code_agent.code_gen(trial)
        except Exception as e:
            self.logger.log(f'Error: {e}')
            trial.error_message = str(e)
            return self.trial
        
        # Evaluate the trial
        matched, message = self.evaluator.evaluate_trial_tables(trial)
        if matched:
            self.logger.log(f'Trial {trial.exp_id} matched.')
            self.trial.matched = True
        else:
            self.logger.log(f'Trial {trial.exp_id} did not match.')
            self.trial.matched = False

        save_pickle(self.trial, os.path.join(self.cfg.get('filecachedir'), f"versions", self.cfg.get_version(), 'saved_trials', f"{self.trial.task.id}.pkl"))
        
        return self.trial