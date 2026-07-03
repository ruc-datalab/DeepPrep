import uuid, copy, re, random

from .base_agent import BaseAgent
from src.data import Task, Trial
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import parse_any_string
from src.tools.helper import GPTPOOL
from src.physicalop import *

class SQL2OpAgent(BaseAgent):
    def __init__(self, name: str='SQL2Op Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.name = name
        self.llm = GPTPOOL(self.cfg)
        self.MAX_ERR_CNT = 5

    def step(self, trial: Trial):
        self._clear_state()
        while True:
            try:
                return self._step(trial)
            except Exception as e:
                self._raise_error(e)

    def _step(self, trial: Trial):
        output = self._generate(trial)
        code_str = self._parse_output(output)
        op_chain = self._get_op_chain_from_code(code_str)
        from src.module.executor import Executor
        from src.physicalop import Terminate
        executor = Executor(cfg=self.cfg)
        for op in op_chain:
            out_tblname, df = executor.execute_op(op, trial, mode='rule')
            trial.tables[out_tblname] = df
        if op_chain and isinstance(op_chain[-1], Terminate):
            target_name = op_chain[-1].result[0]
            trial.tables['target_df'] = trial.tables[target_name]
        else:
            trial.tables['target_df'] = df  # Assume last df is target
        trial.set_generated_tables(['target_df'])
        trial.record('op_chain', op_chain)
        return trial

    def _generate(self, trial: Trial) -> str:
        prompt = PromptGenerator.sql2op_generate(cfg=self.cfg, trial=trial, last_error=self.last_log)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        return out

    def _parse_output(self, output: str) -> str:
        code_str = parse_any_string(output, code_type='python')
        return code_str

    def _get_op_chain_from_code(self, code_str: str):
        import pandas as pd
        import numpy as np
        from src.physicalop import TOTAL_OPS
        exec_env = {
            'pd': pd,
            'np': np,
            're': re,
            'random': random,
        }
        for op_class in TOTAL_OPS:
            exec_env[op_class.__name__] = op_class
        try:
            exec(code_str, exec_env)
            op_chain = exec_env.get('op_chain', None)
            if op_chain is None:
                raise Exception("No 'op_chain' found in the generated code. Please assign the list to 'op_chain'")
            return op_chain
        except Exception as e:
            raise Exception(f"Error executing code: {e}")