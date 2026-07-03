import pandas as pd
from typing import List

class Task:
    def __init__(self, id:str, inp_tbl_names:List[str]=None, tgt_tbl_name:str=None, tgt_tbl_description:str=None, split:str='test', type_='PARROT'):
        self.id = id
        self.inp_tbl_names = inp_tbl_names
        self.tgt_tbl_name = tgt_tbl_name
        self.tgt_tbl_description = tgt_tbl_description
        self.split = split
        self.type_ = type_