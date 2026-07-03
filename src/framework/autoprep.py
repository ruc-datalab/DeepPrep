import os

from src.tools.helper import Config
from src.agent import *
from src.agent.autoprep import DataCleaning, ColumnTransformation, TableTransformation, CodeGenerationLogicalOperator, TerminateLogicalOperator
from src.data import Task, Trial, DataPool
from src.tools.helper import Logger, GPT
from src.module.evaluator import Evaluator
from src.tools.utils import save_pickle, get_benchmark_from_task_id
from src.physicalop import *
from src.tools.utils import df_to_cotable

class AutoPrep:
    def __init__(self, cfg=None, log_file='_MAIN'):
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.log_file = log_file

        self.llm = GPT(self.cfg)
        self.evaluator = Evaluator(self.cfg)
        self.logger = Logger(name = 'AutoPrep1.0', cfg=self.cfg, log_file=log_file)
        self.log_file = log_file
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.agents_registry = {
            'DataCleaning': {
                'description': 'This logical operator will be used to guide the data cleaning operations on the input tables.',
                'signature': 'DataCleaning(input_tables=["table_name"], requirement="requirement_description")',
                'operators': DATA_CLEANING_OPS
            },
            'ColumnTransformation': {
                'description': 'This logical operator will be used to guide the column transformation operations on the input tables.',
                'signature': 'ColumnTransformation(input_tables=["table_name"], requirement="requirement_description")',
                'operators': COLUMN_TRANSFORMATION_OPS
            },
            'TableTransformation': {
                'description': 'This logical operator will be used to guide the table transformation operations on the input tables.',
                'signature': 'TableTransformation(input_tables=["table_name"], requirement="requirement_description")',
                'operators': TABLE_TRANSFORMATION_OPS
            },
            'CodeGenerationLogicalOperator': {
                'description': 'If other logical operators cannot solve the problem, you can use this logical operator to generate a new table using a function that processes input tables.',
                'signature': 'CodeGenerationLogicalOperator(input_tables=["table_name"], requirement="requirement_description")',
                'operators': [CodeGeneration]
            },
            'TerminateLogicalOperator': {
                'description': 'This logical operator will be used to terminate the process and specify the final output tables.',
                'signature': 'TerminateLogicalOperator(input_tables=["table_name"], requirement="requirement_description")',
                'operators': [Terminate]
            },
        }
        self.planner_agent = PlannerAgent(name='Planner Agent', cfg=self.cfg, log_file=self.log_file, planner_resgistry=self.agents_registry)
        self.programer_data_cleaning_agent = ProgrammerAgent(name='Data Cleaning Programmer', cfg=self.cfg, 
                                                            log_file=self.log_file, programmer_resgistry=self.agents_registry['DataCleaning'])
        self.programer_column_transformation_agent = ProgrammerAgent(name='Column Transformation Programmer', 
                                                            cfg=self.cfg, log_file=self.log_file, programmer_resgistry=self.agents_registry['ColumnTransformation'])
        self.programer_table_transformation_agent = ProgrammerAgent(name='Table Transformation Programmer',  
                                                            cfg=self.cfg, log_file=self.log_file, programmer_resgistry=self.agents_registry['TableTransformation'])
        self.programer_code_generation_agent = ProgrammerAgent(name='Code Generation Programmer',  
                                                            cfg=self.cfg, log_file=self.log_file, programmer_resgistry=self.agents_registry['CodeGenerationLogicalOperator'])

        self.MAX_LOGICAL_OPERATOR_CNT = 10

    def assign_related_programmer_agent(self, logical_operator):
        if isinstance(logical_operator, DataCleaning): return self.programer_data_cleaning_agent
        elif isinstance(logical_operator, ColumnTransformation): return self.programer_column_transformation_agent
        elif isinstance(logical_operator, TableTransformation): return self.programer_table_transformation_agent
        elif isinstance(logical_operator, CodeGenerationLogicalOperator): return self.programer_code_generation_agent
        else: raise Exception(f'Invalid logical operator: {logical_operator}')

    def serialize_generated_tbl(self, generated_tbl):
        out_eles = ['Here are the generated tables of current logical operator:']
        for tbl_name, df in generated_tbl.items():
            out_eles.append(f'Table name: {tbl_name}')
            out_eles.append(df_to_cotable(df))
            out_eles.append('')
        return '\n'.join(out_eles)

    def run(self, task: Task):
        benchmark = get_benchmark_from_task_id(task.id)
        if task.split in DataPool.ground_truth[benchmark] and task.id in DataPool.ground_truth[benchmark][task.split]:
            ground_truth_str = "\n".join([str(op) for op in DataPool.ground_truth[benchmark][task.split][task.id]])
            self.logger.log(f'Current processing task: {task.id}. With ground truth to be:\n\n{ground_truth_str}')
        else:
            self.logger.log(f'Current processing task: {task.id}. No ground truth.')
        trial = self._initialize_trial(task)
        self.trial = trial

        logical_ops, physical_ops = [], []
        generated_tbl = None
        planner_messages = self.planner_agent.initialize_message(self.trial)
        MAX_STEP = 24
        for _ in range(MAX_STEP):
            if len(logical_ops) >= self.MAX_LOGICAL_OPERATOR_CNT: break
            
            planner_out, programmer_out = None, None
            try:
                planner_out, logical_op = self.planner_agent.step(self.trial, planner_messages)
                if isinstance(logical_op, TerminateLogicalOperator): 
                    logical_ops.append(logical_op)
                    break
                programmer_agent = self.assign_related_programmer_agent(logical_op)
                programmer_out, physical_op_objs, generated_tbl, tmp_trial = programmer_agent.step(self.trial, logical_op)
            except Exception as e:
                if planner_out is not None: planner_messages.append({"role": "assistant", "content": f"In this round, the planner agent output is: {planner_out}"})
                if programmer_out is not None: planner_messages.append({"role": "assistant", "content": f"In this round, the programmer agent output is: {programmer_out}"})
                planner_messages.append({"role": "user", "content": f"In this round, Error Raised: {e} Please retry to avoid the error."})
                continue

            self.trial = tmp_trial
            # update planner_messages
            planner_messages.append({"role": "assistant", "content": planner_out})
            planner_messages.append({"role": "user", "content": f'<observation> {self.serialize_generated_tbl(generated_tbl)} </observation>'})

            logical_ops.append(logical_op)
            physical_ops.extend(physical_op_objs)

        if len(logical_ops) > 0 and isinstance(logical_ops[-1], TerminateLogicalOperator):
            self.trial.set_generated_tables(logical_ops[-1].input_tables)
        elif generated_tbl is not None:
            self.trial.set_generated_tables(list(generated_tbl.keys()))
            physical_ops.extend([Terminate(result=list(generated_tbl.keys()))])

        # Evaluate the trial
        matched, message = self.evaluator.evaluate_trial_tables(self.trial)
        if matched:
            self.logger.log(f'Trial {self.trial.exp_id} matched.')
            self.trial.matched = True
        else:
            self.logger.log(f'Trial {self.trial.exp_id} did not match.')
            self.trial.matched = False

        save_pickle(self.trial, os.path.join(self.cfg.get('filecachedir'), f"versions", self.cfg.get_version(), 'saved_trials', f"{self.trial.task.id}.pkl"))
        
        return self.trial

    def _initialize_trial(self, task: Task) -> Trial:
        exp_id = f'{task.id}_TRIAL_ID'
        trial = Trial(exp_id=exp_id, task=task)
        self.trial = trial
        trial.load(task)
        return trial