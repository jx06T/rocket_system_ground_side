from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict,List,Tuple

# 數據模型
@dataclass
class SensorData:
    rotationRoll : float
    rotationPitch : float
    direction : float
    timestamp: datetime
    stage:int
    failedTasks:List[int]
    location:Tuple[float, float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any], timestamp: datetime = None) -> 'SensorData':
        """從 JSON 格式的字典創建 SensorData 物件"""
        try:
            return cls(
                rotationRoll=float(data['rotationRoll']),
                rotationPitch=float(data['rotationPitch']),
                direction=float(data['direction']),
                timestamp= data.get('timestamp') or timestamp or datetime.now(),
                stage=data.get('stage',0),
                failedTasks=data.get('failedTasks',[]),
                location = (data.get('location',[25,121.5])[0],data.get('location',[25,121.5])[1])
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
            "stage": self.stage,
            "failedTasks": self.failedTasks,
            "location": self.location,
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