import logging

from src.storage.csv_storage import CsvDataStorage
from src.core.models import SensorData
from src.core.observer import DataObserver 

class StorageObserver(DataObserver):
    """觀察者模式，監聽數據並存入 CSV"""

    def __init__(self, filename: str):
        self.filename = filename
        self.storage = CsvDataStorage()
        self.logger = logging.getLogger(__name__)

    def on_data_received(self, data: SensorData) -> None:
        """接收資料的標準方法"""
        if isinstance(data, SensorData):
            self.storage.save(data, f"{self.filename}_sensor.csv")
        else:
            self.logger.warning(f"StorageObserver received unsupported data type: {type(data)}")

    def on_error(self, error: Exception):
        """當發生錯誤時，記錄錯誤"""
        pass

