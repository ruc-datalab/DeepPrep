import json
import pandas as pd
import os
import ast
import re
from typing import Dict, List
import numpy as np
from src.physicalop import *
from src.physicalop.data_transform import (
    Filter, Sort, Pivot, Join, GroupBy, Rename, Stack, Explode, WideToLong,
    Union, Transpose, DropNulls, Deduplicate, TopK, SelectCol, CastType, Terminate,
    MissingValueImputation, OutlierDetection, StandardizeString, StandardizeDatetime,
    ErrorDetection, AddNewColumn, DropColumn, SplitColumn, Concatenate, Subtitle,
    Append, Count, CodeGeneration, CalculateStatistic
)
from src.physicalop.inverse_data_transform import (
    InversePivot, InverseStack, InverseExplode, InverseWideToLong, InverseTranspose, InverseDropNulls, InverseDeduplicate
)

from src.physicalop import get_generated_table_name

from src.data.trial import Trial, Task
from src.tools.helper import Config, Logger
from src.tools.utils import df_to_cotable, execute_code_from_string


class RuleExecutor:
    def __init__(self, cfg: Config, debug: bool = True, log_file='_MAIN'):
        self.cfg = cfg
        self.logger = Logger(name = '[MAS] Rule Executor', cfg=self.cfg, debug=debug, log_file=log_file)
        self.function_mapper = {
            Filter: self.execute_filter,
            Sort: self.execute_sort,
            Pivot: self.execute_pivot,
            Join: self.execute_join,
            GroupBy: self.execute_groupby,
            Rename: self.execute_rename,
            Stack: self.execute_stack,
            Explode: self.execute_explode,
            WideToLong: self.execute_wide_to_long,
            Union: self.execute_union,
            Transpose: self.execute_transpose,
            DropNulls: self.execute_drop_nulls,
            Deduplicate: self.execute_deduplicate,
            TopK: self.execute_topk,
            SelectCol: self.execute_select_col,
            CastType: self.execute_cast_type,
            Terminate: self.execute_terminate,
            
            MissingValueImputation: self.execute_missing_value_imputation, #? passed
            OutlierDetection: self.execute_outlier_detection, #? passed
            StandardizeString: self.execute_standardize_string, #? passed
            StandardizeDatetime: self.execute_standardize_datetime, #? passed
            ErrorDetection: self.execute_error_detection, #? passed
            AddNewColumn: self.execute_add_new_column, #? passed
            DropColumn: self.execute_drop_column, #? passed
            SplitColumn: self.execute_split_column, #? passed
            Concatenate: self.execute_concatenate, #? passed
            Subtitle: self.execute_subtitle, #? passed
            Append: self.execute_append, #? passed
            Count: self.execute_count, #? passed
            CodeGeneration: self.execute_code_generation, #? passed
            CalculateStatistic: self.execute_calculate_statistic,

            InversePivot: self.execute_inverse_pivot,
            InverseStack: self.execute_inverse_stack,
            InverseExplode: self.execute_inverse_explode,
            InverseWideToLong: self.execute_inverse_wide_to_long,
            InverseTranspose: self.execute_inverse_transpose,
            InverseDropNulls: self.execute_inverse_drop_nulls,
            InverseDeduplicate: self.execute_inverse_deduplicate,
        }

    def execute_missing_value_imputation(self, op: BaseOp, trial: Trial):
        if not isinstance(op, MissingValueImputation):
            raise ValueError(f"Expected MissingValueImputation operation, got {type(op).__name__}")
        table_name=op.table_name
        column_name=op.column_name
        mode=op.mode
        df=trial.tables[table_name].copy()
        if mode=="mean":
            df[column_name]=df[column_name].fillna(df[column_name].mean())
        elif mode=="median":
            df[column_name]=df[column_name].fillna(df[column_name].median())
        elif mode=="mode":
            df[column_name]=df[column_name].fillna(df[column_name].mode()[0])
        return df

    def execute_outlier_detection(self, op: BaseOp, trial: Trial):
        if not isinstance(op, OutlierDetection):
            raise ValueError(f"Expected OutlierDetection operation, got {type(op).__name__}")
        table_name=op.table_name
        column_name=op.column_name
        action=op.action
        # detect phrase: use IQR method to detect outliers
        df=trial.tables[table_name].copy()
        q1=df[column_name].quantile(0.25)
        q3=df[column_name].quantile(0.75)
        iqr=q3-q1
        lower_bound=q1-1.5*iqr
        upper_bound=q3+1.5*iqr

        df[f'{table_name}_{column_name}_is_outlier']=df[column_name].apply(lambda x: True if x<lower_bound or x>upper_bound else False)
        if action=="delete":
            df=df[df[f'{table_name}_{column_name}_is_outlier']==False]
            df.drop(columns=[f'{table_name}_{column_name}_is_outlier'], inplace=True)
        elif action=="add_tag":
            df[f'{table_name}_{column_name}_is_outlier']=df[f'{table_name}_{column_name}_is_outlier'].astype(bool)
        return df

    def execute_standardize_string(self, op: BaseOp, trial: Trial):
        if not isinstance(op, StandardizeString):
            raise ValueError(f"Expected StandardizeString operation, got {type(op).__name__}")
        table_name = op.table_name
        column_name = op.column_name
        func = op.func
        df = trial.tables[table_name].copy()
        try:
            # ---  Lambda  ---
            if func.strip().startswith('lambda'):
                lambda_f = eval(func, {'re': re, 'pd': pd, 'np': np})
                def apply_lambda(s):
                    if pd.isna(s): return s
                    try:
                        return lambda_f(s)
                    except Exception as e:
                        self.logger.log(f"Error applying lambda to value {s}: {e}")
                        return s
                df[column_name] = df[column_name].apply(apply_lambda)
                return df
            # -----------------

            from src.tools.utils.funcs import parse_function_string, execute_code_from_string
            # Parse the function string to get function name and arguments
            func_info = parse_function_string(func)
            if 'name' not in func_info or not func_info['name']:
                raise ValueError("Could not parse function definition from provided code")
            func_name = func_info['name']
            args = func_info['args']
            if len(args) != 1:
                raise ValueError(f"Expected function with 1 argument, got {len(args)}")
            arg_name = args[0]
            
            # self.logger.log(f"Function string to execute: \n{func}")
            # self.logger.log(f"Parsed function info: name={func_name}, args={arg_name}")
            
            # Apply the transformation to each value in the column
            def apply_transform(s):
                if pd.isna(s):
                    return s
                try:
                    exe_code = func + '\n\n' + f'my_final_trans_result = {func_name}({arg_name}=input_val)'
                    result = execute_code_from_string(code_string=exe_code, input_dict={'input_val': s, 're':re, 'pd':pd}, output_vals=['my_final_trans_result'])
                    if result and len(result) == 1:
                        return result[0]
                    else:
                        self.logger.log(f"No result returned for value {s}")
                        return s
                except Exception as e:
                    self.logger.log(f"Error applying transform to value {s}: {e}")
                    return s

            df[column_name] = df[column_name].apply(apply_transform)
        except Exception as e:
            self.logger.log(f"Error during string standardization: {e}")
            raise ValueError(f"Failed to standardize string in column {column_name}: {str(e)}")
        return df
    
    def execute_standardize_datetime(self, op: BaseOp, trial: Trial):
        if not isinstance(op, StandardizeDatetime):
            raise ValueError(f"Expected StandardizeDatetime operation, got {type(op).__name__}")
        table_name = op.table_name
        column_name = op.column_name
        date_format = op.date_format
        df = trial.tables[table_name].copy()
        try:
            from dateutil.parser import parse
            def try_parse_date(x):
                if pd.isna(x):
                    return pd.NaT
                try:
                    if isinstance(x, str):
                        return parse(x, fuzzy=True)
                    return pd.to_datetime(x, errors='coerce')
                except Exception:
                    return pd.NaT

            df[column_name] = df[column_name].apply(try_parse_date)
            if date_format:
                df[column_name] = df[column_name].dt.strftime(date_format)
        except Exception as e:
            self.logger.log(f"Error during datetime standardization: {e}")
            raise ValueError(f"Failed to standardize datetime in column {column_name}: {str(e)}")
        return df

    def execute_filter(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Filter):
            raise ValueError(f"Expected Filter operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        func_str = op.func

        if not func_str or not isinstance(func_str, str):
            raise ValueError(f"Filter function is empty or not a string: {func_str}")

        try:
            # ---  Lambda  ---
            if func_str.strip().startswith('lambda'):
                self.logger.log(f"Filter using lambda: {func_str}")
                lambda_f = eval(func_str, {'re': re, 'pd': pd, 'np': np})
                
                def apply_lambda_filter(row):
                    try:
                        return bool(lambda_f(row))
                    except Exception as e:
                        self.logger.log(f"Error applying lambda filter to row: {e}")
                        return False
                
                mask = df.apply(apply_lambda_filter, axis=1)
                df = df[mask]
                return df
            # -----------------------

            from src.tools.utils.funcs import parse_function_string, execute_code_from_string
            # Parse the function string to get function name and arguments
            func_info = parse_function_string(func_str)
            if 'name' not in func_info or not func_info['name']:
                raise ValueError("Could not parse function definition from provided code")
            func_name = func_info['name']
            args = func_info['args']
            if len(args) != 1:
                raise ValueError(f"Expected function with 1 argument (row), got {len(args)}")
            arg_name = args[0]
            
            self.logger.log(f"Filter function string: \n{func_str}")
            self.logger.log(f"Parsed function info: name={func_name}, args={arg_name}")
            
            # Apply the filter function to each row
            def apply_filter(row: pd.Series) -> bool:
                try:
                    exe_code = func_str + '\n\n' + f'my_filter_result = {func_name}({arg_name}=input_val)'
                    result = execute_code_from_string(code_string=exe_code, input_dict={'input_val': row}, output_vals=['my_filter_result'])
                    if result and len(result) == 1:
                        return bool(result[0])
                    else:
                        self.logger.log(f"No result returned for filter on row")
                        return False
                except Exception as e:
                    self.logger.log(f"Error applying filter to row: {e} when executing code: {exe_code}")
                    return False
            
            # Apply the filter and keep only rows where the function returns True
            mask = df.apply(apply_filter, axis=1)
            df = df[mask]
        except Exception as e:
            self.logger.log(f"Error during filter execution: {e}")
            raise ValueError(f"Failed to apply filter: {str(e)}")

        return df
    
    def execute_sort(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Sort):
            raise ValueError(f"Expected Sort operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        if len(op.ascending) != len(op.by):
            op.ascending = [True] * len(op.by)
        df = df.sort_values(by=op.by, ascending=op.ascending)

        return df
    
    def execute_pivot(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Pivot):
            raise ValueError(f"Expected Pivot operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        df = df.pivot_table(index=op.index, columns=op.columns, values=op.values, aggfunc=op.aggfunc).reset_index()
        # Pivot operation transforms a long DataFrame to a wide format by pivoting specified columns.
        # It aggregates data based on an index and creates new columns from unique values in another column.
        # Case Example:
        # Input DataFrame:
        #   ID  Category  Value
        #   1   A         10
        #   1   B         20
        #   2   A         30
        #   2   B         40
        # After Pivot with index='ID', columns='Category', values='Value', aggfunc='sum':
        #   ID  A   B
        #   1   10  20
        #   2   30  40
        return df
    
    def execute_join(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Join):
            raise ValueError(f"Expected Join operation, got {type(op).__name__}")

        left_df = trial.tables[op.left_table].copy()
        right_df = trial.tables[op.right_table].copy()

        left_dtype = left_df[op.left_on].dtype
        right_dtype = right_df[op.right_on].dtype
        if left_dtype != right_dtype:
            left_df[op.left_on] = left_df[op.left_on].astype(str)
            right_df[op.right_on] = right_df[op.right_on].astype(str)

        joined_df = pd.merge(left_df, right_df, left_on=op.left_on, right_on=op.right_on, how=op.how, suffixes=op.suffixes)
        return joined_df
    
    def execute_groupby(self, op: BaseOp, trial: Trial):
        if not isinstance(op, GroupBy):
            raise ValueError(f"Expected GroupBy operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        grouped = df.groupby(op.by, as_index=False)
        agg_ops = {item['column']: item['agg_func'] for item in op.agg}
        df = grouped.agg(agg_ops)

        return df
    
    def execute_rename(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Rename):
            raise ValueError(f"Expected Rename operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        rename_dict = {item['old_name']: item['new_name'] for item in op.rename_map}
        df = df.rename(columns=rename_dict)

        return df
    
    def execute_stack(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Stack):
            raise ValueError(f"Expected Stack operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        melted_df = df.melt(id_vars=op.id_vars, value_vars=op.value_vars, var_name=op.var_name, value_name=op.value_name)
        # drop the rows where the value is NaN
        melted_df = melted_df.dropna(subset=[op.value_name])
        # melted_df[op.value_name] = melted_df[op.value_name].astype("string")
        # Stack operation transforms a wide DataFrame to a long format by melting specified columns.
        # It unpivots the data, turning columns into rows, useful for normalizing data for analysis.
        # Case Example:
        # Input DataFrame:
        #   ID  A  B
        #   1   10 20
        #   2   30 40
        # After Stack with id_vars=['ID'], value_vars=['A', 'B'], var_name='Category', value_name='Value':
        #   ID  Category  Value
        #   1   A         10
        #   1   B         20
        #   2   A         30
        #   2   B         40
        return melted_df
    
    def execute_explode(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Explode):
            raise ValueError(f"Expected Explode operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        column = op.column
        split_comma = op.split_comma

        cols_to_process = [column] if not isinstance(column, list) else column

        for col in cols_to_process:
            if col not in df.columns:
                return df

        try:
            for col in cols_to_process:
                sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                
                if isinstance(sample, str) or (pd.isna(sample) and split_comma):
                    if split_comma:
                        df[col] = df[col].apply(
                            lambda x: [item.strip() for item in str(x).split(',')] if pd.notna(x) and x != '' else []
                        )
                    else:
                        def parse_string_value(x):
                            if pd.isna(x) or x == '': return []
                            try:
                                result = ast.literal_eval(str(x))
                                return result if isinstance(result, list) else [result]
                            except:
                                return [item.strip() for item in str(x).split()]
                        df[col] = df[col].apply(parse_string_value)
                
                elif not isinstance(sample, list) and sample is not None:
                    df[col] = df[col].apply(lambda x: [x] if pd.notna(x) else [])

            if len(cols_to_process) == 1:
                result_df = df.explode(cols_to_process[0]).reset_index(drop=True)
            else:
                result_df = df.explode(cols_to_process).reset_index(drop=True)

        except Exception as e:
            import traceback
            traceback.print_exc() 
            self.logger.log(f'Error during explode: {e}')
            result_df = df

        return result_df
    
    def execute_wide_to_long(self, op: BaseOp, trial: Trial):
        if not isinstance(op, WideToLong):
            raise ValueError(f"Expected WideToLong operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        long_df = pd.wide_to_long(df, stubnames=op.subnames, i=op.i, j=op.j, sep=op.sep, suffix=op.suffix).reset_index()
        for col in op.subnames:
            long_df[col] = long_df[col].astype("string")
        
        # drop rows where all values are NaN
        long_df = long_df.dropna(how='all', subset=op.subnames)
        
        return long_df
    
    def execute_union(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Union):
            raise ValueError(f"Expected Union operation, got {type(op).__name__}")

        dfs_to_union = [trial.tables[name].copy() for name in op.table_names]
        try:
            unioned_df = pd.concat(dfs_to_union, axis=0, ignore_index=True)
        except ValueError:
            target_type = dfs_to_union[0].dtypes.to_dict()
            for i in range(1, len(dfs_to_union)):
                dfs_to_union[i] = dfs_to_union[i].astype(target_type)
            unioned_df = pd.concat(dfs_to_union, axis=0, ignore_index=True)
            unioned_df.replace('nan', np.nan, inplace=True)

        if op.how == 'distinct':
            unioned_df = unioned_df.drop_duplicates()

        return unioned_df
    
    def execute_transpose(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Transpose):
            raise ValueError(f"Expected Transpose operation, got {type(op).__name__}")
        
        df = trial.tables[op.table_name].copy()
        if df.empty or len(df.columns) == 0:
            df = df.transpose()
        else:
            df_t = df.transpose()
            new_columns = df_t.iloc[0].tolist()
            
            df_t = df_t.iloc[1:]
            first_col_name = df.columns[0]
            df_t.insert(0, first_col_name, df_t.index)
            df_t.columns = [first_col_name] + new_columns
            df = df_t.reset_index(drop=True)

        return df

    def execute_drop_nulls(self, op: BaseOp, trial: Trial):
        if not isinstance(op, DropNulls):
            raise ValueError(f"Expected DropNulls operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        df = df.dropna(subset=op.subset, how=op.how).reset_index(drop=True)

        return df
    
    def execute_deduplicate(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Deduplicate):
            raise ValueError(f"Expected Deduplicate operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        df = df.drop_duplicates(subset=op.subset, keep=op.keep).reset_index(drop=True)

        return df
    
    def execute_topk(self, op: BaseOp, trial: Trial):
        if not isinstance(op, TopK):
            raise ValueError(f"Expected TopK operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        df = df.head(op.k)

        return df
    
    def execute_select_col(self, op: BaseOp, trial: Trial):
        if not isinstance(op, SelectCol):
            raise ValueError(f"Expected SelectCol operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        valid_cols = [c for c in op.columns if c in df.columns]
        df = df[valid_cols]

        return df
    
    def execute_cast_type(self, op: BaseOp, trial: Trial):
        if not isinstance(op, CastType):
            raise ValueError(f"Expected CastType operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        dtype = op.dtype
        if dtype.startswith("int") or dtype.startswith("float"):
            series = df[op.column].apply(lambda x: str(x).strip('"').strip("'"))
        else:
            series = df[op.column]

        try:
            if dtype == "datetime64":
                df[op.column] = pd.to_datetime(series, errors="coerce")
            elif dtype.startswith("int"):
                numeric = pd.to_numeric(series, errors="coerce").fillna(0)
                df[op.column] = numeric.astype(int)
            elif dtype.startswith("float"):
                numeric = pd.to_numeric(series, errors="coerce")
                df[op.column] = numeric.astype(float)
            else:
                df[op.column] = series.astype(str)
        except Exception:
             raise ValueError(f"Type conversion failed: {op.column} -> {dtype}")

        return df

    def execute_terminate(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Terminate):
            raise ValueError(f"Expected Terminate operation, got {type(op).__name__}")

        if not op.result or not isinstance(op.result, list):
            raise ValueError(f"Terminate operation must have a result list, got {op.result}")

        for name in op.result:
            if name not in trial.tables:
                raise ValueError(f"Table {name} not found in the input tables.")
        df = trial.tables[op.result[0]]

        return df
    
    def execute_error_detection(self, op: BaseOp, trial: Trial):
        if not isinstance(op, ErrorDetection):
            raise ValueError(f"Expected ErrorDetection operation, got {type(op).__name__}")
        table_name = op.table_name
        column_name = op.column_name
        func = op.func
        df = trial.tables[table_name].copy()
        try:
            # ---  Lambda  ---
            if func.strip().startswith('lambda'):
                lambda_f = eval(func, {'re': re, 'pd': pd, 'np': np})
                def check_error_lambda(val):
                    if pd.isna(val): return False
                    try:
                        return bool(lambda_f(val))
                    except Exception as e:
                        self.logger.log(f"Error checking value {val} with lambda: {e}")
                        return False
                
                mask = df[column_name].apply(check_error_lambda)
                df = df[mask]
                return df
            # -----------------------

            from src.tools.utils.funcs import parse_function_string, execute_code_from_string
            # Parse the function string to get function name and arguments
            func_info = parse_function_string(func)
            if 'name' not in func_info or not func_info['name']:
                raise ValueError("Could not parse function definition from provided code")
            func_name = func_info['name']
            args = func_info['args']
            if len(args) != 1:
                raise ValueError(f"Expected function with 1 argument, got {len(args)}")
            arg_name = args[0]
            
            # Apply the error check function to each value in the column
            def check_error(val):
                if pd.isna(val):
                    return False
                try:
                    exe_code = func + '\n\n' + f'my_error_check_result = {func_name}({arg_name}=input_val)'
                    result = execute_code_from_string(code_string=exe_code, input_dict={'input_val': val}, output_vals=['my_error_check_result'])
                    if result and len(result) == 1:
                        return bool(result[0])
                    else:
                        self.logger.log(f"No result returned for error check on value {val}")
                        return False
                except Exception as e:
                    self.logger.log(f"Error checking value {val}: {e}")
                    return False

            # Apply the error check function and filter out rows with errors
            mask = df[column_name].apply(check_error)
            df = df[mask]
        except Exception as e:
            self.logger.log(f"Error during error detection: {e}")
            raise ValueError(f"Failed to detect errors in column {column_name}: {str(e)}")
        return df

    def execute_add_new_column(self, op: BaseOp, trial: Trial):
        if not isinstance(op, AddNewColumn):
            raise ValueError(f"Expected AddNewColumn operation, got {type(op).__name__}")
        table_name = op.table_name
        new_column_name = op.new_column_name
        func = op.func
        df = trial.tables[table_name].copy()
        try:
            # ---  Lambda  ---
            if func.strip().startswith('lambda'):
                lambda_f = eval(func, {'re': re, 'pd': pd, 'np': np})
                def compute_new_value_lambda(row):
                    try:
                        return lambda_f(row)
                    except Exception as e:
                        self.logger.log(f"Error computing new value with lambda: {e}")
                        return None
                
                df[new_column_name] = df.apply(compute_new_value_lambda, axis=1)
                return df
            # -----------------------
            
            from src.tools.utils.funcs import parse_function_string, execute_code_from_string
            # Parse the function string to get function name and arguments
            func_info = parse_function_string(func)
            if 'name' not in func_info or not func_info['name']:
                raise ValueError("Could not parse function definition from provided code")
            func_name = func_info['name']
            args = func_info['args']
            if len(args) != 1:
                raise ValueError(f"Expected function with 1 argument (row), got {len(args)}")
            arg_name = args[0]
            
            self.logger.log(f"Function string for new column computation: \n{func}")
            self.logger.log(f"Parsed function info: name={func_name}, args={arg_name}")
            
            # Apply the computation function to each row to create the new column
            def compute_new_value(row):
                try:
                    # Convert row to dictionary for passing to function
                    exe_code = func + '\n\n' + f'my_new_column_value = {func_name}({arg_name}=input_val)'
                    result = execute_code_from_string(code_string=exe_code, input_dict={'input_val': row}, output_vals=['my_new_column_value'])
                    if result and len(result) == 1:
                        return result[0]
                    else:
                        self.logger.log(f"No result returned for row computation")
                        return None
                except Exception as e:
                    self.logger.log(f"Error computing new value for row: {e}")
                    return None
            
            # Use the specified new column name from the operator
            df[new_column_name] = df.apply(compute_new_value, axis=1)
        except Exception as e:
            self.logger.log(f"Error during new column addition: {e}")
            raise ValueError(f"Failed to add new column to table {table_name}: {str(e)}")
        return df

    def execute_drop_column(self, op: BaseOp, trial: Trial):
        if not isinstance(op, DropColumn):
            raise ValueError(f"Expected DropColumn operation, got {type(op).__name__}")
        table_name = op.table_name
        drop_columns = op.drop_columns
        df = trial.tables[table_name].copy()
        try:
            df = df.drop(columns=drop_columns, errors='ignore')
        except Exception as e:
            self.logger.log(f"Error during column drop: {e}")
            raise ValueError(f"Failed to drop columns {drop_columns} from table {table_name}: {str(e)}")
        return df

    def execute_split_column(self, op: BaseOp, trial: Trial):
        if not isinstance(op, SplitColumn):
            raise ValueError(f"Expected SplitColumn operation, got {type(op).__name__}")
        table_name = op.table_name
        source_column = op.source_column
        target_columns = op.target_columns
        func = op.func
        df = trial.tables[table_name].copy()
        try:
            # ---  Lambda  ---
            if func.strip().startswith('lambda'):
                lambda_f = eval(func, {'re': re, 'pd': pd, 'np': np})
                for col in target_columns:
                    df[col] = None
                
                for i in range(len(df)):
                    val = df.iloc[i][source_column]
                    if pd.isna(val): continue
                    try:
                        res = lambda_f(val)
                        if isinstance(res, dict):
                            for col in target_columns:
                                if col in res:
                                    df[col].iloc[i] = res[col]
                        else:
                            raise ValueError(f"Lambda result must be a dict, got {type(res)}")
                    except Exception as e:
                        self.logger.log(f"Error splitting value {val} with lambda at index {i}: {e}")
                        continue
                df = df.drop(columns=[source_column])
                return df
            # -----------------------

            
            from src.tools.utils.funcs import parse_function_string, execute_code_from_string
            func_info = parse_function_string(func)
            if 'name' not in func_info or not func_info['name']:
                raise ValueError("Could not parse function definition from provided code")
            func_name = func_info['name']
            args = func_info['args']
            if len(args) != 1:
                raise ValueError(f"Expected function with 1 argument, got {len(args)}")
            arg_name = args[0]
            
            # Initialize new columns with None
            for col in target_columns:
                df[col] = None
            
            # Iterate through each row and apply the split function
            for i in range(len(df)):
                val = df.iloc[i][source_column]
                if pd.isna(val):
                    continue  # Skip if value is NaN
                try:
                    # input_val = f'"""{val}"""' if isinstance(val, str) else str(val)
                    exe_code = func + '\n\n' + f'my_split_result = {func_name}({arg_name}=input_val)'
                    result = execute_code_from_string(code_string=exe_code, input_dict={'input_val': val}, output_vals=['my_split_result'])
                    if result and len(result) == 1 and isinstance(result[0], dict):
                        split_dict = result[0]
                        for col in target_columns:
                            if col in split_dict:
                                df[col].iloc[i] = split_dict[col]
                    else:
                        raise ValueError(f"Invalid split result for value {val}: {result}. The function should return a dictionary with target column names as keys.")
                except Exception as e:
                    self.logger.log(f"Error splitting value {val} at index {i}: {e}")
                    continue 
            df = df.drop(columns=[source_column])
        except Exception as e:
            self.logger.log(f"Error during column split: {e}")
            raise ValueError(f"Failed to split column {source_column} in table {table_name}: {str(e)}")
        return df

    def execute_concatenate(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Concatenate):
            raise ValueError(f"Expected Concatenate operation, got {type(op).__name__}")
        table_name = op.table_name
        concatenate_columns = op.concatenate_columns
        target_column = op.target_column
        func = op.func
        df = trial.tables[table_name].copy()
        try:
            # ---  Lambda  ---
            if func.strip().startswith('lambda'):
                lambda_f = eval(func, {'re': re, 'pd': pd, 'np': np})
                def concatenate_values_lambda(row):
                    try:
                        return lambda_f(row)
                    except Exception as e:
                        self.logger.log(f"Error concatenating values with lambda: {e}")
                        return None
                
                df[target_column] = df[concatenate_columns].apply(concatenate_values_lambda, axis=1)
                df = df.drop(columns=concatenate_columns)
                return df
            # -----------------------

            from src.tools.utils.funcs import parse_function_string, execute_code_from_string
            func_info = parse_function_string(func)
            if 'name' not in func_info or not func_info['name']:
                raise ValueError("Could not parse function definition from provided code")
            func_name = func_info['name']
            args = func_info['args']
            if len(args) != 1:
                raise ValueError(f"Expected function with 1 argument (row), got {len(args)}")
            arg_name = args[0]
            
            # self.logger.log(f"Function string for concatenation: \n{func}")
            # self.logger.log(f"Parsed function info: name={func_name}, args={arg_name}")
            
            def concatenate_values(row):
                try:
                    exe_code = func + '\n\n' + f'my_concat_result = {func_name}({arg_name}=input_val)'
                    result = execute_code_from_string(code_string=exe_code, input_dict={'input_val': row}, output_vals=['my_concat_result'])
                    if result and len(result) == 1:
                        return result[0]
                    else:
                        self.logger.log(f"No result returned for concatenation")
                        return None
                except Exception as e:
                    self.logger.log(f"Error concatenating values for row: {e}")
                    return None

            df[target_column] = df[concatenate_columns].apply(concatenate_values, axis=1)
            # drop the concatenate_columns
            df = df.drop(columns=concatenate_columns)
        except Exception as e:
            self.logger.log(f"Error during concatenation: {e}")
            raise ValueError(f"Failed to concatenate columns {concatenate_columns} in table {table_name}: {str(e)}")
        return df

    def execute_subtitle(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Subtitle):
            raise ValueError(f"Expected Subtitle operation, got {type(op).__name__}")
        table_name = op.table_name
        title = op.title
        target_column = op.target_column
        df = trial.tables[table_name].copy()
        try:
            # Add the subtitle as a new column with the same value for all rows
            df[target_column] = title
            self.logger.log(f"Added subtitle '{title}' as column '{target_column}' to table {table_name}")
        except Exception as e:
            self.logger.log(f"Error during subtitle addition: {e}")
            raise ValueError(f"Failed to add subtitle to table {table_name}: {str(e)}")
        return df

    def execute_append(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Append):
            raise ValueError(f"Expected Append operation, got {type(op).__name__}")
        table_name = op.table_name
        table_to_be_appended = op.table_to_be_appended
        source_df = trial.tables[table_name].copy()
        append_df = trial.tables[table_to_be_appended].copy()
        try:
            # Ensure columns match between the two DataFrames
            missing_cols_source = set(append_df.columns) - set(source_df.columns)
            for col in missing_cols_source:
                source_df[col] = pd.NA
            missing_cols_append = set(source_df.columns) - set(append_df.columns)
            for col in missing_cols_append:
                append_df[col] = pd.NA
            
            # Reorder columns to match
            append_df = append_df[source_df.columns]
            result_df = pd.concat([source_df, append_df], ignore_index=True)
        except Exception as e:
            self.logger.log(f"Error during append operation: {e}")
            raise ValueError(f"Failed to append table {table_to_be_appended} to {table_name}: {str(e)}")
        return result_df

    def execute_count(self, op: BaseOp, trial: Trial):
        if not isinstance(op, Count):
            raise ValueError(f"Expected Count operation, got {type(op).__name__}")
        table_name = op.table_name
        df = trial.tables[table_name].copy()
        try:
            count_value = len(df)
            # Create a new DataFrame with a single row and column for the count
            if 'statistic_table' not in trial.tables:
                result_df = pd.DataFrame({'operator': [str(op)], 'statistic_name': ['count'], 'value': [count_value]})
            else:
                result_df = trial.tables['statistic_table']
                # append a new row
                result_df = pd.concat([result_df, pd.DataFrame({'operator': [str(op)], 'statistic_name': ['count'], 'value': [count_value]})], ignore_index=True)
        except Exception as e:
            self.logger.log(f"Error during count operation: {e}")
            raise ValueError(f"Failed to count rows in table {table_name}: {str(e)}")
        return result_df

    def execute_code_generation(self, op: BaseOp, trial: Trial):
        if not isinstance(op, CodeGeneration):
            raise ValueError(f"Expected CodeGeneration operation, got {type(op).__name__}")
        table_names = op.table_names
        target_table = op.target_table
        func = op.func
        try:
            from src.tools.utils.funcs import parse_function_string, execute_code_from_string
            func_info = parse_function_string(func)
            if 'name' not in func_info or not func_info['name']:
                raise ValueError("Could not parse function definition from provided code")
            func_name = func_info['name']
            args = func_info['args']
            if len(args) != len(table_names):
                raise ValueError(f"Expected function with {len(table_names)} arguments, got {len(args)}")
            
            self.logger.log(f"Function string for code generation: \n{func}")
            self.logger.log(f"Parsed function info: name={func_name}, args={args}")
            
            # Prepare input dictionary with DataFrames
            input_dict = {arg: trial.tables[table_name].copy() for arg, table_name in zip(args, table_names)}
            # Execute the code to generate a new table
            exe_code = func + '\n\n' + f'my_generated_table = {func_name}(' + ', '.join([f"{arg}={arg}" for arg in args]) + ')'
            result = execute_code_from_string(code_string=exe_code, input_dict=input_dict, output_vals=['my_generated_table'])
            if result and len(result) == 1:
                # Assuming the function returns a single DataFrame
                return result[0]
            else:
                raise ValueError("CodeGeneration did not return a valid DataFrame")
        except Exception as e:
            self.logger.log(f"Error during code generation: {e}")
            raise ValueError(f"Failed to execute code generation for tables {table_names}: {str(e)}")

    def execute_calculate_statistic(self, op: BaseOp, trial: Trial):
        if not isinstance(op, CalculateStatistic):
            raise ValueError(f"Expected CalculateStatistic operation, got {type(op).__name__}")
        table_name = op.table_name
        statistic_name = op.statistic_name
        func = op.func
        try:
            from src.tools.utils.funcs import parse_function_string, execute_code_from_string
            func_info = parse_function_string(func)
            if 'name' not in func_info or not func_info['name']:
                raise ValueError("Could not parse function definition from provided code")
            func_name = func_info['name']
            args = func_info['args']
            if len(args) != 1:
                raise ValueError(f"Expected function with 1 argument, got {len(args)}")
            
            self.logger.log(f"Function string for statistic calculation: \n{func}")
            self.logger.log(f"Parsed function info: name={func_name}, args={args}")
            
            # Prepare input dictionary with DataFrames
            input_dict = {arg: trial.tables[table_name].copy() for arg, table_name in zip(args, [table_name])}
            # Execute the code to calculate the statistic
            arg_str = ', '.join([f"{arg}={arg}" for arg in args])
            exe_code = func + '\n\n' + f'my_statistic_result = {func_name}({arg_str})'
            result = execute_code_from_string(code_string=exe_code, input_dict=input_dict, output_vals=['my_statistic_result'])
            if result and len(result) == 1:
                # Create a new DataFrame with a single row and column for the statistic
                if 'statistic_table' not in trial.tables:
                    result_df = pd.DataFrame({'operator': [str(op)], 'statistic_name': [statistic_name], 'value': [result[0]]})
                else:
                    result_df = trial.tables['statistic_table']
                    # append a new row
                    result_df = pd.concat([result_df, pd.DataFrame({'operator': [str(op)], 'statistic_name': [statistic_name], 'value': [result[0]]})], ignore_index=True)
                return result_df
            else:
                raise ValueError("CalculateStatistic did not return a valid result")
        except Exception as e:
            self.logger.log(f"Error during statistic calculation: {e}")
            raise ValueError(f"Failed to calculate statistic {statistic_name} for table {table_name}: {str(e)}")

    def execute_op_on_df(self, op: BaseOp, df: pd.DataFrame):
        if op in [CodeGeneration, Count, Terminate, Join, Union]:
            raise ValueError(f"Unsupported operation: {type(op).__name__}")

        table_key = op.table_name
        tri = Trial(exp_id='test', task=Task(id='testid'))
        tri.tables[table_key] = df.copy()

        generated_table = self.execute_op(op, tri)

        return generated_table

    def execute_op(self, op: BaseOp, trial: Trial):
        if type(op) not in self.function_mapper:
            raise ValueError(f"Unsupported operation: {type(op).__name__} with {op}, the keys are {self.function_mapper.keys()}")
        try:
            df = self.function_mapper[type(op)](op, trial)
        except Exception as e:
            self.logger.log(f"Error during executing operation {op}: {e}")
            raise ValueError(f"Failed to execute operation {op}: {str(e)}")

        return df

    def execute_inverse_pivot(self, op: BaseOp, trial: Trial):
        if not isinstance(op, InversePivot):
            raise ValueError(f"Expected InversePivot operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        result = pd.melt(df, id_vars=op.index, value_vars=df.columns.difference([op.index]), var_name=op.columns, value_name=op.values)
        # InversePivot operation reverses a pivot, converting a wide DataFrame back to a long format.
        # It is similar to Stack as both operations use pd.melt to unpivot data, but they may differ in parameter configuration.
        # In this implementation, Stack allows explicit specification of value_vars, while InversePivot dynamically determines value_vars as all columns except the index.
        # Thus, they are not strictly equivalent due to potential differences in column selection.
        # Case Example for InversePivot:
        # Input DataFrame:
        #   ID  A   B
        #   1   10  20
        #   2   30  40
        # After InversePivot with index='ID', var_name='Category', value_name='Value':
        #   ID  Category  Value
        #   1   A         10
        #   1   B         20
        #   2   A         30
        #   2   B         40
        return result

    def execute_inverse_stack(self, op: BaseOp, trial: Trial):
        if not isinstance(op, InverseStack):
            raise ValueError(f"Expected InverseStack operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        # Use pivot instead of pivot_table since we're reversing a stack operation
        # and don't need aggregation
        result = df.pivot(index=op.id_vars, columns=op.var_name, values=op.value_name).reset_index()
        return result

    def execute_inverse_explode(self, op: BaseOp, trial: Trial):
        if not isinstance(op, InverseExplode):
            raise ValueError(f"Expected InverseExplode operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        result = df.groupby(df.index).agg({op.column: lambda x: ','.join(x) if op.split_comma else list(x)}).reset_index(drop=True)
        return result

    def execute_inverse_wide_to_long(self, op: BaseOp, trial: Trial):
        if not isinstance(op, InverseWideToLong):
            raise ValueError(f"Expected InverseWideToLong operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        
        # Pivot the data from long to wide format
        result = df.pivot(index=op.i, columns=op.j, values=op.subnames).reset_index()
        
        # Flatten multi-level column index if necessary
        if isinstance(result.columns, pd.MultiIndex):
            # Create new column names in the format subname_sep_value
            new_columns = []
            for col in result.columns:
                if col[1] == '':  # This is one of the index columns
                    new_columns.append(col[0])
                else:
                    # col[0] is the subname (value column name), col[1] is the value of j column
                    new_columns.append(f"{col[0]}{op.sep}{col[1]}")
            result.columns = new_columns
        
        # Ensure numeric columns maintain their type
        for col in result.columns:
            if col not in op.i:
                result[col] = pd.to_numeric(result[col], errors='coerce')
        
        # drop rows where all values are NaN
        result = result.dropna(how='all', subset=op.subnames)

        return result

    def execute_inverse_transpose(self, op: BaseOp, trial: Trial):
        if not isinstance(op, InverseTranspose):
            raise ValueError(f"Expected InverseTranspose operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        
        # Reverse the transpose operation by restoring the original structure
        # The first column contains the original column names
        if len(df.columns) > 0:
            # Get the first column which contains the original column names
            first_col = df.columns[0]
            original_col_names = df[first_col].tolist()
            
            # Remove the first column and transpose
            df_data = df.drop(columns=[first_col])
            df_t = df_data.transpose()
            
            # Set the column names to the original column names
            df_t.columns = original_col_names
            
            # Reset index to make the original index a regular column
            df_t = df_t.reset_index()
            
            # Rename the index column to the original first column name
            if len(df_t.columns) > 0:
                df_t = df_t.rename(columns={df_t.columns[0]: first_col})
            
            result = df_t
        else:
            result = df.transpose()
            
        return result

    def execute_inverse_drop_nulls(self, op: BaseOp, trial: Trial):
        if not isinstance(op, InverseDropNulls):
            raise ValueError(f"Expected InverseDropNulls operation, got {type(op).__name__}")

        df = trial.tables[op.table_name].copy()
        subset = op.subset if op.subset is not None else df.columns.tolist()
        how = op.how
        count = op.count

        if count > 0:
            new_rows_list = []
            for _ in range(count):
                new_row = df.sample(n=1).copy()
                if how == "all":
                    for col in subset:
                        new_row[col] = None
                elif how == "any":
                    import random
                    null_col = random.choice(subset)
                    new_row[null_col] = None
                # For non-subset columns, randomly select values from other rows
                for col in df.columns:
                    if col not in subset:
                        random_value = df[col].sample(n=1, random_state=None).iloc[0]
                        new_row[col] = random_value
                new_rows_list.append(new_row)
            new_rows = pd.concat(new_rows_list, ignore_index=True)
            result = pd.concat([df, new_rows], ignore_index=True)
        else:
            result = df

        return result

    def execute_inverse_deduplicate(self, op: BaseOp, trial: Trial):
        if not isinstance(op, InverseDeduplicate):
            raise ValueError(f"Expected InverseDeduplicate operation, got {type(op).__name__}")
        df = trial.tables[op.table_name].copy()
        subset = op.subset if op.subset is not None else df.columns.tolist()
        count = op.count

        # assert that all tuples in subset are unique
        if df.duplicated(subset=subset).any():
            raise ValueError(f"Tuples in subset {subset} are not unique before inverse deduplication")

        # insert duplicate rows, make sure only the subset columns are duplicated from the reference row
        if count > 0:
            # Use the last row as the reference row for subset values
            reference_row = df.tail(1).copy()
            duplicated_rows_list = []
            for _ in range(count):
                new_row = reference_row.copy()
                # For non-subset columns, randomly select values from other rows
                for col in df.columns:
                    if col not in subset:
                        random_value = df[col].sample(n=1, random_state=None).iloc[0]
                        new_row[col] = random_value
                duplicated_rows_list.append(new_row)
            duplicated_rows = pd.concat(duplicated_rows_list, ignore_index=True)
            result = pd.concat([df, duplicated_rows], ignore_index=True)

        return result

class CodeExecutor:
    def __init__(self, cfg: Config, debug: bool = True, log_file='_MAIN'):
        self.cfg = cfg
        self.logger = Logger(name = '[MAS] Code Executor', cfg=self.cfg, debug=debug, log_file=log_file)
        
        from src.agent.code_generation import CodeGen
        self.coder = CodeGen(cfg=cfg, log_file=log_file)

    def execute_op(self, op: BaseOp, trial: Trial):
        return self.coder.implement_and_execute_logical_operator(trial, op)

class Executor:
    def __init__(self, cfg: Config, debug: bool = True, log_file='_MAIN'):
        self.cfg = cfg
        self.logger = Logger(name = '[MAS] Executor', cfg=self.cfg, debug=debug, log_file=log_file)
        self.rule_executor = RuleExecutor(cfg, debug, log_file)
        self.code_executor = CodeExecutor(cfg, debug, log_file)

    def execute_op(self, op: BaseOp, trial: Trial, mode='rule'):
        if isinstance(op, Terminate):
            df = self.rule_executor.execute_op(op, trial)
        elif mode == 'rule':
            df = self.rule_executor.execute_op(op, trial)
        elif mode == 'code':
            df = self.code_executor.execute_op(op, trial)
        else:
            raise ValueError(f"Invalid mode: {mode}")

        out_tblname = get_generated_table_name(op)

        # set the column name to string
        df.columns = df.columns.astype(str)

        output = f'Name: "{out_tblname}"\n{df_to_cotable(df, cut_line=self.cfg.get("gen_tbl_cut_line"), cut_col=self.cfg.get("gen_tbl_cut_col"))}'
        self.logger.log(f'Executed Op: {op}', f'Output:\n{output}', sep='\n')

        # if df.empty:
        #     raise ValueError(f'The output table is empty after executing operator {op}!')

        return out_tblname, df
    
    def step_op(self, op: BaseOp, trial: Trial, out_tbl_name: str, out_tbl_obj: pd.DataFrame):
        output = None
        if isinstance(op, Terminate):
            trial.set_generated_tables(op.result)
            output = f'Output the final tables: {op.result}.'
            for tbl in op.result:
                output += f'The table {tbl} has {out_tbl_obj.shape[0]} rows and has {out_tbl_obj.shape[1]} columns: ' + ', '.join(out_tbl_obj.columns.tolist()) + '.'
        else:
            output = f'Table Name: "{out_tbl_name}"\nTable Data:\n{df_to_cotable(out_tbl_obj, cut_line=self.cfg.get("gen_tbl_cut_line"), cut_col=self.cfg.get("gen_tbl_cut_col"), max_len=1000)}'

        trial.tables[out_tbl_name] = out_tbl_obj
        trial.add_op(op, output)
        self.logger.log(f'Step Op: {op}', f'Output:\n{output}', sep='\n')

        return output
