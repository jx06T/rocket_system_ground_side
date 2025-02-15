from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

# 數據模型
@dataclass
class SensorData:
    rotationRoll : float
    rotationPitch : float
    direction : float
    timestamp: datetime

    @classmethod
    def from_dict(cls, data: Dict[str, float], timestamp: datetime = None) -> 'SensorData':
        """從 JSON 格式的字典創建 SensorData 物件"""
        try:
            return cls(
                rotationRoll=float(data['rotationRoll']),
                rotationPitch=float(data['rotationPitch']),
                direction=float(data['direction']),
                timestamp=data['timestamp'] or timestamp or datetime.now()
            )
        except KeyError as e:
            raise ValueError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValueError(f"Invalid data format: {e}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rotationRoll": self.rotationRoll,
            "rotationPitch": self.rotationPitch,
            "direction": self.direction,
            "timestamp": self.timestamp,
        }
@dataclass
class LogData:
    content : str
    timestamp: datetime

    @classmethod
    def new(cls, content:str, timestamp: datetime = None) -> 'LogData':
        """依照 content 創建 LogData 物件"""
        try:
            return cls(
                content=content,
                timestamp=timestamp or datetime.now()
            )
        except KeyError as e:
            raise ValueError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValueError(f"Invalid data format: {e}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "timestamp": self.timestamp,
        }