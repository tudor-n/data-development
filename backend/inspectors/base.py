from abc import ABC, abstractmethod
import polars as pl
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
    def inspect(self, df: pl.DataFrame) -> List[Issue]:
        pass