import serial
import threading
import queue
import json
import logging
import time
import re
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
        self.stop_event = threading.Event()
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

    def _format_error(self, e: Exception) -> str:
        err_str = str(e)
        prefix = f"could not open port '{self.port}': "
        if err_str.startswith(prefix):
            err_str = err_str[len(prefix):]
        
        # 匹配 Windows 的 OSError 格式，如 FileNotFoundError(2, '系統找不到指定的檔案。', None, 2)
        match = re.search(r"([a-zA-Z0-9_]+)\(\d+,\s*['\"]([^'\"]+)['\"]", err_str)
        if match:
            exception_name = match.group(1)
            error_msg = match.group(2)
            reason = f"{exception_name}: {error_msg}"
        else:
            reason = err_str

        return f"無法連線到 port '{self.port}' ({reason})"

    def _reconnect(self):
        """嘗試重新連接序列埠"""
        for observer in self.observers:
            observer.on_error("disconnect")
        retry_count = 0
        while retry_count < self.max_retries and self.running:
            try:
                if self.serial and self.serial.is_open:
                    self.serial.close()  
                self.serial = serial.Serial(self.port, self.baudrate, timeout=1)  
                self.logger.info("Serial port reconnected")
                return 
            except (serial.SerialException, FileNotFoundError) as e:
                self.logger.error(self._format_error(e))
            except Exception as e:
                self.logger.error(f"Unexpected error during reconnection: {e}")

            retry_count += 1
            self.logger.info(f"Retrying... ({retry_count}/{self.max_retries})")
            if self.stop_event.wait(self.retry_interval):
                break

    def _read_serial(self):
        while self.running:
            try:
                if self.serial and self.serial.is_open:
                    data = self.serial.readline()
                    if data:
                        self.data_queue.put(data)
                else:
                    self.logger.warning("Serial port is not open. Attempting to reconnect...")
                    self._reconnect()
                    if not self.serial or not self.serial.is_open:
                        self.stop_event.wait(self.retry_interval)

            except serial.SerialException as e:
                self.logger.error(self._format_error(e))
                self._reconnect()
                if not self.serial or not self.serial.is_open:
                    self.stop_event.wait(self.retry_interval)
                
            except Exception as e:
                self.logger.error(f"Serial read error: {e}")
                self._reconnect()
                if not self.serial or not self.serial.is_open:
                    self.stop_event.wait(self.retry_interval)
                for observer in self.observers:
                    observer.on_error(e)

    def _process_data(self):
        while self.running:
            try:
                raw_data = self.data_queue.get(timeout=1)
                decoded_data = raw_data.decode('utf-8', errors='ignore').strip()
                if not decoded_data:
                    continue

                sensor_data = None
                try:
                    # 1. 優先嘗試 JSON 格式
                    parsed_data = json.loads(decoded_data)
                    sensor_data = SensorData.from_dict(parsed_data, datetime.now())
                except (json.JSONDecodeError, TypeError, KeyError):
                    # 2. JSON 解析失敗，嘗試新版 ASCII 遙測格式
                    try:
                        sensor_data = SensorData.from_new_format(decoded_data, datetime.now())
                    except ValueError:
                        # 3. 兩者皆失敗，印出格式錯誤提示（限制預覽長度並轉義，防止白框）
                        preview = decoded_data[:30]
                        safe_preview = ascii(preview)
                        self.logger.error(f"Format error: Invalid data received (len={len(decoded_data)}): {safe_preview}...")
                        continue
                except Exception as e:
                    self.logger.error(f"Data processing error (JSON): {e}")

                if sensor_data:
                    try:
                        self._notify_observers(sensor_data)
                    except Exception as e:
                        self.logger.error(f"Observer notify error: {e}")
                        for observer in self.observers:
                            observer.on_error(e)

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Data processing queue error: {e}")

    def start(self):
        """啟動通訊，並在未連線時持續嘗試重新連線"""
        self.running = True
        self.stop_event.clear()

        self.read_thread = threading.Thread(target=self._read_serial)
        self.process_thread = threading.Thread(target=self._process_data)

        self.read_thread.start()
        self.process_thread.start()

        self.logger.info("Serial communication started")

    def stop(self):
        """停止通訊"""
        self.running = False
        self.stop_event.set()
        
        # 1. 先關閉序列埠，中斷 read_thread 中的 readline() 阻塞狀態，防止 Windows 死鎖 (Deadlock)
        if self.serial:
            try:
                self.serial.close()
            except Exception as e:
                self.logger.error(f"Error closing serial during stop: {e}")

        # 2. 安全等待線程退出
        if self.read_thread:
            self.read_thread.join()
        if self.process_thread:
            self.process_thread.join()
            
        self.logger.info("Serial communication stopped")


