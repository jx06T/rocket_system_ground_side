import logging
import json
import zmq
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.models import SensorData
from src.utils.settings import load_channel_settings

class ZmqReceiverThread(QThread):
    """
    ZMQ 遙測資料接收執行緒。
    在背景非阻塞地自一或多個通道訂閱數據，解密解析後透過 PyQt 信號發送回 GUI。
    """
    data_received = pyqtSignal(str, SensorData) # 傳遞 (topic/channel_id, SensorData)
    error_occurred = pyqtSignal(str)

    def __init__(self, channel_ids=None):
        super().__init__()
        if channel_ids is None:
            channel_ids = ["ch1"]
        self.channel_ids = channel_ids
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.logger.info(f"Starting ZmqReceiverThread for channels: {self.channel_ids}")
        context = zmq.Context()
        socket = context.socket(zmq.SUB)

        connected_any = False
        for ch in self.channel_ids:
            try:
                _, _, zmq_port, _ = load_channel_settings(ch)
                address = f"tcp://127.0.0.1:{zmq_port}"
                socket.connect(address)
                socket.setsockopt_string(zmq.SUBSCRIBE, "") # 訂閱所有 topic 訊息
                self.logger.info(f"ZmqReceiverThread connected to PUB: {address}")
                connected_any = True
            except Exception as e:
                self.logger.error(f"Failed to connect to channel {ch} PUB: {e}")

        if not connected_any:
            self.error_occurred.emit("No active ports found to connect to")
            return

         # 在 Socket 上設置接收超時時間 (200ms)，取代 Poller，避免 Windows 下 pyzmq.Poller.poll 發生記憶體存取衝突 (Access Violation)
        socket.setsockopt(zmq.RCVTIMEO, 200)

        while not self.isInterruptionRequested():
            try:
                topic_bytes, payload_bytes = socket.recv_multipart()
                topic = topic_bytes.decode('utf-8')
                payload_dict = json.loads(payload_bytes.decode('utf-8'))
                
                # 還原為 SensorData 物件
                sensor_data = SensorData.from_dict(payload_dict)
                self.data_received.emit(topic, sensor_data)
            except zmq.Again:
                # 超時未收到資料，繼續下一次迴圈以利響應 QThread 中斷要求
                continue
            except Exception as e:
                self.logger.error(f"Error in ZMQ receiver loop: {e}")
                self.error_occurred.emit(str(e))
                self.msleep(100) # 防止無限快速報錯擠滿日誌

        # 釋放資源
        try:
            socket.close()
            context.term()
        except Exception:
            pass
        self.logger.info("ZmqReceiverThread cleanly stopped")
