from tqdm import tqdm
from src.logicalop._base import *


class DataSummarization(BaseLogicalOp):
    """DataSummarization class to summarize the data

    For example:
    1. get a conclusion from the table
    """
    def __init__(self, desc:str = None, out: AtomicElement = None):
        super().__init__(name='DataSummarization', desc=desc, out=out)