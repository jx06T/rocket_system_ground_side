from abc import ABC, abstractmethod
from src.core.models import SensorData

class DataObserver(ABC):
    @abstractmethod
    def on_data_received(self, data: SensorData):
        """當新數據到達時被調用"""
        pass

    @abstractmethod
    def on_error(self, error: Exception):
        """當發生錯誤時被調用"""
        pass
