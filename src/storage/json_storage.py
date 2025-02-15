import json
import logging
from src.core.models import SensorData
from src.storage.base import DataStorage

class JsonDataStorage(DataStorage):
    """JSON 數據存儲"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def save(self, data: SensorData,filename:str):
        try:
            new_entry = {
                "timestamp": data.timestamp.isoformat(),
                "rotationRoll": data.rotationRoll,
                "rotationPitch": data.rotationPitch,
                "direction": data.direction
            }

            # 讀取現有數據，然後追加
            try:
                with open(filename, 'r') as f:
                    entries = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                entries = []

            entries.append(new_entry)

            with open(filename, 'w') as f:
                json.dump(entries, f, indent=4)

        except Exception as e:
            self.logger.error(f"JSON storage error: {e}")
