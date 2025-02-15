from abc import ABC, abstractmethod
from src.core.models import SensorData

class DataStorage(ABC):
    """數據存儲的抽象類"""

    @abstractmethod
    def save(self, data: SensorData):
        """保存數據"""
        pass
