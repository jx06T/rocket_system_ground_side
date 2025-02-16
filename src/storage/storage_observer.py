import logging

from src.storage.csv_storage import CsvDataStorage
from src.storage.json_storage import JsonDataStorage
from src.core.models import SensorData,LogData
from src.core.observer import DataObserver 

class StorageObserver(DataObserver):
    """觀察者模式，監聽數據並存入 CSV"""

    def __init__(self, filename: str):
        self.filename = filename
        self.storage_handlers = {
            "sensor": {
                "csv": CsvDataStorage(),
                "json": JsonDataStorage()
            },
            "log": {
                "csv": CsvDataStorage(),
                "json": JsonDataStorage()
            }
       }
        self.default_storage = "csv"  
        self.logger = logging.getLogger(__name__)

        
    def on_data_received(self, data: SensorData) -> None:
        """接收資料的標準方法"""
        data_type = self._get_data_type(data)
        self._store_data(data, data_type, self.default_storage)

    def _store_data(self, data: SensorData, data_type: str, storage_type: str) -> None:
        """實際處理儲存邏輯"""
        if data_type in self.storage_handlers and storage_type in self.storage_handlers[data_type]:
            storage = self.storage_handlers[data_type][storage_type]
            storage.save(data, f"{self.filename}_{data_type}.{storage_type}")
        else:
            self.logger.error(f"Data storage error: Unexpected storage format")

    def _get_data_type(self, data: SensorData) -> str:
        """判斷資料類型"""
        if isinstance(data, SensorData):
            return "sensor"
        elif isinstance(data, LogData):
            return "log"
        else:
            raise ValueError(f"Unknown data type: {type(data)}")

    def on_error(self, error: Exception):
        """當發生錯誤時，記錄錯誤"""
        # self.logger.error(f"Data logging error: {error}")
