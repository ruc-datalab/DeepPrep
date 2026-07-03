from .base_agent import BaseAgent
from src.data import Trial
from src.prompt.prompt_generator import PromptGenerator
from src.physicalop import InverseDeduplicate, InverseDropNulls, InverseExplode, InversePivot, InverseStack, InverseTranspose, InverseWideToLong
from src.tools.utils import parse_any_string, parse_tag_wrapped_string
from src.tools.helper import GPTPOOL
from src.physicalop import *
from app.client import ApiClient
import httpx

class InverseOpAgent(BaseAgent):
    def __init__(self, name: str='DataScience Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.llm = GPTPOOL(self.cfg)
        self.mode = self.cfg.get('execute_mode')
        self.client = ApiClient()

    def make_dataset_dirty(self, trial: Trial):
        tbl_struc_trans_cnt = 0
        candidate_ops = ['InverseDeduplicate', 'InverseDropNulls', 'InverseExplode', 'InversePivot', 'InverseStack', 'InverseTranspose', 'InverseWideToLong']
        generated_ops = []
        while len(candidate_ops) > 0:
            break #!


    
    def reactop_step(self, trial: Trial):
        done = False
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
    


    # TODO: This function is not robust.
    def _parse_multiturn_continuous_output(self, output: str) -> str:
        if '<observation>' in output and '</observation>' in output:
            raise Exception('The <observation> tag should not be used in the output!')

        think = parse_tag_wrapped_string(output, tag='think', hard_replace=['your_think_here'])
        refer_turn_num = parse_tag_wrapped_string(output, tag='refer_turn_num', hard_replace=['your_refer_turn_num_here'])
        copy_operator_num = parse_tag_wrapped_string(output, tag='copy_operator_num', hard_replace=['your_copy_operator_num_here'])

        solution = parse_tag_wrapped_string(output, tag='solution', hard_replace=['your_solution_here']) \
            if '<solution>' in output and '</solution>' in output else None
        operator_chain = parse_tag_wrapped_string(output, tag='operator', hard_replace=['your_operator_here']) \
            if '<operator>' in output and '</operator>' in output else None
        
        if refer_turn_num is None or refer_turn_num.strip() == 'None' or\
              copy_operator_num is None or copy_operator_num.strip() == 'None':
            refer_turn_num = None
            copy_operator_num = None

        else:
            try:
                refer_turn_num = int(refer_turn_num)
                copy_operator_num = int(copy_operator_num)
            except:
                raise Exception('The refer_turn_num and copy_operator_num must be integers!')
        
        return think, refer_turn_num, copy_operator_num, solution, operator_chain
    
    def _refer_and_copy_operator(self, trial: Trial, refer_turn_num: int, copy_operator_num: int, operator_chain: str) -> str:
        if 'operator' not in trial.record or refer_turn_num > len(trial.recording['operator']):
            raise Exception(f'The refer_turn_num {refer_turn_num} is out of range!')
        
        refer_operator_chain = trial.recording['operator'][refer_turn_num - 1]
        refer_ops = [a.strip() for a in refer_operator_chain.split('-->') if a.strip() != '']

        cur_ops = [a.strip() for a in operator_chain.split('-->') if a.strip() != '']

        if len(refer_ops) < copy_operator_num:
            raise Exception(f'The number of operators in the operator chain is less than the copy_operator_num {copy_operator_num}!')
        
        new_ops = refer_ops[:copy_operator_num] + cur_ops
        new_operator_chain = '-->'.join(new_ops)
        return new_operator_chain

    def multiturn_continuous_step(self, trial: Trial):
        his_op_and_output = ''
        for i in range(self.cfg.get('max_explore_turn')):
            cur_turn = i + 1

            prompt = PromptGenerator.multiturn_continuous_agent_generate(self.cfg, trial, last_error=self.last_log, cur_turn=cur_turn, his_op_and_output=his_op_and_output)
            self.logger.log(prompt)
            out = self.llm.query(prompt)
            self.logger.log(out)

            try:
                think, refer_turn_num, copy_operator_num, solution, operator_chain = self._parse_multiturn_continuous_output(out)
            except Exception as e:
                self.last_log = str(e)
                continue
            
            trial.record('think', think)
            trial.record('refer_turn_num', refer_turn_num)
            trial.record('copy_operator_num', copy_operator_num)
            trial.record('raw_operator', operator_chain)
            trial.record('operator', operator_chain)
            trial.record('solution', solution)

            if isinstance(refer_turn_num, int) and isinstance(copy_operator_num, int):
                if solution:
                    self.last_log = 'The <solution> tag should not be used when you refer to the previous turn. And you should not output a solution when you refer to the previous turn.'
                    continue
                operator_chain = self._refer_and_copy_operator(trial, refer_turn_num, copy_operator_num, operator_chain)
                trial.record_pop('operator')
                trial.record('operator', operator_chain)

            if solution:
                if not ('Terminate' in solution.split('-->')[-1]):
                    self.last_log = 'The operator chain within the <solution> tag must end with a Terminate operator to output a table as target table.'
                    continue
                break

            obs = None

            if not operator_chain: obs = 'No valid operator found. Your should output either an operator or a solution.'
            else:
                op_str_lis = [a.strip() for a in operator_chain.split('-->')]
                obs = self.client.get_simulate_trial_exe_obs(trial_id=trial.exp_id, operators=op_str_lis, mode=self.mode)
                
                if len(obs) > 0 and len(obs[0]) == 1:
                    obs_str = '\n'.join(['\n'.join(x) for x in obs])
                else:
                    obs_str = f'[Please refer to the first {copy_operator_num} Outputs from Turn {refer_turn_num}]\n' + '\n'.join(['\n'.join(x) for x in obs[copy_operator_num:]])
            
            his_op_and_output = f'{his_op_and_output}\n\n<operator> {operator_chain} </operator>\n\n<observation> {obs_str} </observation>'
            trial.record('observation', obs_str)

        final_solution = solution
        if not final_solution:
            final_solution = operator_chain

        trial.record('final_solution', final_solution)
        trial.record('turn', cur_turn)
        
        if not final_solution:
            raise Exception(f'The Agent failed to generate a solution within {self.cfg.get("max_explore_turn")} turns!')
        
        return final_solution
