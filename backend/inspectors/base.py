from abc import ABC, abstractmethod
import pandas as pd
from typing import List
from models.schemas import Issue

class BaseInspector(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    @property
    @abstractmethod
    def category(self) -> str:
        pass
    @abstractmethod
    def inspect(self, df: pd.DataFrame) -> List[Issue]:
        pass