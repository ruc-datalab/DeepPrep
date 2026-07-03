import json

from .base_agent import BaseAgent
from src.data import Task, Trial
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import parse_any_string
from src.tools.helper import GPTPOOL
from src.physicalop import *

class PlannerAgent(BaseAgent):
    def __init__(self, name: str='Planner Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.name = name
        self.llm = GPTPOOL(self.cfg)

    def update_subtask(self, trial: Trial, freeze_last_index: int): # id在[0, freeze_last_index]之间的subtask不更新
        self._clear_state()
        while True:
            try:
                return self._update_subtask(trial, freeze_last_index)
            except Exception as e:
                self._raise_error(e)

    def _update_subtask(self, trial: Trial, freeze_last_index: int):
        planner_output = self._generate_update_subtask(trial, freeze_last_index)
        subtasks = self._parse_result_update_subtask(planner_output)
        
        for nex_subt in subtasks:
            if nex_subt in trial.task.subtasks:
                raise ValueError(f"Your output: {nex_subt} already exists in the subtasks! Do not repeat the same subtask.")
            
        trial.task.subtasks = trial.task.subtasks[:freeze_last_index+1] + subtasks
        return trial
    
    def _generate_update_subtask(self, trial: Trial, freeze_last_index: int) -> str:
        prompt = PromptGenerator.planner_agent_update_subtask(
            trial=trial, freeze_last_index=freeze_last_index, last_error=self.last_log)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        return out
    
    def _parse_result_update_subtask(self, output: str) -> tuple:
        out = parse_any_string(output, hard_replace=['json_data', 'json'])
        if '[NOTHING_UPDATE]' in out: return []

        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            raise ValueError(f"Your output: {out} cannot be parsed as JSON, please check your output format.")
        
        if 'next_subtasks' not in data:
            raise ValueError(f"Your output: {out} does not contain 'next_subtasks' key, please check your output format.")
        
        next_subtasks = data['next_subtasks']
        if not isinstance(next_subtasks, list):
            raise ValueError(f"Your output: {out} contains 'next_subtasks' key but it's not a list, please check your output format.")

        return next_subtasks

    def step(self, trial: Trial):
        self._clear_state()
        while True:
            try:
                return self._step(trial)
            except Exception as e:
                self._raise_error(e)

    def _step(self, trial: Trial):
        """This function is the working function of the planner agent.
        Input: 
            - task (trial.task): the overall task
        Output:
            - sub-questions
            - desired metadata"""
        planner_output = self._generate(trial)
        subtasks = self._parse_step_result(planner_output)
        
        trial.task.subtasks = subtasks

        return trial

    def _generate(self, trial: Trial) -> str:
        prompt = PromptGenerator.planner_agent_step(
            trial=trial, last_error=self.last_log)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        return out

    def _parse_step_result(self, output: str) -> tuple:
        """
        Parse the output of the planner agent.
        """
        out = parse_any_string(output, hard_replace=['json_data', 'json'])
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            raise ValueError(f"Your output: {out} cannot be parsed as JSON, please check your output format.")
        
        if 'subtasks' not in data:
            raise ValueError(f"Your output: {out} does not contain 'subtasks' key, please check your output format.")
        
        subtasks = data['subtasks']
        if not isinstance(subtasks, list):
            raise ValueError(f"Your output: {out} contains 'subtasks' key but it's not a list, please check your output format.")
        
        return subtasks
        