import uuid, os
import httpx
import random
import time

from src.tools.helper import Config
from src.agent import *
from src.data import Task, Trial, DataPool
from src.tools.helper import Logger
from src.module import Evaluator
from src.tools.utils import save_pickle, load_pickle, df_to_cotable, get_benchmark_from_task_id
from src.physicalop import *
from app.client import ApiClient
import copy
from src.module.executor import RuleExecutor
from src.prompt.prompt_generator import PromptGenerator

class GenerateInverseOperation:
    def __init__(self, cfg=None, log_file='_MAIN', op_select='random'):
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.code_agent = CodeGeneration(cfg=self.cfg, log_file=log_file)
        self.react_agent = ReactAgent(cfg=self.cfg, log_file=log_file)
        self.rule_exer = RuleExecutor(cfg=self.cfg, log_file=log_file)
        self.evaluator = Evaluator(cfg=self.cfg, log_file=log_file)
        self.logger = Logger(name = 'Generate Inverse Operation', cfg=self.cfg, log_file=log_file)
        self.op_select = op_select
        self.MAX_CLEAN_OP = 6

    def generate_one_inverseop_and_op(self, input_table:pd.DataFrame, op:BaseOp):
        df = copy.deepcopy(input_table)
        if op.__name__ == 'Transpose':
            df = self.rule_exer.execute_op_on_df(Transpose(table_name='test_table'), df)
            code = """df = input_table.copy()
if df.empty or len(df.columns) == 0:
    target_df = df.transpose()
else:
    df_t = df.transpose()
    new_columns = df_t.iloc[0].tolist()
    
    df_t = df_t.iloc[1:]
    first_col_name = df.columns[0]
    df_t.insert(0, first_col_name, df_t.index)
    df_t.columns = [first_col_name] + new_columns
    target_df = df_t.reset_index(drop=True)"""
            return code, df, "The Dirty Table can be get by transpose the Target Table."
        
        try:
            code, dirty_table = self.code_agent.generate_inverse_operation(df=df, op=op)
            matched, message = self.evaluator.validate(table_a=df, table_b=dirty_table, table_a_name='Target Table', table_b_name='Dirty Table', type_match=True)
            self.logger.log(f"The Input Table and Generated Dirty Table are matched or not? {matched}, the message is: {message}")
            if not matched:
                return code, dirty_table, message
            else:
                return None, None, None
        except Exception as e:
            return None, None, None
        
    def generate_dc_op(self, dirty_table: pd.DataFrame, target_table: pd.DataFrame, unmatched_message: str, op: BaseOp):
        MAX_RETRY = 3
        message = copy.deepcopy(unmatched_message)
        for _ in range(MAX_RETRY):
            try:
                dc_op = self.react_agent.generte_op_to_restore_table(dirty_table=dirty_table, target_table=target_table, message=message, op_class=op)
                if dc_op is None:
                    return None
            except Exception as e:
                self.logger.log(f"Error during generating dc op: {e}")
                message = f'The difference between the Input Dirty Table and Target Table is: {unmatched_message}. when generating the dc op, occurring errors: {e}.'
                continue
            
            try:
                generated_table = self.rule_exer.execute_op_on_df(dc_op, dirty_table)
                self.logger.log(f"After executing the dc op, we get the new df:\n{generated_table}")
                matched, match_message = self.evaluator.validate(table_a=generated_table, table_b=target_table, table_a_name='Generated Table', table_b_name='Target Table', type_match=True)
                self.logger.log(f"The Generated Table and Target Table are matched or not? {matched}, the message is: {match_message}")
            except Exception as e:
                self.logger.log(f"Error during executing operation {dc_op}: {e}")
                message = f'The operator {dc_op} is not supported to execute or validate on the dirty table! The error is: {e}'
                continue

            if matched:
                return dc_op
            else:
                message = f'After executing the dc operator {str(dc_op)}, we get the new table: {df_to_cotable(generated_table)}. However, the new table can not restore the dirty table to the clean input table. The difference between the input table and generated new table is: {unmatched_message}.'
                continue
        return None

    def select_one_op(self, df: pd.DataFrame, op_candidates: list[BaseOp], weights=None):
        if self.op_select == 'llm':
            try:
                return self.react_agent.select_inverse_op_for_table(df=df, candidate_dc_op=op_candidates)
            except Exception as e:
                self.logger.log(f'Error during selecting inverse operation: {e}')
                return None
        elif self.op_select == 'random':
            random.seed(time.time())
            if weights is None:
                return random.choice(op_candidates)
            else:
                return random.choices(op_candidates, weights=[weights[op] for op in op_candidates], k=1)[0]
        else:
            raise ValueError(f'Invalid op select method: {self.op_select}')
        
    def extract_all_related_columns_for_trial(self, trial: Trial):
        split = trial.task.split
        task_id = trial.task.id

        benchmark = get_benchmark_from_task_id(task_id)
        origin_sql = DataPool.origin_case[benchmark][split][task_id]['sql']
        input_table_names = DataPool.origin_case[benchmark][split][task_id]['input_table']
        db_id = DataPool.origin_case[benchmark][split][task_id]['db_id']
        corresponding_tblnames = [DataPool.id2db_and_tblname[benchmark][split][tblid.replace('.csv', '')][1] for tblid in input_table_names]

        tblname2tblkey = {tblname: f'table_{i+1}' for i, tblname in enumerate(corresponding_tblnames)}
        related_columns = {}
        for tblname, tblkey in tblname2tblkey.items():
            if tblname.lower() in origin_sql.lower():
                related_columns[tblkey] = []
                df = trial.tables[tblkey]
                for col in df.columns:
                    if col.lower() in origin_sql.lower():
                        related_columns[tblkey].append(col)

        for tblkey, df in trial.tables.items():
            if len(related_columns[tblkey]) > 0:
                trial.tables[tblkey] = trial.tables[tblkey][related_columns[tblkey]]

        return trial

    def run(self, task: Task, weights=None, min_op_cnt: int=1, max_op_cnt: int=6): 
        saved_pkl_fn = os.path.join(self.cfg.get('filecachedir'), f"versions", self.cfg.get_version(), 'saved_trials', f"{task.id}.pkl")
        if os.path.exists(saved_pkl_fn): return load_pickle(saved_pkl_fn)
        
        self.logger.log(f"Weights: {weights}")
        benchmark = get_benchmark_from_task_id(task.id)
        if task.split in DataPool.ground_truth[benchmark] and task.id in DataPool.ground_truth[benchmark][task.split]:
            ground_truth_str = "\n".join([str(op) for op in DataPool.ground_truth[benchmark][task.split][task.id]])
            self.logger.log(f'Current processing task: {task.id}. With ground truth to be:\n\n{ground_truth_str}')
        else:
            self.logger.log(f'Current processing task: {task.id}. No ground truth.')
        trial = Trial.load_trial(task_id=task.id, split=task.split)
        self.trial = trial
        trial.dirty_tables = {}
        dirty_table, inverse_op_codes, his_op_lis = None, None, None

        # trial = self.extract_all_related_columns_for_trial(trial)

        for tbl_name, tbl in trial.tables.items():
            if weights is None: op_candidates = copy.deepcopy(OP_REQUIRE_INVERSE_OP)
            else: op_candidates = copy.deepcopy(list(weights.keys()))

            input_table = copy.deepcopy(tbl)
            max_op_cnt = random.randint(min_op_cnt, max_op_cnt)
            self.logger.log(f"Hope to generate {max_op_cnt} operators to dirty the table.")
            his_op_lis, inverse_op_codes, table_b = [], [], None
            trial.dirty_tables[tbl_name] = {}
            try_cnt = 0

            while True:
                try_cnt += 1
                if try_cnt > 100: break
                if len(his_op_lis) >= max_op_cnt:
                    break

                # for op in op_candidates: 
                #     if op.__name__ in [x.__class__.__name__ for x in his_op_lis]: 
                #         op_candidates.remove(op)

                op = self.select_one_op(df=copy.deepcopy(input_table), op_candidates=op_candidates, weights=weights)
                if op is None:
                    break

                # generate codes to get a dirty table B, satisfy input_table != dirty_table
                code, dirty_table, message = self.generate_one_inverseop_and_op(input_table=copy.deepcopy(input_table), op=op)
                if code is None or dirty_table is None:
                    op_candidates.remove(op)
                    if len(op_candidates) == 0:
                        break
                    continue
                
                # generate a dc op to restore the dirty table B to the input table, satisfy input_table == generated_table
                dc_op = self.generate_dc_op(
                    dirty_table=copy.deepcopy(dirty_table), 
                    target_table=copy.deepcopy(input_table), 
                    unmatched_message=message, op=op)
                if dc_op is None:
                    op_candidates.remove(op)
                    if len(op_candidates) == 0:
                        break
                    continue

                # if successfully generated, table_b is dirty table and be the input of next round

                table_b = copy.deepcopy(dirty_table)
                his_op_lis.append(dc_op)
                inverse_op_codes.append(code)
                input_table = copy.deepcopy(dirty_table)
                op_candidates = copy.deepcopy(OP_REQUIRE_INVERSE_OP)
                for op in his_op_lis:
                    op_candidates.remove(op.__class__)

            trial.dirty_tables[tbl_name]['dirty_table'] = copy.deepcopy(table_b)
            trial.dirty_tables[tbl_name]['inverse_op_codes'] = inverse_op_codes
            trial.dirty_tables[tbl_name]['his_op_lis'] = his_op_lis
            
        save_pickle(self.trial, saved_pkl_fn)
        
        return self.trial