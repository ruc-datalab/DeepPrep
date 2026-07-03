import os
import json
import pandas as pd
from typing import List, Union
from src.physicalop import BaseOp
from .task import Task
from src.tools.utils import open_json, all_filepaths_in_dir, df_to_cotable, load_jsonl, get_benchmark_from_task_id
from src.tools.helper import Config
from src.physicalop import *
import uuid
import copy
from app.client import ApiClient

def construct_operator(op_dict):
    """
    Constructs a physical operator object from its dictionary representation.
    """
    op_name = op_dict.get('op')
    params = op_dict.get('params', {})
    op_tables = op_dict.get('op_tables', [])
    table_indices = op_dict.get('table_indices', [])

    def get_table(index=0):
        # Helper to get the table name safely based on table_indices
        if table_indices and len(op_tables) > table_indices[index]:
            return op_tables[table_indices[index]]
        # Fallback for simpler cases
        if len(op_tables) > index:
            return op_tables[index]
        return None

    op_map = {
        'cast': lambda: CastType(
            table_name=get_table(0),
            column=str(params.get('column')),
            dtype=params.get('dtype')
        ),
        'pivot': lambda: Pivot(
            table_name=get_table(0),
            index=str(params.get('index')),
            columns=str(params.get('columns')),
            values=str(params.get('values')),
            aggfunc=str(params.get('aggfunc'))
        ),
        'sort': lambda: Sort(
            table_name=get_table(0),
            by=[str(x) for x in params.get('by')],
            ascending=params.get('ascending')
        ),
        'dropna': lambda: DropNulls(
            table_name=get_table(0),
            subset=[str(s) for s in params.get('subset')] if isinstance(params.get('subset'), list) else params.get('subset'),
            how=params.get('how')
        ),
        'union': lambda: Union(
            table_names=op_tables,
            how=params.get('how')
        ),
        'filter': lambda: Filter(
            table_name=get_table(0),
            condition=params.get('condition')
        ),
        'transpose': lambda: Transpose(
            table_name=get_table(0)
        ),
        'rename': lambda: Rename(
            table_name=get_table(0),
            rename_map=[{'old_name': str(k), 'new_name': str(v)} for k, v in params.get('rename_map').items()]
        ),
        'join': lambda: Join(
            left_table=get_table(0),
            right_table=get_table(1),
            left_on=str(params.get('left_on')),
            right_on=str(params.get('right_on')),
            how=params.get('how'),
            suffixes=params.get('suffixes')
        ),
        'select': lambda: SelectCol(
            table_name=get_table(0),
            columns=[str(c) for c in params.get('columns')]
        ),
        'unpivot': lambda: Stack(
            table_name=get_table(0),
            id_vars=[str(x) for x in params.get('id_vars')],
            value_vars=[str(x) for x in params.get('value_vars')]
        ),
        'deduplicate': lambda: Deduplicate(
            table_name=get_table(0),
            subset=[str(s) for s in params.get('subset')] if isinstance(params.get('subset'), list) else params.get('subset'),
            keep=params.get('keep')
        ),
        'explode': lambda: Explode(
            table_name=get_table(0),
            column=str(params.get('column')),
            split_comma=params.get('split_comma', False)
        ),
        'groupby': lambda: GroupBy(
            table_name=get_table(0),
            by=[str(b) for b in params.get('by')],
            agg=[{'column': str(k), 'agg_func': v} for k, v in params.get('agg').items()]
        ),
        'topk': lambda: TopK(
            table_name=get_table(0),
            k=params.get('k')
        ),
        'wide_to_long': lambda: WideToLong(
            table_name=get_table(0),
            subnames=[str(s) for s in params.get('subnames')],
            i=[str(i) for i in params.get('i')],
            j=str(params.get('j')),
            sep=str(params.get('sep')),
            suffix=params.get('suffix')
        )
    }

    if op_name in op_map:
        return op_map[op_name]()
    else:
        print(f"Unknown operator type: {op_name}")
        return None

def load_tgt_tbl_schema_description(root_dir:str, total_benchmarks: List[str]) -> dict:
    def load_one_benchmark(benchmark_root:str):
        tgt_tbl_schema_description = {'test': {}, 'train': {}, 'dev': {}}
        for path in all_filepaths_in_dir(benchmark_root, endswith='.json'):
            if '_test_' in path: split = 'test'
            elif '_train_' in path: split = 'train'
            elif '_dev_' in path: split = 'dev'
            else:
                continue
            if split not in tgt_tbl_schema_description:
                tgt_tbl_schema_description[split] = {}
                
            tmp_obj = open_json(path)
            tgt_tbl_schema_description[split].update(tmp_obj)

        print(f"Loaded {sum([len(v) for v in tgt_tbl_schema_description.values()])} schema descriptions")
        return tgt_tbl_schema_description

    total_tgt_tbl_schema_description = {}
    for benchmark in total_benchmarks:
        total_tgt_tbl_schema_description[benchmark] = load_one_benchmark(os.path.join(root_dir, benchmark))
    return total_tgt_tbl_schema_description

