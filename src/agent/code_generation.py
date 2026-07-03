import uuid, copy, re, random

from .base_agent import BaseAgent
from src.data import Task, Trial
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import parse_any_string
from src.tools.helper import GPTPOOL
from src.physicalop import *

class InverseWideToLong(BaseOp):
    def __init__(self, index: list[str], column: str, values: list[str]):
        self.index = index
        self.column = column
        self.values = values

class CodeGen(BaseAgent):
    def __init__(self, name: str='Code Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.name = name
        self.llm = GPTPOOL(self.cfg)
        self.MAX_ERR_CNT = 1

    def generate_inverse_operation(self, df: pd.DataFrame, op: BaseOp):
        self._clear_state()
        self.MAX_ERR_CNT = 2
        while True:
            try:
                prompt = PromptGenerator.code_agent_generate_inverse_op(cfg=self.cfg, df=df, op=op, last_error=self.last_log)
                self.logger.log(prompt)
                out = self.llm.query(prompt)
                self.logger.log(out)
                code_str = parse_any_string(out, code_type='python')
                if isinstance(op, WideToLong):
                    new_df = self._execute_inverse_wide_to_long_code(df, code_str)
                else:
                    new_df = self._execute_inverse_code(df, code_str)
                self.logger.log(f"After executing the inverse code, we get the new df:\n{new_df}")
                return out, new_df
            except Exception as e:
                self._raise_error(e)
    
    def _execute_inverse_wide_to_long_code(self, df: pd.DataFrame, code_str: str):
        if 'InverseWideToLong' not in code_str:
            raise Exception("The generated code is not using InverseWideToLong operator.")
        
        cls = eval(code_str.strip())
        index = cls.index
        column = cls.column
        values = cls.values
        wide_df = df.pivot(index=index, columns=column, values=values)
        if not isinstance(values, list):
            raise Exception("The `values` argument of InverseWideToLong operator should be a list.")
        # rename the column
        wide_df.columns = [f'{metric}_{year}' for metric, year in wide_df.columns]
        wide_df = wide_df.reset_index()
        return wide_df
    
    def _execute_inverse_code(self, df: pd.DataFrame, code_str: str):
        input_table = copy.deepcopy(df) # this is the input object in code_str
    
        import pandas as pd
        import numpy as np
        # Create execution environment with input tables
        exec_env = {
            'pd': pd,
            'np': np,
            'input_table': input_table,
            're': re,
            'random': random,
        }
        
        try:
            # Execute the generated code
            exec(code_str, exec_env)
            target_df = exec_env.get('target_df', None)
            # If no common names found, look for DataFrame variables that weren't in input
            if target_df is None:
                raise Exception("No output DataFrame found in your generated code. Please assign result to 'target_df'")
            return target_df
        except Exception as e:
            raise Exception(f"Error executing code: {e}")


    def code_gen(self, trial: Trial):
        self._clear_state()
        self.MAX_ERR_CNT = 1
        while True:
            try:
                return self._code_gen(trial)
            except Exception as e:
                self._raise_error(e)

    def _code_gen(self, trial: Trial):
        output = self._generate(trial)
        code_str = self._parse_output(output)
        target_df = self._execute_code(trial, code_str)
        trial.tables['target_df'] = target_df
        trial.set_generated_tables(['target_df'])
        trial.record('code', code_str)
        return trial

    def _generate(self, trial: Trial) -> str:
        prompt = PromptGenerator.code_agent_generate(cfg=self.cfg, trial=trial, last_error=self.last_log)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        return out

    def _parse_output(self, output: str) -> str:
        code_str = parse_any_string(output, code_type='python')
        return code_str

    def implement_and_execute_logical_operator(self, trial: Trial, op: BaseOp):
        self._clear_state()
        while True:
            try:
                return self._implement_and_execute_logical_operator(trial, op)
            except Exception as e:
                self._raise_error(e)

    def _implement_and_execute_logical_operator(self, trial: Trial, op: BaseOp):
        #? Step 1: Prompt LLM to generate code
        prompt = PromptGenerator.code_agent_implement_logical_operator(cfg=self.cfg, trial=trial, last_error=self.last_log, op=op)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        #? Step 2: Extract code from output
        code_str = parse_any_string(out, code_type='python')
        #? Step 3: Execute code
        target_df = self._execute_code(trial, code_str)
        return target_df
    
    def _execute_code(self, trial: Trial, code_str: str):
        input_tables = copy.deepcopy(trial.tables) # this is the input object in code_str

        import pandas as pd
        # Create execution environment with input tables
        exec_env = {
            'input_tables': input_tables,
            'pd': pd,
        }
        
        try:
            # Execute the generated code
            exec(code_str, exec_env)
            target_df = exec_env.get('target_df', None)
            # If no common names found, look for DataFrame variables that weren't in input
            if target_df is None:
                raise Exception("No output DataFrame found in your generated code. Please assign result to 'target_df'")
            return target_df
        except Exception as e:
            raise Exception(f"Error executing code: {e}")