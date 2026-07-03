from typing import Optional, Dict, Union, List, Any
from abc import ABC, abstractmethod
import pandas as pd

class BaseOp:
    """
    Base class for all physical operations
    """

    def __init__(self):
        """
        Initialize the base operation.
        """
        pass
    
    @classmethod
    def get_action_description(cls) -> str:
        """
        Get the action description for the operation.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional['BaseOp']:
        """
        Parse the action from the given text.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class ContainerOp(BaseOp):

    def __init__(self):
        super().__init__()


class LocalOp(BaseOp):

    def __init__(self):
        super().__init__()



class Operation(ABC):
    """Base class for transformation operations"""
    
    def __init__(self, params: Dict = None, table: Union[pd.DataFrame, List[pd.DataFrame]] = None, table_info: Union[Dict, List[Dict]] = None, validate: bool = True):
        """
        Initialize operation
        
        Args:
            params: Operation parameters
            validate: Whether to validate parameters immediately
        """
        self.params = params or {}
        if isinstance(table, list):
            self.table = [df.copy() for df in table] if table else []
        elif isinstance(table, pd.DataFrame):
            if not table.empty:
                self.table = table.copy()
            else:
                self.table = pd.DataFrame()
        else:
            self.table = pd.DataFrame()

        self.table_info = table_info.copy() if table_info else []
        if validate:
            self.validate_params()
    
    def validate_params(self):
        """Validate parameter validity, implemented by subclasses"""
        pass
    
    @abstractmethod
    def transform(self) -> pd.DataFrame:
        """
        Perform transformation operation
        
        Args:
            self.df: Input DataFrame
            
        Returns:
            pd.DataFrame: Transformed DataFrame
        """
        pass
    
    def get_param(self, name: str, default: Any = None) -> Any:
        """
        Safely get parameter value
        
        Args:
            name: Parameter name
            default: Default value
            
        Returns:
            Parameter value
        """
        return self.params.get(name, default)