def load_ground_truth(root_dir:str, total_benchmarks: List[str]) -> dict:
    def load_one_benchmark(benchmark_root:str):
        ground_truth = {}
        try:
            # <local_data_root>/PARROT
            max_op_len = 0
            for split in ['test', 'train', 'dev']:
                ground_truth[split] = {}
                path = os.path.join(benchmark_root, split, 'benchmark.jsonl')
                if not os.path.exists(path):
                    print(f"Warning: {path} not found")
                    continue
                for line in open(path):
                    tmp_obj = json.loads(line)
                    task_id = tmp_obj['task_id']

                    if 'tol_ops' not in tmp_obj:
                        if 'transform_chain_str' not in tmp_obj:
                            continue
                        # print(tmp_obj.keys())
                        transform_chain_str = tmp_obj['transform_chain_str']
                        op_dicts = json.loads(transform_chain_str)
                        operator_chain = op_dicts
                        
                    #     operator_chain = []
                    #     for op_dict in op_dicts:
                    #         operator = construct_operator(op_dict)
                    #         if operator:
                    #             operator_chain.append(operator)
                    #     if isinstance(operator_chain[-1], Terminate):
                    #         operator_chain.pop()
                    #     last_op = operator_chain[-1]
                        
                    #     if isinstance(last_op, Join):
                    #         tbl_name =  f'{last_op.left_table}_{last_op.right_table}_join'
                    #     elif isinstance(last_op, Union):
                    #         tbl_name = '_'.join(last_op.table_names) + '_union'
                    #     elif isinstance(last_op, Terminate):
                    #         tbl_name = last_op.result[0]
                    #     else:
                    #         tbl_name = last_op.table_name
                    #     operator_chain.append(Terminate(result=[tbl_name]))
                    else:
                        operator_chain = tmp_obj['tol_ops']

                    ground_truth[split][task_id] = operator_chain
                    max_op_len = max(max_op_len, len(operator_chain))
            print(f"Loaded {sum([len(v) for v in ground_truth.values()])} ground truth, max op len: {max_op_len}")
            return ground_truth, max_op_len
        except Exception as e:
            print(f"Error loading ground truth: {e}")
            return ground_truth, 0
    
    total_ground_truth = {}
    total_max_op_len = {}
    for benchmark in total_benchmarks:
        total_ground_truth[benchmark], total_max_op_len[benchmark] = load_one_benchmark(os.path.join(root_dir, benchmark))
    return total_ground_truth, total_max_op_len

def load_origin_case(root_dir:str, total_benchmarks: List[str]) -> dict:
    def load_one_benchmark(benchmark_root:str):
        origin_case = {}
        for split in ['test', 'train', 'dev']:
            origin_case[split] = {}
            path = os.path.join(benchmark_root, split, 'benchmark.jsonl')
            if not os.path.exists(path):
                print(f"Warning: {path} not found")
                continue
            for line in open(path):
                tmp_obj = json.loads(line)
                task_id = tmp_obj['task_id']
                origin_case[split][task_id] = tmp_obj
        print(f"Loaded {sum([len(v) for v in origin_case.values()])} origin case")
        return origin_case

    total_origin_case = {}
    for benchmark in total_benchmarks:
        total_origin_case[benchmark] = load_one_benchmark(os.path.join(root_dir, benchmark))
    return total_origin_case

def load_db2tblname2id(root_dir:str, total_benchmarks: List[str]) -> dict:
    def load_one_benchmark(benchmark_root:str):
        db2tblname2id = {}
        for split in ['test', 'train', 'dev']:
            path = os.path.join(benchmark_root, split, 'db_to_tblname_to_uuid.json')
            if os.path.exists(path):
                db2tblname2id[split] = open_json(path)
        id2db_and_tblname = {split: {} for split in db2tblname2id}
        for split, db2tblname2id_dict in db2tblname2id.items():
            for db_id, tblname2id_dict in db2tblname2id_dict.items():
                for tblname, id in tblname2id_dict.items():
                    id2db_and_tblname[split][id] = (db_id, tblname)
        return db2tblname2id, id2db_and_tblname

    total_db2tblname2id2uuid, total_id2db_and_tblname = {}, {}
    for benchmark in total_benchmarks:
        total_db2tblname2id2uuid[benchmark], total_id2db_and_tblname[benchmark] = load_one_benchmark(os.path.join(root_dir, benchmark))
    return total_db2tblname2id2uuid, total_id2db_and_tblname

