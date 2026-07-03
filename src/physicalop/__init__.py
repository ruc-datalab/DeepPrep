from random import shuffle, seed
from ._base import *
from .data_transform import *
from .inverse_data_transform import *

seed(42)

DATA_CLEANING_OPS = [
    StandardizeString, 
    ErrorDetection, 
    DropNulls, 
    MissingValueImputation, 
    OutlierDetection, 
    StandardizeDatetime, 
    Deduplicate
]

COLUMN_TRANSFORMATION_OPS = [
    AddNewColumn, 
    CastType, 
    Explode, 
    Rename, 
    DropColumn, 
    SplitColumn, 
    Concatenate
]

TABLE_TRANSFORMATION_OPS = [
    Join, 
    Union, 
    Append, 
    Pivot, 
    Transpose, 
    Stack, 
    WideToLong, 
    Subtitle, 
    Sort, 
    GroupBy, 
    TopK, 
    Filter, 
    SelectCol, 
    Count, 
    CalculateStatistic
]

OTHER_OPS = [
    CodeGeneration, 
    Terminate
]

PARROT_OP = [
    Filter, Sort, Pivot, Join, GroupBy, Rename, Stack, Explode, WideToLong,
    Union, Transpose, DropNulls, Deduplicate, TopK, SelectCol, CastType, Terminate
]

AUTOPIPELINE_OP = [
    StandardizeDatetime,
    CodeGeneration,
    # Concatenate,
    Pivot,
    Stack,
    SplitColumn, Sort, Join, GroupBy, Rename,
    SelectCol, 
    Union, CastType, Terminate, Filter,
    AddNewColumn, DropColumn
]

NEW_OP = [
    MissingValueImputation,
    OutlierDetection,
    StandardizeString,
    StandardizeDatetime,
    ErrorDetection,
    CalculateStatistic,
    CodeGeneration,
    DropColumn,
    SplitColumn,
    Concatenate,
    AddNewColumn,
    Subtitle,
    Append,
    Count,
]

TASKTYPE_2_AVAILABLE_OP = {
    'PARROT': PARROT_OP, 
    'NEW': NEW_OP, 
}

TOTAL_OPS = NEW_OP + PARROT_OP

SQL_OPS = [
    Filter, Sort, Join, GroupBy, Rename,
    Union, Transpose, DropNulls, Deduplicate, TopK, SelectCol, CastType, Terminate,
    StandardizeString,
    StandardizeDatetime,
    CalculateStatistic,
    CodeGeneration,
    DropColumn,
    SplitColumn,
    Concatenate,
    AddNewColumn,
    Count,
]

OP_REQUIRE_INVERSE_OP = [
    CastType, Concatenate, Deduplicate, DropNulls, 
    ErrorDetection, Transpose, Explode, MissingValueImputation, 
    OutlierDetection, Pivot, Rename, SplitColumn, 
    Stack, StandardizeDatetime, StandardizeString, WideToLong
]

INVERSE_DESC_DICT = {
    'CastType': 'ConvertColumnToOtherType',
    'Concatenate': 'SplitColumn',
    'Deduplicate': 'InsertDuplicatedRow',
    'DropNulls': 'InsertNullRow',
    'ErrorDetection': 'InsertErrorRow',
    'Transpose': 'Transpose',
    'Explode': 'MergeColumn',
    'MissingValueImputation': 'InsertRowWithMissingValue',
    'OutlierDetection': 'InsertRowWithOutlier',
    'Pivot': 'Unpivot',
    'Rename': 'RenameColumn',
    'SplitColumn': 'Concatenate',
    'Stack': 'Unstack',
    'StandardizeDatetime': 'MakeDatetimeFormatInconsistent',
    'StandardizeString': 'MakeValueInconsistent',
    'WideToLong': 'LongToWide',
}



def get_generated_table_name(op: BaseOp):
    if isinstance(op, Join):
        return f'{op.left_table}_{op.right_table}_join'
    elif isinstance(op, Union):
        return '_'.join(op.table_names) + '_union'
    elif isinstance(op, Terminate):
        return op.result[0]
    elif isinstance(op, Count) or isinstance(op, CalculateStatistic):
        return 'statistic_table'
    elif isinstance(op, CodeGeneration):
        return op.target_table
    else:
        return op.table_name

def auto_parse_op(action_str:str):
    """
    Automatically detect the operation type from the action string.
    """
    action_str = action_str.strip()
    for op in TOTAL_OPS:
        try:
            action = op.parse_action_from_text(action_str)
        except:
            continue
        if action is not None:
            return action
    raise ValueError(f"Cannot detect operation type from action string: {action_str}. Please output the correct operator name and arguments.")
