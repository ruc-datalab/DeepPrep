from tqdm import tqdm
from src.logicalop._base import *


class DataRetrieval(BaseLogicalOp):
    """DataRetrieval class to retrieve new data, (+ Data)

    For example:
    1. retrieve the salary information of an employee from [db]
    2. get description of [a term] used in the question
    3. describe files stored in some dir (such as [function], [py],...)
    """
    def __init__(self, desc:str = None, out: AtomicElement = None):
        super().__init__(name='DataRetrieval', desc=desc, out=out)