class DataPool:
    tbl_schema_description = load_tgt_tbl_schema_description(
        root_dir=os.path.join(Config.load_base_config().get('filecachedir'), 'schema_description'),
        total_benchmarks=Config.load_base_config().get('total_benchmarks')
    )
    ground_truth, max_op_len = load_ground_truth(
        root_dir=os.path.join(Config.load_base_config().get('data_root')), 
        total_benchmarks=Config.load_base_config().get('total_benchmarks')
    )
    origin_case = load_origin_case(
        root_dir=os.path.join(Config.load_base_config().get('data_root')),
        total_benchmarks=Config.load_base_config().get('total_benchmarks')
    )
    db2tblname2id, id2db_and_tblname = load_db2tblname2id(
        root_dir=os.path.join(Config.load_base_config().get('data_root')),
        total_benchmarks=Config.load_base_config().get('total_benchmarks')
    )

    @staticmethod
    def get_sql(task_id:str, split:str='test'):
        benchmark = get_benchmark_from_task_id(task_id)

        origin_sql = DataPool.origin_case[benchmark][split][task_id]['sql']
        input_table_names = DataPool.origin_case[benchmark][split][task_id]['input_table']
        db_id = DataPool.origin_case[benchmark][split][task_id]['db_id']
        corresponding_tblnames = [DataPool.id2db_and_tblname[benchmark][split][tblid.replace('.csv', '')][1] for tblid in input_table_names]

        tblname2tblkey = {tblname: f'table_{i+1}' for i, tblname in enumerate(corresponding_tblnames)}
        for tblname, tblkey in tblname2tblkey.items():
            origin_sql = origin_sql.replace(tblname, tblkey)
        return origin_sql


    @staticmethod
    def load_trial(task_id:str, split:str='test', exp_id:str=None):
        if exp_id is None:
            exp_id = f'{task_id}_{uuid.uuid4()}'
        benchmark = get_benchmark_from_task_id(task_id)

        task = Task(id=task_id, inp_tbl_names=DataPool.origin_case[benchmark][split][task_id]['input_table'], tgt_tbl_name=DataPool.origin_case[benchmark][split][task_id]['target_table'], split=split)
        trial = Trial(exp_id=exp_id, task=task)
        trial.load(task)
        return trial

