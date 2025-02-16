import serial
import threading
import queue
import json
import logging
import time
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
        self.max_retries = 10000 
        self.retry_interval = 5  

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

    def _reconnect(self):
        """嘗試重新連接序列埠"""
        for observer in self.observers:
            observer.on_error("disconnect")
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                if self.serial and self.serial.is_open:
                    self.serial.close()  
                self.serial = serial.Serial(self.port, self.baudrate, timeout=1)  
                self.logger.info("Serial port reconnected")
                return 
            except serial.SerialException as e:
                self.logger.error(f"Serial port error: {e}")
            except FileNotFoundError as e:
                self.logger.error(f"Reconnection failed: {e}")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error during reconnection: {e}")

            retry_count += 1
            self.logger.info(f"Retrying... ({retry_count}/{self.max_retries})")
            time.sleep(self.retry_interval) 


    def _read_serial(self):
        while self.running:
            try:
                if self.serial and self.serial.is_open and self.serial.in_waiting:
                    data = self.serial.readline()
                    self.data_queue.put(data)
                else :
                    if not self.serial or not self.serial.is_open:
                        self.logger.warning("Serial port is not open. Attempting to reconnect...")
                        self._reconnect()
                    else:
                        time.sleep(1)  

            except serial.SerialException as e:
                self.logger.error(f"Serial port error: {e}")
                self._reconnect()
                
            except Exception as e:
                self.logger.error(f"Serial read error: {e}")
                self._reconnect()
                for observer in self.observers:
                    observer.on_error(e)

    def _process_data(self):
        while self.running:
            try:
                raw_data = self.data_queue.get(timeout=1)
                decoded_data = raw_data.decode().strip()

                try:
                    parsed_data = json.loads(decoded_data)

                    sensor_data = SensorData.from_dict(parsed_data,datetime.now())
                                                            
                    self._notify_observers(sensor_data)

                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON format: {decoded_data}")
                except Exception as e:
                    self.logger.error(f"Data processing error: {e}")
                    for observer in self.observers:
                        observer.on_error(e)

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Data processing queue error: {e}")

    def start(self):
        """啟動通訊，並在未連線時持續嘗試重新連線"""
        self.running = True

        self.read_thread = threading.Thread(target=self._read_serial)
        self.process_thread = threading.Thread(target=self._process_data)

        self.read_thread.start()
        self.process_thread.start()

        self.logger.info("Serial communication started")

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

