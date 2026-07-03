import uuid, copy, re, random
import pandas as pd
from io import StringIO
import contextlib

from .base_agent import BaseAgent
from src.data import Task, Trial
from src.tools.utils import parse_any_string, parse_tag_wrapped_string, df_to_cotable
from src.tools.helper import GPT
from src.physicalop import *

SYSTEM_MESSAGE = """
# Role Definition

You are a Code Agent to generate python code to transform the input tables into the target tables.

# Task Description

- You are allowed to use two tags to generate code to complete the task in multiple turns. 
- In each turn, you can use:
    - <think> your_think_here </think>: This tag is used for analyzing what action should be taken next based on the current status and historical information.
    - <python> your_python_code_here </python>: This tag is used to output the python code you generated in the current turn. When generating the python code, you should follow the following rules:
        - The input tables will be provided in the dict object `input_tables`. You can access each table by the key (which is the name of the table) in the dict. For example, you can access the table `table_1` by `input_tables['table_1']`.
        - Your generated target table should be assigned to a pd.DataFrame object named `target_df`.
    - <end> END </end>: If the task can be completed by the code, append this tag after </python> tag.
- After generating the python code in each turn, an external executor will execute the code and display the target table `target_df`.

CRITICAL REQUIREMENTS:
1. The output table MUST match EXACTLY the schema described in "Target Table Schema Description".
2. Column names MUST be identical (case-sensitive) to the target schema.
3. Do NOT add extra columns. Do NOT omit any required columns.
4. Data types and formats MUST match the target schema.
5. Before finishing, VERIFY your result matches the target schema exactly.
""".strip()

USER_MESSAGE = """
# Input Tables

{input_table}

# Target Table Schema Description

{target_table_schema}

# Output
""".strip()

class CodeAgent(BaseAgent):
    def __init__(self, name: str='Code Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.name = name
        self.llm = GPT(self.cfg)
        self.MAX_TURN = 5

    def step(self, trial: Trial, log_line = -1):
        self._clear_state()
        messages = self._initial_messages(trial, log_line)
        cur_turn = 0
        generated_tbl = None
        for i in range(self.MAX_TURN):
            cur_turn = i + 1
            df, messages, done = self._step(trial, cur_turn, messages)
            if done: 
                if df is not None:
                    generated_tbl = df
                break
            else:
                generated_tbl = df
        
        trial.tables['target_df'] = generated_tbl
        trial.set_generated_tables(['target_df'])

        return cur_turn, generated_tbl, messages

    def _step(self, trial: Trial, cur_turn: int, messages: list) -> tuple[pd.DataFrame, list, bool]:
        messages.append({"role": "user", "content": f"Generate your output for turn {cur_turn}:"})

        self.logger.log_messages(messages)
        out, think_content = self.llm.query(messages, get_thinking=True)
        self.logger.log_with_think_content(think_content, out)
        
        full_response = f"<think> {think_content} </think>\n{out}"
        messages.append({"role": "assistant", "content": full_response})

        # check if the task is done
        if '<end>' in out and '</end>' in out:
            done = True
            out = out.split('<end>')[0]
        else:
            done = False

        try:
            python_code = parse_tag_wrapped_string(out, tag='python', hard_replace=['your_python_code_here'])
            
            if python_code:
                target_df, captured_output, exec_success = self._execute_code(trial, python_code)
                
                if exec_success:
                    observation = f"<observation>\nCode executed successfully.\nExecution Output:\n{captured_output}\n</observation>"
                    messages.append({"role": "user", "content": observation})
                    return target_df, messages, done
                else:
                    error_msg = captured_output if captured_output else "Unknown execution error"
                    observation = f"<observation>\nCode execution failed.\n\nError:\n{error_msg}\n\nPlease fix the error and try again.\n</observation>"
                    messages.append({"role": "user", "content": observation})
                    return None, messages, done
            else:
                observation = f"<observation>\nNo Python code found in your response. Please provide code within <python> ... </python> tags.\n</observation>"
                messages.append({"role": "user", "content": observation})
                return None, messages, done
                
        except Exception as e:
            observation = f"<observation>\nError parsing or executing code: {str(e)}\n\nPlease check your code format and try again.\n</observation>"
            messages.append({"role": "user", "content": observation})
            return None, messages, done

    def _initial_messages(self, trial: Trial, log_line) -> list:
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(task=trial.task)
        system_message = SYSTEM_MESSAGE
        if log_line != -1:
            system_message += f"\nFOLLOW THIS!!!: When generating python code, print the intermediate results **EVERY {log_line} LINES**."
            system_message += f"\nFOLLOW THIS!!!: When generating python code, print the intermediate results **EVERY {log_line} LINES**."
            system_message += f"\nFOLLOW THIS!!!: When generating python code, print the intermediate results **EVERY {log_line} LINES**."
        user_message = USER_MESSAGE.format(input_table=inp_tbls, target_table_schema=tgt_tbl_schema_description)
        messages = []
        messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})
        return messages
        
    def _execute_code(self, trial: Trial, code_str: str) -> tuple[pd.DataFrame, str, bool]:
        """
        执行代码并返回结果
        
        Returns:
            tuple: (target_df, captured_output, success)
        """
        input_tables = copy.deepcopy(trial.tables) 
        
        exec_env = {
            'input_tables': input_tables,
            'pd': pd,
            'numpy': __import__('numpy'),
            'np': __import__('numpy'),
        }
        
        output = StringIO()
        success = False
        target_df = None
        
        try:
            with contextlib.redirect_stdout(output):
                exec(code_str, exec_env)
                
                target_df = exec_env.get('target_df', None)
                
                if target_df is not None:
                    success = True
                else:
                    output.write("\nError: No 'target_df' variable found after code execution.")
                    
        except SyntaxError as e:
            output.write(f"SyntaxError: {str(e)}")
            if hasattr(e, 'lineno') and hasattr(e, 'text'):
                output.write(f"\nLine {e.lineno}: {e.text}")
                output.write(f"\nError at position {e.offset}")
        except Exception as e:
            output.write(f"Runtime Error: {str(e)}")
            import traceback
            output.write(f"\nTraceback:\n{traceback.format_exc()}")
        
        captured_output = output.getvalue()
        return target_df, captured_output, success

    def _clear_state(self):
        pass