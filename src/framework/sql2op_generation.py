import uuid, copy, os
import httpx

from src.tools.helper import Config
from src.agent import ReactAgent, SelfReflectionAgent
from src.data import Task, Trial, DataPool
from src.tools.helper import Logger
from src.module import Evaluator, Executor
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import save_pickle, save_json, load_pickle, open_json, get_benchmark_from_task_id
from app.client import ApiClient
from src.tools.utils import parse_tag_wrapped_string

class MyReActAgent(ReactAgent):
    def __init__(self, name: str='React Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)

    def _generate(self, trial: Trial, cur_turn: int) -> str:
        prompt = PromptGenerator.react_agent_sql2op_generate(cfg=self.cfg, trial=trial, last_error=self.last_log, cur_turn=cur_turn)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        return out

class MySelfReflectionAgent(SelfReflectionAgent):
    def __init__(self, name: str='Self Reflection Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)

    def self_reflection_solution_generate(self, trial: Trial, cur_turn: int, messages_generate: list):
        if cur_turn == 1:
            prompt = PromptGenerator.self_reflection_agent_sql2op_solution_generate(self.cfg, trial, last_error=self.last_log, cur_turn=cur_turn, his_op_and_output='')
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

        evaluation_msg = f'<evaluation> {eval_str} </evaluation>'
        messages_generate.append({"role": "user", "content": evaluation_msg})

        # Prepare history string for reflection
        history_str = '\n\n'.join([msg['content'] for msg in messages_generate[1:]])

        return think, solution, obs_str, messages_generate, history_str
    
    def self_reflection_reflect(self, trial: Trial, cur_turn: int, history_str: str):
        # Check the evaluation result from history
        if '[Matched]!' in history_str:
            return '[CorrectSolution]', True

        messages_reflect = []
        prompt = PromptGenerator.self_reflection_agent_sql2op_reflect(self.cfg, trial, last_error=self.last_log, cur_turn=cur_turn, his_op_and_output=history_str)
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

class SQL2OpFramework:
    def __init__(self, cfg=None, log_file='_MAIN'):
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.evaluator = Evaluator(cfg=self.cfg, log_file=log_file)
        self.executor = Executor(cfg=self.cfg, log_file=log_file)
        self.logger = Logger(name = 'SQL2Op', cfg=self.cfg, log_file=log_file)
        self.react_agent = MyReActAgent(cfg=self.cfg, log_file=log_file)
        self.self_reflection_agent = MySelfReflectionAgent(cfg=self.cfg, log_file=log_file)
        self.client = ApiClient()
        self.mode = self.cfg.get('execute_mode', 'rule')
        self.supported_prompting_functions = [self.react_step, self.self_reflection_step]
        self.prompting_round = 2

    def react_step(self, trial: Trial):

        try:
            solution = self.react_agent.reactop_step(trial)
        except Exception as e:
            self.logger.log(f'Error: {e}')
            trial.error_message = str(e)
            return None
        
        return solution

    def self_reflection_step(self, trial: Trial):

        try:
            solution = self.self_reflection_agent.step(trial)
        except Exception as e:
            self.logger.log(f'Error: {e}')
            trial.error_message = str(e)
            return None
        
        return solution
    
    def run(self, task: Task):
        json_fn = os.path.join(self.cfg.get('filecachedir'), f"versions", self.cfg.get_version(), 'solutions', f"{task.id}.json")
        if os.path.exists(json_fn): return open_json(json_fn)
        
        trial = self._initialize_trial(task)
        self.trial = trial

        tried_prompting_functions = []
        for i, prompting_function in enumerate(self.supported_prompting_functions):
            for cur_round in range(self.prompting_round):

                new_trial = copy.deepcopy(trial)
                new_trial_id, _, _ = self.client.copy_trial(trial_id=trial.exp_id)
                new_trial.exp_id = new_trial_id
                
                solution = prompting_function(new_trial)
                tried_prompting_functions.append(prompting_function.__name__)
                if solution is None:
                    continue
                if isinstance(solution, str):
                    solution = [x.strip() for x in solution.split('-->') if x.strip() != '']
                if not isinstance(solution, list):
                    raise Exception(f'The solution must be a list of operators!')
                solution = [str(op) for op in solution]
                
                # evaluate the solution
                matched, message = self.client.simulate_trial_and_evaluate(trial_id=trial.exp_id, operators=solution, mode=self.mode)
                if matched:
                    save_json({'solution': solution, 'matched': matched, 'prompting_method_idx': i, 'prompting_round': cur_round, 'tried_prompting_functions': tried_prompting_functions}, json_fn)
                    self.logger.log(f'Trial {trial.exp_id} Solution generated successfully. Solution: {" --> ".join(solution)}')
                    return solution
                else:
                    trial.suggestion = f'In your last round, you have generated a solution: {" --> ".join(solution)}. However, the generated table does not match the target table, it has difference: {message}. You should try to avoid the same error in this new round.'
                    self.logger.log(f'Trial {trial.exp_id} did not match. Suggestion: {trial.suggestion}')

        return 'No Solution'

    def _initialize_trial(self, task: Task) -> Trial:
        benchmark = get_benchmark_from_task_id(task.id)
        if task.split in DataPool.ground_truth[benchmark] and task.id in DataPool.ground_truth[benchmark][task.split]:
            ground_truth_str = "\n".join([str(op) for op in DataPool.ground_truth[benchmark][task.split][task.id]])
            self.react_agent.logger.log(f'Current processing task: {task.id}. With ground truth to be:\n\n{ground_truth_str}')
        else:
            self.react_agent.logger.log(f'Current processing task: {task.id}. No ground truth.')

        trial_id, message = self.client.create_trial(   
            input_tables=task.inp_tbl_names, target_description=Trial.generate_schema_description(task), 
            tgt_tbl_path=task.tgt_tbl_name, task_id=task.id, split=task.split)
        exp_id = trial_id
        trial = Trial(exp_id=exp_id, task=task)
        self.trial = trial
        trial.load(task)
        return trial
