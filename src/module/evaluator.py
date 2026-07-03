import pandas as pd
import numpy as np
from pandas.api.types import is_numeric_dtype
from typing import Union

from src.data.trial import Trial
from src.tools.helper import Config, Logger
from src.tools.utils.standardize import is_float

class Evaluator:
    """
    Evaluates the result of a trial by comparing the generated tables with a target table.
    """
    def __init__(self, cfg: Config, debug: bool = True, log_file='_MAIN'):
        self.cfg = cfg
        self.logger = Logger(name = '[MAS] Evaluator', cfg=self.cfg, debug=debug, log_file=log_file)

    def evaluate_trial_tables(self, trial: Trial) -> tuple[bool, str]:
        """
        Evaluate if any table in the trial matches the target table.

        Args:
            trial (Trial): The trial object containing the generated tables.
            target_T (pd.DataFrame): The target table to match against.

        Returns:
            tuple: A tuple containing a boolean indicating if a match was found,
                   and a message describing the result.
        """
        generated_tables = trial.generated_tbls
        target_T = trial.tgt_tbl
        if not generated_tables:
            return False, "No tables were generated in the trial."

        last_error_msg = ""
        for table_name, generated_T in generated_tables.items():
            is_match, msg = self.validate(generated_T, target_T)
            if is_match:
                success_msg = f"Success: Generated table '{table_name}' matches the target table."
                self.logger.log(f'Evaluating {trial.task.id}: {success_msg}')
                return True, success_msg
            else:
                last_error_msg = f"Table '{table_name}' did not match target: {msg}"
                self.logger.log(f'Evaluating {trial.task.id}: {last_error_msg}')

        return False, f"Failure: {last_error_msg}"

    def calculate_similarity_reward(self, trial: Trial) -> float:
        """
        Calculate the similarity reward for a trial.
        """
        generated_tables = trial.generated_tbls
        target_T = trial.tgt_tbl
        if not generated_tables:
            return 0.0
        reward = -1.0
        for table_name, generated_T in generated_tables.items():
            score, details = self.calculate_similarity(generated_T, target_T)
            reward = max(reward, score)
        return reward

    @staticmethod
    def calculate_similarity(
        table_a: pd.DataFrame, 
        table_b: pd.DataFrame, 
        tolerance: float = 1e-6,
        weights: dict = None
    ) -> float:
        """
        Calculates a similarity score between two DataFrames, ranging from 0.0 to 1.0.

        The score is a weighted average of schema, shape, and content similarity.

        Args:
            table_a (pd.DataFrame): The first table (e.g., generated table).
            table_b (pd.DataFrame): The second table (e.g., target table).
            tolerance (float): Absolute error tolerance for numeric column comparison.
            weights (dict): A dictionary with weights for 'schema', 'shape', and 'content'. 
                            Defaults to {'schema': 0.3, 'shape': 0.2, 'content': 0.5}.

        Returns:
            float: A similarity score between 0.0 and 1.0.
        """
        if weights is None:
            weights = {'schema': 0.4, 'shape': 0.2, 'content': 0.4}

        # 0. Pre-check and cleaning
        if not isinstance(table_a, pd.DataFrame) or not isinstance(table_b, pd.DataFrame):
            return 0.0, {'schema': 0.0, 'shape': 0.0, 'content': 0.0}
        
        # Standardize NaNs and copy to avoid side effects
        df1 = table_a.replace([pd.NA, 'nan', 'None', '<NA>'], np.nan).copy()
        df2 = table_b.replace([pd.NA, 'nan', 'None', '<NA>'], np.nan).copy()
        df1.columns = df1.columns.astype(str)
        df2.columns = df2.columns.astype(str)

        # --- 1. Schema Similarity (Jaccard Index for columns) ---
        cols1 = set(df1.columns)
        cols2 = set(df2.columns)
        
        if not cols1 and not cols2: # Both tables have no columns
            return 1.0, {'schema': 1.0, 'shape': 1.0, 'content': 1.0}

        intersection = cols1.intersection(cols2)
        union = cols1.union(cols2)
        s_schema = len(intersection) / len(union) if union else 0.0

        # --- 2. Shape Similarity (Row count ratio) ---
        rows1, rows2 = len(df1), len(df2)
        s_shape = 1.0 if rows1 == rows2 else 0.0

        # --- 3. Content Similarity ---
        s_content = 0.0
        common_cols = sorted(list(intersection))
        
        if common_cols and min(rows1, rows2) > 0:
            # Align tables for comparison
            df1_common = df1[common_cols]
            df2_common = df2[common_cols]

            try:
                # Safe sorting
                df1_sorted = df1_common.sort_values(by=common_cols, key=lambda col: col.map(str), na_position="first").reset_index(drop=True)
                df2_sorted = df2_common.sort_values(by=common_cols, key=lambda col: col.map(str), na_position="first").reset_index(drop=True)
            except (TypeError, ValueError):
                # If sorting fails due to very messy types, content similarity is 0
                df1_sorted, df2_sorted = df1_common, df2_common # Keep original order as fallback

            # Compare content only up to the minimum number of rows
            num_rows_to_compare = min(len(df1_sorted), len(df2_sorted))
            df1_trimmed = df1_sorted.head(num_rows_to_compare)
            df2_trimmed = df2_sorted.head(num_rows_to_compare)

            col_similarities = []
            for col in common_cols:
                s1 = df1_trimmed[col]
                s2 = df2_trimmed[col]
                
                matches = 0
                # Numeric comparison
                if is_numeric_dtype(s1.dtype) and is_numeric_dtype(s2.dtype):
                    matches = np.isclose(s1, s2, atol=tolerance, equal_nan=True).sum()
                # Generic string-based comparison
                else:
                    s1_str = s1.fillna("__NA__").astype(str)
                    s2_str = s2.fillna("__NA__").astype(str)
                    matches = (s1_str == s2_str).sum()
                
                col_similarity = matches / num_rows_to_compare if num_rows_to_compare > 0 else 1.0
                col_similarities.append(col_similarity)

            if col_similarities:
                s_content = np.mean(col_similarities)

        # --- 4. Final Weighted Score ---
        final_score = (weights['schema'] * s_schema +
                       weights['shape'] * s_shape +
                       weights['content'] * s_content)
        
        return final_score, {'schema': s_schema, 'shape': s_shape, 'content': s_content}

    @staticmethod
    def validate(table_a: pd.DataFrame, table_b: pd.DataFrame, tolerance: float = 1e-6, table_a_name: str = 'Generated Table', table_b_name: str = 'Target Table', type_match: bool = False) -> tuple[bool, Union[str, None]]:
        """
        Validate whether the generated table matches the target table, allowing a certain tolerance for numeric columns.

        Args:
            table_a (pd.DataFrame): default to be `Generated Table`.
            table_b (pd.DataFrame): default to be `Target Table`.
            tolerance (float): Absolute error tolerance for numeric column comparison, default is 1e-6.

        Returns:
            tuple: (Validation result: bool, Difference information: str or None)
        """
        # 1. Type check
        if not isinstance(table_a, pd.DataFrame) or not isinstance(table_b, pd.DataFrame):
            return False, f"{table_a_name} or {table_b_name} is not a DataFrame."
        
        table_a = table_a.replace([pd.NA, 'nan', 'None', '<NA>'], np.nan)
        table_b = table_b.replace([pd.NA, 'nan', 'None', '<NA>'], np.nan)

        
        table_a = table_a.copy()
        table_b = table_b.copy()
        table_a.columns = table_a.columns.astype(str)
        table_b.columns = table_b.columns.astype(str)

        # 2. Column name check (ignore order)
        cols_gen = set(table_a.columns)
        cols_tgt = set(table_b.columns)
        if cols_gen != cols_tgt:
            missing = cols_tgt - cols_gen
            extra = cols_gen - cols_tgt
            msg = []
            if missing:
                msg.append(f"Missing columns: {missing}")
            if extra:
                msg.append(f"Extra columns: {extra}")
            return False, "; ".join(msg)

        # Handle empty dataframes
        if table_a.empty and table_b.empty:
            return True, None
        if table_a.empty or table_b.empty:
             return False, f"Row count mismatch: {table_a_name} has {len(table_a)} rows, {table_b_name} has {len(table_b)} rows."

        # 3. Align columns, sort by all columns, and reset index
        cols = sorted(list(cols_gen))
        df1 = table_a[cols]
        df2 = table_b[cols]

        try:
            # Use a safer string conversion for sorting to avoid dtype promotion issues
            df1 = df1.sort_values(by=cols, key=lambda col: col.map(str), na_position="first").reset_index(drop=True)
            df2 = df2.sort_values(by=cols, key=lambda col: col.map(str), na_position="first").reset_index(drop=True)
        except (TypeError, ValueError) as e:
            return False, f"Failed to sort tables for comparison due to mixed types: {e}"

        # 4. Row count check
        if len(df1) != len(df2):
            return False, f"Row count mismatch: {table_a_name} has {len(df1)} rows, {table_b_name} has {len(df2)} rows."

        # 5. Compare columns one by one
        if type_match:
            mismatch_rows = []
            for col in cols:
                for i in range(len(df1)):
                    val1, val2 = df1.loc[i, col], df2.loc[i, col]
                    if is_float(val1) and is_float(val2):
                        if np.isclose(val1, val2, atol=tolerance, equal_nan=True): continue
                        else: mismatch_rows.append(i)
                    else:
                        if type(val1) != type(val2) or val1 != val2:
                            mismatch_rows.append(i)

            if len(mismatch_rows) > 0:
                return False, f"Column '{col}' mismatches at rows {mismatch_rows}."
            return True, None
            
        else:
            for col in cols:
                s1, s2 = df1[col], df2[col]
                mask = None

                # Numeric column comparison
                if is_numeric_dtype(s1.dtype) and is_numeric_dtype(s2.dtype):
                    mask = np.isclose(s1, s2, atol=tolerance, equal_nan=True)
                # Mixed numeric/object comparison
                elif is_numeric_dtype(s1.dtype) != is_numeric_dtype(s2.dtype):
                    s1_conv = pd.to_numeric(s1, errors='coerce')
                    s2_conv = pd.to_numeric(s2, errors='coerce')
                    
                    if s1.notna().eq(s1_conv.notna()).all() and s2.notna().eq(s2_conv.notna()).all():
                        mask = np.isclose(s1_conv, s2_conv, atol=tolerance, equal_nan=True)
                    else:
                        mask = s1.fillna("__NA__").astype(str).eq(s2.fillna("__NA__").astype(str)).to_numpy()
                # Other cases compare as object/string
                else:
                    mask = s1.fillna("__NA__").astype(str).eq(s2.fillna("__NA__").astype(str)).to_numpy()

                if not np.all(mask):
                    bad_idx = np.where(~mask)[0][:5].tolist()
                    return False, (
                        f"Column '{col}' mismatches at rows {bad_idx}.\n"
                        f"{table_a_name} samples: {df1.loc[bad_idx, col].tolist()}\n"
                        f"{table_b_name} samples: {df2.loc[bad_idx, col].tolist()}"
                    )

            return True, None