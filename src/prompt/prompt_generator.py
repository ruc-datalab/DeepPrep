import os
import json
from typing import List

from src.physicalop import *
from src.data.trial import Trial, DataPool
from src.tools.utils import load_text_file, all_filepaths_in_dir
from src.tools.helper import Config
from src.tools.utils import df_to_cotable

import random

def load_prompts(root: str) -> dict:
    prompts = {}
    prompt_root = os.path.join(root, 'agent')
    for fp in all_filepaths_in_dir(root=prompt_root, endswith='.md'):
        fn = os.path.basename(fp).split('.')[0]
        agent, module = fn.split('_')
        prompt = load_text_file(fp)
        if agent not in prompts:
            prompts[agent] = {}
        prompts[agent][module] = prompt

    demo_prompts = {}
    demo_root = os.path.join(root, 'demo')
    for fp in all_filepaths_in_dir(root=demo_root, endswith='.md'):
        fn = os.path.basename(fp).split('.')[0]
        agent, module = fn.split('_')
        prompt = load_text_file(fp)
        if agent not in demo_prompts:
            demo_prompts[agent] = {}
        demo_prompts[agent][module] = prompt

    system_msgs = {}
    sysmsg_root = os.path.join(root, 'system_message')
    for fp in all_filepaths_in_dir(root=sysmsg_root, endswith='.md'):
        fn = os.path.basename(fp).split('.')[0]
        agent, module = fn.split('_')
        prompt = load_text_file(fp)
        if agent not in system_msgs:
            system_msgs[agent] = {}
        system_msgs[agent][module] = prompt
    
    role_msgs = {}
    role_msg_root = os.path.join(root, 'role')
    for fp in all_filepaths_in_dir(root=role_msg_root, endswith='.md'):
        fn = os.path.basename(fp).split('.')[0]
        agent, module = fn.split('_')
        prompt = load_text_file(fp)
        if agent not in role_msgs:
            role_msgs[agent] = {}
        role_msgs[agent][module] = prompt
    
    return prompts, system_msgs, role_msgs, demo_prompts

