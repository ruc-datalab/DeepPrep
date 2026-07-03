from .base_agent import BaseAgent
from src.data import Trial
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import parse_any_string, parse_tag_wrapped_string
from src.tools.helper.gpt_inference import GPT
from src.physicalop import *
from app.client import ApiClient
import httpx
import copy

class MultiTurnAgent(BaseAgent):
    def __init__(self, name: str='MultiTurn Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.llm = GPT(self.cfg)
        self.mode = self.cfg.get('execute_mode')
        self.client = ApiClient()

    def _check_solution(self, trial: Trial, solution: str):
        if not ('Terminate' in solution.split('-->')[-1]):
            raise Exception('The operator chain within the <solution> tag must end with a Terminate operator to output a table as target table.')
        
        tmp_trial = copy.deepcopy(trial)
        tmp_trial.exp_id, _, _ = self.client.copy_trial(trial.exp_id)
        
        for op in solution.split('-->'):
            op = op.strip()
            auto_parse_op(op)
            try:
                self.client.add_step(trial_id=tmp_trial.exp_id, op=op, mode=self.mode)
            except Exception as e:
                raise Exception(f'In the generated solution: <solution> {solution} </solution>, the operator {op} cannot be executed! Try to debug the operator chain.')
        
        return True


    def _multiturn_step(self, trial: Trial, cur_turn: int, messages: list):
        if cur_turn == 1:
            sys_prompt, user_prompt = PromptGenerator.multiturn_agent_generate(self.cfg, trial, last_error=self.last_log, cur_turn=cur_turn, his_op_and_output='')
            messages = []
            messages.append({"role": "system", "content": sys_prompt})
            messages.append({"role": "user", "content": user_prompt})
        else:
            pass
        
        self.logger.log_messages(messages)
        out, think_content = self.llm.query(messages, get_thinking=True)
        self.logger.log_with_think_content(think_content, out)

        think, solution, operator_chain = self._parse_multiturn_output(out)
        if think is None: think = think_content

        if solution and operator_chain:
            if cur_turn >= self.cfg.get('max_explore_turn'):  operator_chain = None
            else: solution = None

        parsed_content = ""
        if think: parsed_content += f'<think> {think} </think>\n'

        if solution:
            self._check_solution(trial, solution)
            parsed_content += f'<solution> {solution} </solution>'
            messages.append({"role": "assistant", "content": parsed_content.strip()})
            return think, None, solution, None, messages

        if operator_chain:
            parsed_content += f'<operator> {operator_chain} </operator>'
            messages.append({"role": "assistant", "content": parsed_content.strip()})

        # operator_chain exists
        obs = None
        op_str_lis = [a.strip() for a in operator_chain.split('-->') if a.strip() != '']
        if len(op_str_lis) > self.cfg.get('max_explore_op'):
            raise Exception(f'The number of operators in the operator chain is greater than the max number of exploring operators: {self.cfg.get("max_explore_op")}!')

        obs = self.client.get_simulate_trial_exe_obs(trial_id=trial.exp_id, operators=op_str_lis, mode=self.mode)
        obs_str = '\n'.join(['\n'.join(x) for x in obs])

        if cur_turn >= self.cfg.get('max_explore_turn'): # If the current turn is the final turn to output the solution.
            turn_left_str = 'This is the last turn to complete the task. You should try to use the solution tag to output the final operator chain.'
        else:
            if self.cfg.get('max_explore_turn') > 10: # If the max explore turn is set to a large number, we do not remind the user about the remaining turns.
                turn_left_str = f'You can use operator tag for further exploration or use solution tag to output the final operator chain.'
            else:
                turn_left_str = f'You can use operator tag for further exploration (You have {self.cfg.get("max_explore_turn") - cur_turn} more exploration turns left) or use solution tag to output the final operator chain.'
        
        turn_left_str += ' You can refer to the results in previous turns, but remember to generate operator chain from the scratch.'

        reminder_str = f'<reminder>{turn_left_str}</reminder>'

        observation_msg = f'<observation> {obs_str}\n{reminder_str} </observation>'
        messages.append({"role": "user", "content": observation_msg})

        return think, operator_chain, None, obs_str, messages
    
    def multiturn_step(self, trial: Trial):
        messages = []

        for i in range(self.cfg.get('max_explore_turn')+1):
            cur_turn = i + 1 # The exploration turn number starts from 1.
            self._clear_state()

            while True:
                try:
                    # cur turn: 1, 2, 3, 4, 5, 6 (final turn to output solution)
                    think, operator_chain, solution, obs, messages = self._multiturn_step(trial, cur_turn, messages)
                    trial.record('think', think)
                    trial.record('operator', operator_chain)
                    trial.record('solution', solution)
                    trial.record('observation', obs)
                    break
                except httpx.HTTPStatusError as e:
                    error_msg = e.response.json()['detail']
                    continue
                except Exception as e:
                    error_msg = str(e)
                    self._raise_error(error_msg)
                    continue

            if solution:
                break
            if not obs:
                messages.append({"role": "user", "content": "<warning> Please follow the instructions in # Hint Section. </warning>"})
            

        trial.record('messages', messages)
        trial.record('turn', cur_turn)

        if not solution:
            raise Exception(f'The Agent failed to generate a solution within {self.cfg.get("max_explore_turn")} turns!')

        return solution

    def _parse_multiturn_output(self, output: str) -> str:
        """
        Parse the output of the ds agent.
        """
        # if '<observation>' in output and '</observation>' in output:
        #     raise Exception('The <observation> tag **should not** be used in the output! An external executor will automatically execute the operator chain and return the execution result wrapped by the <observation> tag.')
        think = parse_tag_wrapped_string(output, tag='think', hard_replace=['your_think_here']) \
            if '<think>' in output and '</think>' in output else None
        solution = parse_tag_wrapped_string(output, tag='solution', hard_replace=['your_solution_here']) \
            if '<solution>' in output and '</solution>' in output else None
        operator_chain = parse_tag_wrapped_string(output, tag='operator', hard_replace=['your_operator_here']) \
            if '<operator>' in output and '</operator>' in output else None

        if operator_chain is None and solution is None:
            raise Exception('The operator chain and solution cannot be both None! This means current turn takes no action.')
        
        return think, solution, operator_chain