class Trial:

    @staticmethod
    def load_trial(task_id:str, split:str='test', exp_id:str=None):
        if exp_id is None:
            exp_id = f'{task_id}_{uuid.uuid4()}'
        benchmark = get_benchmark_from_task_id(task_id)
        assert task_id in DataPool.origin_case[benchmark][split], f"Task {task_id} not found in {split}"
        assert DataPool.origin_case[benchmark][split][task_id]['input_table'] is not None, f"Input table not found for task {task_id} in {split}"
        assert DataPool.origin_case[benchmark][split][task_id]['target_table'] is not None, f"Target table not found for task {task_id} in {split}"
        assert DataPool.tbl_schema_description[benchmark][split][task_id] is not None, f"Table schema description not found for task {task_id} in {split}"
        task = Task(id=task_id, 
                    inp_tbl_names=DataPool.origin_case[benchmark][split][task_id]['input_table'], 
                    tgt_tbl_name=DataPool.origin_case[benchmark][split][task_id]['target_table'], split=split, 
                    tgt_tbl_description=DataPool.tbl_schema_description[benchmark][split][task_id] if task_id in DataPool.tbl_schema_description[benchmark][split] else 'None')
        trial = Trial(exp_id=exp_id, task=task)
        trial.load(task)
        return trial
    
    @staticmethod
    def serialize_initial_table(task_id:str, split:str='test'):
        trial = Trial.load_trial(task_id, split)
        return trial.serialize_input_tables()
    

    def __init__(self, exp_id:str, task: Task, ops: List[BaseOp]=None, obs: List[str]=None, suggestion:str=None):
        self.exp_id = exp_id
        self.task = task
        self.ops = ops if ops else []
        self.obs = obs if obs else []
        self.suggestion = suggestion
        self.result = None
        self.eval_result = None
        self.tables = {}
        self.tgt_tbl = None
        self.generated_tbls = {}
        self.recording = {}
        self.error_message = None
        self.matched = None

    def is_terminated(self):
        """Check if the trial has been terminated."""
        return any(isinstance(op, Terminate) for op in self.ops)

    def clear_ops(self):
        """Clear the operator history of the trial."""
        self.op_history = []

    def get_table_names(self):
        return list(self.tables.keys())

    def get_table(self, table_name):
        return self.tables.get(table_name)

    def record(self, key: str, value: str):
        if key not in self.recording:
            self.recording[key] = []
        self.recording[key].append(value)

    def record_pop(self, key: str):
        # pop the last value of the key
        if key not in self.recording:
            raise Exception(f'Key {key} not found in recording!')
        return self.recording[key].pop()

    @staticmethod
    def generate_schema_description(task:Task):
        benchmark = get_benchmark_from_task_id(task.id)
        if task.split not in DataPool.tbl_schema_description[benchmark] or task.id not in DataPool.tbl_schema_description[benchmark][task.split]:
            return 'None'

        json_data = DataPool.tbl_schema_description[benchmark][task.split][task.id]
        eles = [f"We transform the input tables to complete the task: {json_data['Task Description']}"]
        eles.append('The column schema of the target table is as follows:')
        for col in json_data['Column Schema']:
            eles.append(f'- Name of Column: "{col}"')
            eles.append(f'  - Description: {json_data["Column Schema"][col]["description"]}')
            if 'requirements' in json_data["Column Schema"][col] and len(json_data["Column Schema"][col]['requirements']) > 0:
                eles.append(f'  - Requirements')
                for req in json_data["Column Schema"][col]['requirements']:
                    eles.append(f'    - {req}')
        return '\n'.join(eles)

    def set_generated_tables(self, table_names: List[str]):
        if len(table_names) == 0:
            self.generated_tbls = self.tables
        else:
            self.generated_tbls = {name: self.tables[name] for name in table_names}
    
    def load(self, task:Task):
        tables = {}
        tgt_tbl = None
        benchmark = get_benchmark_from_task_id(task.id)
        # when loading dataframe, set the value <NA> to None
        data_root = Config.load_base_config().get('data_root')
        if task.inp_tbl_names is not None:
            for i, table_name in enumerate(task.inp_tbl_names):
                table_path = os.path.join(data_root, benchmark, task.split, table_name)
                if table_path.endswith('.csv'):
                    tables[f'table_{i+1}'] = pd.read_csv(table_path, na_values=['<NA>', 'NA', 'nan', 'NaN', 'N/A', 'n/a', 'null', 'None', 'none'])
                elif table_path.endswith('.parquet'):
                    tables[f'table_{i+1}'] = pd.read_parquet(table_path)
                elif table_path.endswith('.pkl'):
                    tables[f'table_{i+1}'] = pd.read_pickle(table_path)
        if task.tgt_tbl_name is not None:
            tgt_tbl_path = os.path.join(data_root, benchmark, task.split, task.tgt_tbl_name)
            if tgt_tbl_path.endswith('.csv'):
                tgt_tbl = pd.read_csv(tgt_tbl_path, na_values=['<NA>', 'NA', 'nan', 'NaN', 'N/A', 'n/a', 'null', 'None', 'none'])
            elif tgt_tbl_path.endswith('.parquet'):
                tgt_tbl = pd.read_parquet(tgt_tbl_path)
            elif tgt_tbl_path.endswith('.pkl'):
                tgt_tbl = pd.read_pickle(tgt_tbl_path)

        if task.tgt_tbl_description is not None:
            try:
                task.tgt_tbl_description = DataPool.tbl_schema_description[benchmark][task.split][task.id]
                self.task = task
            except Exception as e:
                print(f"Error loading target table description: {e}")
                task.tgt_tbl_description = None

        self.tables = tables
        self.tgt_tbl = tgt_tbl
        
    def serialize_input_tables(self, cut_line: int=10, cut_col: int=20):
        eles = []
        for i, (table_name, table) in enumerate(self.tables.items()):
            eles.append(f'Name: "{table_name}"')
            eles.append(df_to_cotable(table, cut_line=cut_line, cut_col=cut_col))
            eles.append('\n------------------\n')
        return '\n'.join(eles)

    def add_op(self, action: BaseOp, ob: str):
        self.ops.append(action)
        self.obs.append(ob)
    
    def seralize_ops_and_observations(self):
        eles = []
        for i, (op, ob) in enumerate(zip(self.ops, self.obs)):
            eles.append(f'** Op {i+1} **: {op}')
            eles.append(f'** Output {i+1} **: {ob}')
            eles.append('---')
        
        return '\n'.join(eles)

    def clear_ops(self):
        self.ops = []
        self.obs = []

    def get_ops(self) -> List[BaseOp]:
        return self.ops
    
    def print_ops(self):
        for action in self.ops:
            print(action)
        print('------------------')