import pandas as pd
import copy
from .funcs import cal_tokens

def add_row_number_to_df(df: pd.DataFrame, col_name='row_id'):
    if col_name in df.columns:
        df = df.drop(columns=[col_name])
    df.insert(0, col_name, range(1, len(df)+1)) 
    return df


def df_to_cotable(tbl: pd.DataFrame, cut_line = 10, cut_col = 20, max_len = 6000):
    if tbl is None:
        return "None"

    df = copy.deepcopy(tbl)

    columns = list(tbl.columns)
    if cut_col != -1 and len(tbl.columns) > cut_col:
        columns = columns[:cut_col]
        df = df[columns]

    ret = ""

    if cut_col != -1 and len(tbl.columns) > cut_col:
        header_str = ' | '.join([str(col).replace('\n', '\\n') for col in columns]) + ' | ...\n'
        header_str += '|'.join(['---' for _ in range(len(columns))]) + ' | ...\n'
    else:
        header_str = ' | '.join([str(col).replace('\n', '\\n') for col in columns]) + '\n'
        header_str += '|'.join(['---' for _ in range(len(columns))]) + '\n'

    ret += header_str
    
    for i in range(len(df)):
        if cut_line!=-1 and i > cut_line-1:
            ret += '......\n'
            break
        # row_str = ' | '.join([str(x) for x in df.iloc[i].values]) + '\n'
        row_eles = [x.replace("\n", "\\n") if type(x) == str else x for x in df.iloc[i].values]
        if cut_col != -1 and len(tbl.columns) > cut_col:
            row_str = ' | '.join([f'"{x}"' if type(x) == str else str(x) for x in row_eles]) + ' | ...\n'
        else:
            row_str = ' | '.join([f'"{x}"' if type(x) == str else str(x) for x in row_eles]) + '\n'
        ret += row_str
    
    ret = ret.strip()

    if len(ret) > max_len:
        return ret[:max_len] + "\n......\n[Truncated due to length]"
    
    if len(tbl) == 0:
        ret += '\n(The table is empty!!!)'

    return ret