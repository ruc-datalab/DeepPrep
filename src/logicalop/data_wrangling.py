from tqdm import tqdm
from src.logicalop._base import *


class DataWrangling(BaseLogicalOp):
    """DataWrangling class to wrangle the data

    For example:
    1. union the table from [file1] and [file2]
    2. transform the table
    3. Edit the python file to debug
    """
    def __init__(self, desc:str = None, out: AtomicElement = None):
        super().__init__(name='DataWrangling', desc=desc, out=out)