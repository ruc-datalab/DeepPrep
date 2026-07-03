import uuid

from src.agent.base_agent import BaseAgent
from src.data import Task, Trial
from src.tools.utils import parse_any_string
from src.tools.helper import GPTPOOL
from src.physicalop import *
from src.prompt.prompt_generator import PromptGenerator 

class CriticAgent(BaseAgent):
    def __init__(self, name: str='Critic Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.name = name
        self.llm = GPTPOOL(self.cfg)
        self.his_critic = []
        self.max_critic_cnt = self.cfg.get('critic_max_cnt')
    
    def critique_path(self, trial: Trial, op_path: list[BaseOp], final_obs: str) -> bool:
        """
        Uses the LLM to critique an entire path of operators.
        Returns True if the path is deemed correct, False otherwise.
        """
        op_path_str = "\n".join([f"- {str(op)}" for op in op_path])
        
        prompt = PromptGenerator.mcts_critic_critique_path(
            trial=trial,
            op_path=op_path_str,
            output_obs=final_obs
        )
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)

        if '[Correct]' in out:
            return True
        return False

    def _clear_his_suggestions(self):
        self.his_critic = []

    def _add_incorrect_critic_suggestion(self, op: BaseOp, obs: str, suggestion: str):
        self.his_critic.append({
            'op': op,
            'obs': obs,
            'suggestion': suggestion
        })

    def step(self, output:str, trial: Trial, current_op: BaseOp):
        self._clear_state()
        while True:
            try:
                return self._step(output, trial, current_op)
            except Exception as e:
                self._raise_error(e)

    def _step(self, output:str, trial: Trial, current_op: BaseOp):
        """This function is the working function of the critic agent.
        Input: 
            - file: critic base on the file.value
            - trial: the current trial
            - current_op: the current operation
        Output:
            - accept: whether to accept the current operation
            - suggestion(optional): If the operation is not accepted, the debugging suggestion"""
        if len(self.his_critic) >= self.max_critic_cnt:
            self.logger.log(f"Critic agent has reached the maximum number of suggestions ({self.max_critic_cnt}).")
            return True, None

        critic_output = self._generate(trial, output, current_op)
        accept, suggestion = self._parse_critic_result(critic_output)

        if accept: self._clear_his_suggestions()
        else: self._add_incorrect_critic_suggestion(current_op, output, suggestion)

        return accept, suggestion
        

    def _generate(self, trial: Trial, output: str, current_op: BaseOp) -> str:
        prompt = PromptGenerator.critic_agent_critic(
            trial=trial, output=output, current_op=current_op, last_error=self.last_log, 
            his_fail_trial=self._serialize_his_suggestions() if len(self.his_critic) > 0 else None)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        return out

    def _parse_critic_result(self, output: str) -> tuple:
        """
        Parse the output of the critic agent.
        """
        accept, suggestion = False, None
        out = parse_any_string(output, hard_replace='special_token_or_suggestion_here')
        if '[CorrectExecution]' in out:
            accept = True
        else:
            suggestion = out
        
        return accept, suggestion
    
    def _serialize_his_suggestions(self) -> str:
        eles = []
        for i, dic in enumerate(self.his_critic):
            op, obs, suggestion = dic['op'], dic['obs'], dic['suggestion']
            eles.append(f"**Critic try [{i+1}]**")
            eles.append(f"**Operation**: {op}")
            eles.append(f"**Observation**: {obs}")
            eles.append(f"**Failed Suggestion**: {suggestion}")
            eles.append('---')
        
        return '\n'.join(eles)
        