class PromptGenerator:
    
    PROMPTS, SYSMSG, ROLE, DEMO = load_prompts(root='src/prompt')

    @staticmethod
    def error_analyzer_analyze(trial: Trial, error_category:dict, last_error:str=None) -> str:
        """error_category: {tag: {error_category: str, error_reason_sample: List[str]}}"""
        trial.load(trial.task)
        inp_tbl = trial.serialize_input_tables()
        tgt_tbl = Trial.generate_schema_description(trial.task)

        eles = []
        i = 0
        for think, operator, observation in zip(
            trial.recording['think'], 
            trial.recording['operator'], 
            trial.recording['observation']):
            i += 1
            eles.append(f"Turn {i}:")
            if think:
                eles.append(f"<think> {think} </think>")
            if operator:
                eles.append(f"<operator> {operator} </operator>")
            if observation:
                eles.append(f"<observation> {observation} </observation>")
            eles.append('')
        final_solution = operator
        if 'final_solution' in trial.recording:
            final_solution = trial.recording['final_solution']
        eles.append(f"<solution> {final_solution} </solution>")
        process = '\n'.join(eles)

        eles = []
        for i, tag in enumerate(list(error_category.keys())):
            eles.append(f"Error Category #{i+1}:")
            eles.append(f"\t- Error Category Tag: {tag}")
            eles.append(f"\t- Error Category: {error_category[tag]['error_category']}")
            eles.append(f"\t- Error Reason Example:")
            for error_reason_sample in error_category[tag]['error_reason']:
                eles.append(f"\t\t- {error_reason_sample}")
        error_category_str = '\n'.join(eles)
        
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''
        
        prompt = PromptGenerator.PROMPTS['ErrorAnalyzer']['Analyze']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['ErrorAnalyzer']['Analyze'].strip(),
            system_msg=PromptGenerator.SYSMSG['ErrorAnalyzer']['Analyze'].strip(),
            inp_tbl=inp_tbl.strip(),
            tgt_tbl=tgt_tbl.strip(),
            process=process.strip(),
            error_category_str=error_category_str.strip(),
            last_error_if_exist=last_error_if_exist.strip(),
        )
        return prompt
    
    @staticmethod
    def multiturn_continuous_agent_generate(cfg: Config, trial: Trial, last_error:str=None, cur_turn:int=0, his_op_and_output:str=None) -> str:
        cur_ops: List[BaseOp] = TOTAL_OPS
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        inp_tbls = trial.serialize_input_tables(cut_line=cfg.get('ini_tbl_cut_line'), cut_col=cfg.get('ini_tbl_cut_col'))
        tgt_tbl_schema_description = Trial.generate_schema_description(task=trial.task)

        if trial.suggestion: suggestion_if_exist = f'** Suggestion for generating the next op **: {trial.suggestion}\n\n'
        else: suggestion_if_exist = ''
        
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        prompt = PromptGenerator.PROMPTS['DSAgent']['MultiturnContinuousOps']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['DSAgent']['MultiturnContinuousOps'].strip(),
            ops=op_str.strip(),
            demo=PromptGenerator.DEMO['DSAgent']['MultiturnContinuousOps'].strip(),

            system_msg=PromptGenerator.SYSMSG['DSAgent']['MultiturnOps'].strip().format(
                max_explore_turn=cfg.get('max_explore_turn')),
                
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),
            suggestion_if_exist=suggestion_if_exist,
            last_error_if_exist=last_error_if_exist.strip(),
            max_explore_turn=cfg.get('max_explore_turn'),
            cur_turn=cur_turn,
            his_op_and_output=his_op_and_output.strip(),
        )
        return prompt

    @staticmethod
    def self_reflection_agent_solution_generate(cfg: Config, trial: Trial, last_error:str=None, cur_turn:int=0, his_op_and_output:str='') -> str: 
        cur_ops: List[BaseOp] = TOTAL_OPS
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(task=trial.task)

        if trial.suggestion: suggestion_if_exist = f'** Suggestion for generating the next op **: {trial.suggestion}\n\n'
        else: suggestion_if_exist = ''
        
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        prompt = PromptGenerator.PROMPTS['SelfReflectionAgent']['SolutionGenerate']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['SelfReflectionAgent']['SolutionGenerate'].strip(),
            ops=op_str.strip(),
            demo=PromptGenerator.DEMO['SelfReflectionAgent']['SolutionGenerate'].strip(),
            system_msg=PromptGenerator.SYSMSG['SelfReflectionAgent']['SolutionGenerate'].strip().format(
                max_reflect_turn=cfg.get('max_reflect_turn')),

            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),

            max_reflect_turn=cfg.get('max_reflect_turn'),
            his_op_and_output=his_op_and_output.strip(),
        )

        if not his_op_and_output:
            prompt = prompt.replace('\n\n# History Operator Chains and Outputs\n\n', '')
        return prompt
    
    @staticmethod
    def self_reflection_agent_sql2op_solution_generate(cfg: Config, trial: Trial, last_error:str=None, cur_turn:int=0, his_op_and_output:str='') -> str: 
        cur_ops: List[BaseOp] = SQL_OPS
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl = df_to_cotable(trial.tgt_tbl)

        if trial.suggestion: suggestion_if_exist = f'** Suggestion for generating the next op **: {trial.suggestion}\n\n'
        else: suggestion_if_exist = ''
        
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        prompt = PromptGenerator.PROMPTS['SelfReflectionAgent']['Sql2OpSolutionGenerate']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['SelfReflectionAgent']['SolutionGenerate'].strip(),
            ops=op_str.strip(),
            demo=PromptGenerator.DEMO['SelfReflectionAgent']['SolutionGenerate'].strip(),
            system_msg=PromptGenerator.SYSMSG['SelfReflectionAgent']['SolutionGenerate'].strip().format(
                max_reflect_turn=cfg.get('max_reflect_turn')),

            inp_tbls=inp_tbls.strip(),
            tgt_tbl=tgt_tbl.strip(),
            sql=DataPool.get_sql(task_id=trial.task.id, split=trial.task.split),

            max_reflect_turn=cfg.get('max_reflect_turn'),
            his_op_and_output=his_op_and_output.strip(),
        )

        if not his_op_and_output:
            prompt = prompt.replace('\n\n# History Operator Chains and Outputs\n\n', '')
        return prompt
    
    def select_inverse_op_for_table(cfg: Config, df: pd.DataFrame, last_error:str=None, ops_str:str = None) -> BaseOp:
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''
        input_table = df_to_cotable(df)
        prompt = PromptGenerator.PROMPTS['Other']['SelectInverseOp']
        prompt = prompt.format(
            input_table=input_table.strip(),
            ops=ops_str.strip(),
            last_error_if_exist=last_error_if_exist.strip(),
        )
        return prompt

    @staticmethod
    def self_reflection_agent_reflect(cfg: Config, trial: Trial, last_error:str=None, cur_turn:int=0, his_op_and_output:str='') -> str: 
        cur_ops: List[BaseOp] = TOTAL_OPS
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(task=trial.task)
    
        if trial.suggestion: suggestion_if_exist = f'** Suggestion for generating the next op **: {trial.suggestion}\n\n'
        else: suggestion_if_exist = ''
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        prompt = PromptGenerator.PROMPTS['SelfReflectionAgent']['SelfReflect']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['SelfReflectionAgent']['SelfReflect'].strip(),
            ops=op_str.strip(),
            system_msg=PromptGenerator.SYSMSG['SelfReflectionAgent']['SelfReflect'].strip(),
            demo=PromptGenerator.DEMO['SelfReflectionAgent']['SelfReflect'].strip(),
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),
            his_op_and_output=his_op_and_output.strip(),
            # suggestion_if_exist=suggestion_if_exist,
            # last_error_if_exist=last_error_if_exist,
        )

        if not his_op_and_output:
            prompt = prompt.replace('\n\n# History Operator Chains and Outputs\n\n', '')
        return prompt

    @staticmethod
    def self_reflection_agent_sql2op_reflect(cfg: Config, trial: Trial, last_error:str=None, cur_turn:int=0, his_op_and_output:str='') -> str: 
        cur_ops: List[BaseOp] = TOTAL_OPS
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl = df_to_cotable(trial.tgt_tbl)
    
        if trial.suggestion: suggestion_if_exist = f'** Suggestion for generating the next op **: {trial.suggestion}\n\n'
        else: suggestion_if_exist = ''
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        prompt = PromptGenerator.PROMPTS['SelfReflectionAgent']['SelfReflect']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['SelfReflectionAgent']['SelfReflect'].strip(),
            ops=op_str.strip(),
            system_msg=PromptGenerator.SYSMSG['SelfReflectionAgent']['SelfReflect'].strip(),
            demo=PromptGenerator.DEMO['SelfReflectionAgent']['SelfReflect'].strip(),
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl.strip(),
            his_op_and_output=his_op_and_output.strip(),
            # suggestion_if_exist=suggestion_if_exist,
            # last_error_if_exist=last_error_if_exist,
        )

        if not his_op_and_output:
            prompt = prompt.replace('\n\n# History Operator Chains and Outputs\n\n', '')
        return prompt

    @staticmethod
    def multiturn_agent_generate(cfg: Config, trial: Trial, last_error:str=None, cur_turn:int=0, his_op_and_output:str='') -> str: 
        cur_ops: List[BaseOp] = TOTAL_OPS
        if cfg.get('diverse_input'):
            random.shuffle(cur_ops)
            # shuffle the row and column of the input tables
            for table_name, table in trial.tables.items():
                table = table.sample(frac=1).reset_index(drop=True)
                trial.tables[table_name] = table
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(task=trial.task)

        if trial.suggestion: suggestion_if_exist = f'** Suggestion for generating the next op **: {trial.suggestion}\n\n'
        else: suggestion_if_exist = ''
        
        if last_error: last_error_if_exist = f'\n** Last Error **: {last_error}. Try to avoid the error in the current Output.'
        else: last_error_if_exist = ''

        prompt_sys = PromptGenerator.PROMPTS['MultiturnAgent']['MultiturnOpsSys']
        prompt_user = PromptGenerator.PROMPTS['MultiturnAgent']['MultiturnOpsUser']

        sys_message = PromptGenerator.SYSMSG['MultiturnAgent']['MultiturnOps'].strip().format(
                max_explore_turn=cfg.get('max_explore_turn'))
        if cfg.get('max_explore_turn') > 10:
            sys_message = sys_message.replace(f'You will have {cfg.get("max_explore_turn")} to explore. ', 'You have multiple turns to explore the operators to complete the task.')

        prompt_sys = prompt_sys.format(
            role=PromptGenerator.ROLE['MultiturnAgent']['MultiturnOps'].strip(),
            ops=op_str.strip(),
            demo=PromptGenerator.DEMO['MultiturnAgent']['MultiturnOps'].strip(),
            system_msg=sys_message,
        )
        prompt_user = prompt_user.format(
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),
            last_err=last_error_if_exist.strip(),
            # max_explore_turn=cfg.get('max_explore_turn'),
            his_op_and_output=his_op_and_output.strip(),
        )

        if not his_op_and_output:
            prompt_user = prompt_user.replace('\n\n# History Operator Chains and Outputs\n\n', '')
        return prompt_sys, prompt_user

    @staticmethod
    def multiturn_agent_generate_zeroshot(cfg: Config, trial: Trial, last_error:str=None, cur_turn:int=0, his_op_and_output:str='') -> str: 
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(task=trial.task)

        if trial.suggestion: suggestion_if_exist = f'** Suggestion for generating the next op **: {trial.suggestion}\n\n'
        else: suggestion_if_exist = ''
        
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        prompt_sys = PromptGenerator.PROMPTS['DSAgent']['MultiturnOpsZeroshotSys']
        prompt_user = PromptGenerator.PROMPTS['DSAgent']['MultiturnOpsZeroshotUser']

        prompt_sys = prompt_sys.format(
            role=PromptGenerator.ROLE['DSAgent']['MultiturnOps'].strip(),
            system_msg=PromptGenerator.SYSMSG['DSAgent']['MultiturnOps'].strip().format(
                max_explore_turn=cfg.get('max_explore_turn')),
        )
        prompt_user = prompt_user.format(
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),
            last_error_if_exist=last_error_if_exist.strip(),
            max_explore_turn=cfg.get('max_explore_turn'),
            his_op_and_output=his_op_and_output.strip(),
            cur_turn=cur_turn,
        )

        if not his_op_and_output:
            prompt_user = prompt_user.replace('\n\n# History Operator Chains and Outputs\n\n', '')
        return prompt_sys, prompt_user
    
    @staticmethod
    def react_agent_restore_clean_table(cfg: Config, dirty_table: pd.DataFrame, target_table: pd.DataFrame, difference: str, op_class: BaseOp, last_error:str=None) -> str:
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        if 'Please reduce the input length.' in last_error_if_exist or 'E(GPT):' in last_error_if_exist:
            last_error_if_exist = ''
            cut_line = 20
            cut_col = 10
        else:
            cut_line = cfg.get('ini_tbl_cut_line')
            cut_col = cfg.get('ini_tbl_cut_col')

        dirty_table_str = df_to_cotable(dirty_table, cut_line=cut_line, cut_col=cut_col)
        target_table_str = df_to_cotable(target_table, cut_line=cut_line, cut_col=cut_col)

        op_str = op_class.get_action_description().strip()

        prompt = PromptGenerator.PROMPTS['ReactAgent']['RestoreCleanTable']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['ReactAgent']['RestoreCleanTable'].strip(),
            system_message=PromptGenerator.SYSMSG['ReactAgent']['RestoreCleanTable'].strip(),
            op=op_str.strip(),
            dirty_table=dirty_table_str.strip(),
            target_table=target_table_str.strip(),
            difference=difference.strip(),
            last_error_if_exist=last_error_if_exist.strip(),
        )
        return prompt

    @staticmethod
    def react_agent_sql2op_generate(cfg: Config, trial: Trial, last_error:str=None, cur_turn:int=0) -> str:
        cur_ops: List[BaseOp] = SQL_OPS
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        his_op_and_output = trial.seralize_ops_and_observations()

        inp_tbls = Trial.serialize_initial_table(task_id=trial.task.id, split=trial.task.split)
        tgt_tbl = df_to_cotable(trial.tgt_tbl)

        if trial.suggestion: suggestion_if_exist = f'** Suggestion for current task **: {trial.suggestion}\n\n'
        else: suggestion_if_exist = ''
        
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''  

        prompt = PromptGenerator.PROMPTS['ReactAgent']['Sql2OpGenerate']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['ReactAgent']['Sql2OpGenerate'].strip(),
            inp_tbls=inp_tbls.strip(),
            tgt_tbl=tgt_tbl.strip(),
            his_op_and_output=his_op_and_output.strip(),
            ops=op_str.strip(),
            sql=DataPool.get_sql(task_id=trial.task.id, split=trial.task.split),
            system_msg=PromptGenerator.SYSMSG['ReactAgent']['ReactNextOp'].strip().format(
                max_explore_turn=cfg.get('max_explore_turn')),
            suggestion_if_exist=suggestion_if_exist,
            last_error_if_exist=last_error_if_exist,
            demo=PromptGenerator.DEMO['ReactAgent']['Sql2OpGenerate'].strip(),
            cur_turn=cur_turn,
            max_explore_turn=cfg.get('max_explore_turn'),
        )
        return prompt

    @staticmethod
    def react_agent_generate(cfg: Config, trial: Trial, last_error:str=None, cur_turn:int=0) -> str:
        cur_ops: List[BaseOp] = TOTAL_OPS
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        his_op_and_output = trial.seralize_ops_and_observations()

        inp_tbls = Trial.serialize_initial_table(task_id=trial.task.id, split=trial.task.split)
        tgt_tbl_schema_description = Trial.generate_schema_description(trial.task)

        if trial.suggestion:
            suggestion_if_exist = f'** Suggestion for generating the next op **: {trial.suggestion}\n\n'
        else:
            suggestion_if_exist = ''
        
        if last_error:
            last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else:
            last_error_if_exist = ''

        prompt = PromptGenerator.PROMPTS['ReactAgent']['ReactNextOp']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['ReactAgent']['ReactNextOp'].strip(),
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),
            his_op_and_output=his_op_and_output.strip(),
            ops=op_str.strip(),
            system_msg=PromptGenerator.SYSMSG['ReactAgent']['ReactNextOp'].strip().format(
                max_explore_turn=cfg.get('max_explore_turn')),
            suggestion_if_exist=suggestion_if_exist,
            last_error_if_exist=last_error_if_exist,
            demo=PromptGenerator.DEMO['ReactAgent']['ReactNextOp'].strip(),
            cur_turn=cur_turn,
            max_explore_turn=cfg.get('max_explore_turn'),
        )
        return prompt

    @staticmethod
    def mcts_agent_select_and_complete(cfg: Config, trial: Trial) -> str:
        cur_ops: List[BaseOp] = TOTAL_OPS
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        his_op_and_output = trial.seralize_ops_and_observations()

        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(trial.task)

        prompt = PromptGenerator.PROMPTS['MCTSAgent']['SelectAndComplete']
        prompt = prompt.format(
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),
            his_op_and_output=his_op_and_output.strip(),
            ops=op_str.strip()
        )
        return prompt

    @staticmethod
    def mcts_agent_expand(cfg: Config, trial: Trial) -> str:
        cur_ops: List[BaseOp] = TOTAL_OPS # Assuming TOTAL_OPS is the list of all available ops
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        his_op_and_output = trial.seralize_ops_and_observations()

        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(trial.task)

        prompt = PromptGenerator.PROMPTS['MCTSAgent']['Expand']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['MCTSAgent']['Expand'].strip(),
            system_msg=PromptGenerator.SYSMSG['MCTSAgent']['Expand'].strip(),
            demo=PromptGenerator.DEMO['MCTSAgent']['Expand'].strip(),
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),
            his_op_and_output=his_op_and_output.strip(),
            ops=op_str.strip()
        )
        return prompt

    @staticmethod
    def mcts_agent_rollout(cfg: Config, trial: Trial) -> str:
        cur_ops: List[BaseOp] = TOTAL_OPS
        op_str = '\n\n'.join([op.get_action_description().strip() for op in cur_ops])
        his_op_and_output = trial.seralize_ops_and_observations()

        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(trial.task)

        prompt = PromptGenerator.PROMPTS['MCTSAgent']['Rollout']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['MCTSAgent']['Rollout'].strip(),
            system_msg=PromptGenerator.SYSMSG['MCTSAgent']['Rollout'].strip(),
            demo=PromptGenerator.DEMO['MCTSAgent']['Rollout'].strip(),
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),
            his_op_and_output=his_op_and_output.strip(),
            ops=op_str.strip()
        )
        return prompt

    @staticmethod
    def mcts_critic_critique_path(trial: Trial, op_path: str, output_obs: str) -> str:
        """Generates a prompt for the critic to evaluate an entire path."""
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(trial.task)

        prompt = PromptGenerator.PROMPTS['MCTSAgent']['Critic']
        prompt = prompt.format(
            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),
            op_path=op_path.strip(),
            output_obs=output_obs.strip()
        )
        return prompt

    @staticmethod
    def critic_agent_critic(trial: Trial, output: str, current_op: BaseOp, last_error:str=None, his_fail_trial:str=None) -> str:

        his_op = trial.seralize_ops_and_observations()
        cur_op = str(current_op)

        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = json.dumps(trial.tgt_tbl_schema_description, indent=4)
        
        if last_error:
            last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else:
            last_error_if_exist = ''

        prompt = PromptGenerator.PROMPTS['CriticAgent']['Critic']
        prompt = prompt.format(
            role = PromptGenerator.ROLE['CriticAgent']['Critic'].strip(),
            his_op = his_op.strip(),
            cur_op = cur_op.strip(),
            inp_tbls = inp_tbls.strip(),
            tgt_tbl_schema_description = tgt_tbl_schema_description.strip(),
            obs = output.strip(),
            last_error_if_exist=last_error_if_exist.strip(),
            his_fail_trial=his_fail_trial.strip() if his_fail_trial else 'Empty',
            demo=PromptGenerator.DEMO['CriticAgent'][trial.task.type_].strip(),
        )
        return prompt
    
    def code_agent_generate_inverse_op(cfg: Config, df: pd.DataFrame, op: BaseOp, last_error:str=None) -> str:
        # get the class name of the op
        op_name = op.__name__
        op_class = op
        inverse_op_name = f"Inverse{op_name}"
        op_str = op_class.get_action_description().replace('##', '').strip()

        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''
        
        if 'Please reduce the input length.' in last_error_if_exist or 'E(GPT):' in last_error_if_exist:
            last_error_if_exist = ''
            cut_line = 20
            cut_col = 10
        else:
            cut_line = cfg.get('ini_tbl_cut_line')
            cut_col = cfg.get('ini_tbl_cut_col')

        df_str = df_to_cotable(df, cut_line=cut_line, cut_col=cut_col)
        # op replace ##, [op_replace_tag] replace with op_str
        prompt = PromptGenerator.PROMPTS['CodeAgent']['GenerateInverseOp']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['CodeAgent']['GenerateInverseOp'].strip(),
            demo=PromptGenerator.DEMO['CodeAgent'][f'Inverse{op_name}'].strip(),
            system_msg=PromptGenerator.SYSMSG['CodeAgent']['GenerateInverseOp'].strip(),
            input_table=df_str.strip(),
            op = op_str.strip(),
            last_error_if_exist=last_error_if_exist.strip(),
        ).replace('[op_replace_tag]', op_str)

        return prompt

    def code_agent_select_data_cleaning_operators(cfg: Config, df: pd.DataFrame, op_candidates: list[BaseOp], last_error:str=None) -> str:

        op_str = '\n\n'.join([op.get_action_description().strip() for op in op_candidates])

        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        if 'Please reduce the input length.' in last_error_if_exist or 'E(GPT):' in last_error_if_exist:
            cut_line = 20
            cut_col = 10
            last_error_if_exist = ''
        else:
            cut_line = cfg.get('ini_tbl_cut_line')
            cut_col = cfg.get('ini_tbl_cut_col')

        df_str = df_to_cotable(df, cut_line=cut_line, cut_col=cut_col)

        prompt = PromptGenerator.PROMPTS['CodeAgent']['SelectDataCleaningOperators']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['CodeAgent']['SelectDataCleaningOperators'].strip(),
            demo=PromptGenerator.DEMO['CodeAgent']['SelectDataCleaningOperators'].strip(),
            system_msg=PromptGenerator.SYSMSG['CodeAgent']['SelectDataCleaningOperators'].strip(),
            input_table=df_str.strip(),
            op_candidates=op_str.strip(),
            last_error_if_exist=last_error_if_exist,
        )
        return prompt
    
    def code_agent_generate(cfg:Config, trial: Trial, last_error:str=None) -> str:
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(task=trial.task)
        
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        prompt = PromptGenerator.PROMPTS['CodeAgent']['Generate']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['CodeAgent']['Generate'].strip(),
            demo=PromptGenerator.DEMO['CodeAgent']['Generate'].strip(),
            system_msg=PromptGenerator.SYSMSG['CodeAgent']['Generate'].strip(),

            inp_tbls=inp_tbls.strip(),
            tgt_tbl_schema_description=tgt_tbl_schema_description.strip(),

            last_error_if_exist=last_error_if_exist,
        )

        return prompt
    
    @staticmethod
    def code_agent_implement_logical_operator(cfg:Config, trial: Trial, last_error:str=None, op:BaseOp=None) -> str:
        inp_tbls = trial.serialize_input_tables()
        
        if last_error: last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else: last_error_if_exist = ''

        prompt = PromptGenerator.PROMPTS['CodeAgent']['ImplementLogicalOperator']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['CodeAgent']['ImplementLogicalOperator'].strip(),
            demo=PromptGenerator.DEMO['CodeAgent']['ImplementLogicalOperator'].strip(),
            system_msg=PromptGenerator.SYSMSG['CodeAgent']['ImplementLogicalOperator'].strip(),
            inp_tbls = inp_tbls,
            op = str(op),
            last_error_if_exist = last_error_if_exist,
        )
        return prompt

    @staticmethod
    def op_distance_agent_estimate(trial: Trial, last_error: str=None) -> str:
        inp_tbls = trial.serialize_input_tables()
        his_ops_and_obs = trial.seralize_ops_and_observations()
        
        if last_error:
            last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else:
            last_error_if_exist = ''
        
        prompt = PromptGenerator.PROMPTS['OpDistanceAgent']['Estimate']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['OpDistanceAgent']['Estimate'].strip(),
            system_msg=PromptGenerator.SYSMSG['OpDistanceAgent']['Estimate'].strip(),
            demo=PromptGenerator.DEMO['OpDistanceAgent']['Estimate'].strip(),
            inp_tbls=inp_tbls.strip(),
            his_ops_and_obs=his_ops_and_obs.strip(),
            target_schema=Trial.generate_schema_description(trial.task).strip(),
            last_error_if_exist=last_error_if_exist.strip(),
        )
        return prompt

    @staticmethod
    def op_distance_agent_v2_estimate(trial: Trial, generated_table, target_table, difference, last_error: str=None) -> str:
        inp_tbls = trial.serialize_input_tables()
        his_ops_and_obs = trial.seralize_ops_and_observations()
        generated_table_str = df_to_cotable(generated_table)
        target_table_str = df_to_cotable(target_table)
        
        if last_error:
            last_error_if_exist = f'** Last Error **: {last_error}. Try to avoid the error in the current Output.\n\n'
        else:
            last_error_if_exist = ''
        
        prompt = PromptGenerator.PROMPTS['OpDistanceAgentV2']['Estimate']
        prompt = prompt.format(
            role=PromptGenerator.ROLE['OpDistanceAgentV2']['Estimate'].strip(),
            system_msg=PromptGenerator.SYSMSG['OpDistanceAgentV2']['Estimate'].strip(),
            demo=PromptGenerator.DEMO['OpDistanceAgentV2']['Estimate'].strip(),
            inp_tbls=inp_tbls.strip(),
            his_ops_and_obs=his_ops_and_obs.strip(),
            generated_table=generated_table_str.strip(),
            target_table=target_table_str.strip(),
            difference=difference.strip(),
            last_error_if_exist=last_error_if_exist.strip(),
        )
        return prompt