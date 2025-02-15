import csv
import logging
from src.core.models import SensorData
from src.storage.base import DataStorage

class CsvDataStorage(DataStorage):
    """CSV 數據存儲"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def save(self, data: SensorData,filename:str):
        try:
            with open(filename, 'a', newline='') as f:
                fieldnames = ["timestamp", "rotationRoll", "rotationPitch", "direction"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                if f.tell() == 0:
                    writer.writeheader()
                    
                writer.writerow({
                    "timestamp": data.timestamp,
                    "rotationRoll": data.rotationRoll,
                    "rotationPitch": data.rotationPitch,
                    "direction": data.direction
                })
                
        except Exception as e:
            self.logger.error(f"CSV storage error: {e}")
