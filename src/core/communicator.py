import serial
import threading
import queue
import json
import logging
from datetime import datetime
from typing import List, Optional

from src.core.models import SensorData
from src.core.observer import DataObserver  
from src.storage.csv_storage import CsvDataStorage

class SerialCommunicator:
    def __init__(self, port: str, baudrate: int):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.running = False
        self.observers: List[DataObserver] = []
        self.data_queue = queue.Queue()
        self.logger = logging.getLogger(__name__)
        
        # 工作線程
        self.read_thread: Optional[threading.Thread] = None
        self.process_thread: Optional[threading.Thread] = None

    def add_observer(self, observer: DataObserver):
        self.observers.append(observer)

    def remove_observer(self, observer: DataObserver):
        self.observers.remove(observer)

    def _notify_observers(self, data: SensorData):
        for observer in self.observers:
            try:
                observer.on_data_received(data)
            except Exception as e:
                observer.on_error(e)
                self.logger.error(f"Observer error: {e}")

    def _read_serial(self):
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    data = self.serial.readline()
                    self.data_queue.put(data)
            except Exception as e:
                self.logger.error(f"Serial read error: {e}")
                for observer in self.observers:
                    observer.on_error(e)
                self._reconnect()

    def _process_data(self):
        while self.running:
            try:
                raw_data = self.data_queue.get(timeout=1)
                decoded_data = raw_data.decode().strip()

                # 假設數據是 JSON 格式
                try:
                    parsed_data = json.loads(decoded_data)
                    # print(f"Parsed data: {parsed_data}")  # 打印解析後的數據

                    rotationRoll = parsed_data.get('rotationRoll', 0)
                    rotationPitch = parsed_data.get('rotationPitch', 0)
                    direction = parsed_data.get('direction', 0)

                    sensor_data = SensorData(
                        timestamp=datetime.now(),
                        rotationRoll=rotationRoll,
                        rotationPitch=rotationPitch,
                        direction=direction
                    )
                                                            
                    self._notify_observers(sensor_data)

                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON format: {decoded_data}")
                except Exception as e:
                    self.logger.error(f"Data processing error: {e}")
                    for observer in self.observers:
                        observer.on_error(e)

            except queue.Empty:
                continue

    def _reconnect(self):
        """嘗試重新連接序列埠"""
        try:
            if self.serial:
                self.serial.close()
            self.serial = serial.Serial(self.port, self.baudrate)
            self.logger.info("Serial port reconnected")
        except Exception as e:
            self.logger.error(f"Reconnection failed: {e}")

    def start(self):
        """啟動通訊"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate)
            self.running = True
            
            self.read_thread = threading.Thread(target=self._read_serial)
            self.process_thread = threading.Thread(target=self._process_data)
            
            self.read_thread.start()
            self.process_thread.start()
            
            self.logger.info("Serial communication started")
        except Exception as e:
            self.logger.error(f"Failed to start serial communication: {e}")
            raise

    def stop(self):
        """停止通訊"""
        self.running = False
        if self.read_thread:
            self.read_thread.join()
        if self.process_thread:
            self.process_thread.join()
        if self.serial:
            self.serial.close()
        self.logger.info("Serial communication stopped")

