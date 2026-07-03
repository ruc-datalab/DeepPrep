from .base_agent import BaseAgent
from src.data import Trial
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import parse_any_string, parse_tag_wrapped_string
from src.tools.helper.gpt_inference import GPT
from src.physicalop import *
from app.client import ApiClient
import httpx

class SelfReflectionAgent(BaseAgent):
    def __init__(self, name: str='SelfReflection Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.llm = GPT(self.cfg)
        self.mode = self.cfg.get('execute_mode')
        self.client = ApiClient()

    def self_reflection_solution_generate(self, trial: Trial, cur_turn: int, messages_generate: list):
        if cur_turn == 1:
            prompt = PromptGenerator.self_reflection_agent_solution_generate(self.cfg, trial, last_error=self.last_log, cur_turn=cur_turn, his_op_and_output='')
            messages_generate.append({"role": "user", "content": prompt})
        else: pass

        self.logger.log_messages(messages_generate)
        out, think_content = self.llm.query(messages_generate, get_thinking=True)
        self.logger.log_with_think_content(think_content, out)

        think, solution = self._parse_solution_output(out)
        if think is None: think = think_content

        parsed_content = ""
        if think: parsed_content += f'<think> {think} </think>\n'

        if solution is None:
            raise Exception('The solution cannot be None! This means current turn takes no action.')

        if not ('Terminate' in solution.split('-->')[-1]):
            raise Exception('The operator chain within the <solution> tag must end with a Terminate operator to output a table as target table.')

        parsed_content += f'<solution> {solution} </solution>'
        messages_generate.append({"role": "assistant", "content": parsed_content.strip()})

        # operator_chain exists
        obs = None
        op_str_lis = [a.strip() for a in solution.split('-->') if a.strip() != '']

        obs = self.client.get_simulate_trial_exe_obs(trial_id=trial.exp_id, operators=op_str_lis, mode=self.mode)
        obs_str = '\n'.join(['\n'.join(x) for x in obs])

        matched, message = self.client.simulate_trial_and_evaluate(trial_id=trial.exp_id, operators=op_str_lis, mode=self.mode)
        eval_str = f'Evaluate the generated table and the target table: {"[Matched]!" if matched else "[Unmatched]!"} {message}'

        if self.last_log: last_error_if_exist = f'\n** Last Error **: {self.last_log}. Try to avoid the error in the current Output.'
        else: last_error_if_exist = ''

        if cur_turn >= self.cfg.get('max_reflect_turn'): # If the current turn is the final turn to output the solution.
            turn_left_str = 'This is the last turn to complete the task. You should try to use the <solution> tag to output the final operator chain.'
        else:
            turn_left_str = f'Next, use <reflect> tag to reflect on the correctness of the previous solution.'

        reminder_str = f'<reminder>{turn_left_str}{last_error_if_exist}</reminder>'

        observation_msg = f'<observation> {obs_str}\n{reminder_str} </observation>'
        messages_generate.append({"role": "user", "content": observation_msg})

        # evaluation_msg = f'<evaluation> {eval_str} </evaluation>'
        # messages_generate.append({"role": "user", "content": evaluation_msg})

        # Prepare history string for reflection
        history_str = '\n\n'.join([msg['content'] for msg in messages_generate[1:]])

        return think, solution, obs_str, messages_generate, history_str
    
    def self_reflection_reflect(self, trial: Trial, cur_turn: int, history_str: str):
        # Check the evaluation result from history
        # if '[Matched]!' in history_str:
        #     reflect_content = '<reflect> [CorrectSolution] </reflect>'
        #     messages_reflect.append({"role": "assistant", "content": reflect_content})
        #     return '[CorrectSolution]', True, messages_reflect
        messages_reflect = []
        prompt = PromptGenerator.self_reflection_agent_reflect(self.cfg, trial, last_error=self.last_log, cur_turn=cur_turn, his_op_and_output=history_str)
        messages_reflect.append({"role": "user", "content": prompt})

        self.logger.log_messages(messages_reflect)
        out = self.llm.query(messages_reflect)
        self.logger.log(out)

        reflection = parse_tag_wrapped_string(out, tag='reflect', hard_replace=['your_reflection_here'])

        if reflection is None:
            raise Exception('The reflection cannot be None!')

        if '[CorrectSolution]' in reflection:
            solution_correct = True
        elif '[WrongSolution]' in reflection:
            solution_correct = False
        else:
            raise Exception('The reflection must contain either [CorrectSolution] or [WrongSolution]!')

        return reflection, solution_correct

    def step(self, trial: Trial):
        messages_generate = []

        for i in range(self.cfg.get('max_reflect_turn')+1):
            cur_turn = i + 1 # The reflection turn number starts from 1.
            self._clear_state()

            while True:
                try:
                    think, solution, obs, messages_generate, history_str = self.self_reflection_solution_generate(trial, cur_turn, messages_generate)
                    trial.record('think', think)
                    trial.record('solution', solution)
                    trial.record('observation', obs)
                    # if max_reflect_turn is 0, skip the reflection step
                    if self.cfg.get('max_reflect_turn') == 0: 
                        solution_correct = True
                        break
                    reflection, solution_correct = self.self_reflection_reflect(trial, cur_turn, history_str)
                    trial.record('reflection', reflection)
                    trial.record('solution_correct', solution_correct)
                    break
                except httpx.HTTPStatusError as e:
                    error_msg = e.response.json()['detail']
                    continue
                except Exception as e:
                    error_msg = str(e)
                    self._raise_error(error_msg)
                    continue

            if solution_correct:
                break

        trial.record('turn', cur_turn)
        
        if not solution:
            raise Exception(f'The Agent failed to generate a solution within {self.cfg.get("max_reflect_turn")} turns!')
        
        return solution
    
    def _parse_solution_output(self, output: str) -> str:
        """
        Parse the output of the ds agent.
        """
        think = parse_tag_wrapped_string(output, tag='think', hard_replace=['your_think_here']) \
            if '<think>' in output and '</think>' in output else None
        solution = parse_tag_wrapped_string(output, tag='solution', hard_replace=['your_solution_here']) \
            if '<solution>' in output and '</solution>' in output else None
        
        return think, solution
