import os
import sys
import argparse
import logging
import threading
import json
import time
from datetime import datetime
import zmq
import uuid

# 將專案根目錄加入路徑以支援導入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.communicator import SerialCommunicator
from src.core.lora_protocol import LoraProtocolHandler
from src.core.models import SensorData
from src.core.observer import DataObserver
from src.storage.storage_observer import StorageObserver
from src.utils.settings import load_channel_settings, save_channel_settings

class ZmqPublishObserver(DataObserver):
    """ZMQ 數據發布觀察者"""
    def __init__(self, zmq_port: int, topic: str):
        self.topic = topic
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://127.0.0.1:{zmq_port}")
        self.logger = logging.getLogger(f"ZmqPublishObserver_{topic}")
        self.logger.info(f"ZMQ PUB socket bound to port {zmq_port} for topic '{topic}'")

    def on_data_received(self, data: SensorData) -> None:
        if isinstance(data, SensorData):
            try:
                # 轉為字典並準備 JSON 傳輸
                data_dict = data.to_dict()
                
                # datetime 物件不支援 JSON 直接序列化，需轉換為 ISO 格式字串
                data_dict["timestamp"] = data.timestamp.isoformat()
                
                # 💡 打上地面站接收的高精度時間戳 (Ground Station Timestamp)
                data_dict["gs_timestamp"] = time.time()
                
                # ZMQ Multipart 封包傳輸 [Topic, Payload]
                self.socket.send_multipart([
                    self.topic.encode('utf-8'),
                    json.dumps(data_dict).encode('utf-8')
                ])
            except Exception as e:
                self.logger.error(f"Failed to publish data via ZMQ: {e}")

    def on_error(self, error: Exception):
        pass


class ZmqLogHandler(logging.Handler):
    """ZMQ 日誌轉發器：將後端進程中的日誌（如連線、重試日誌）封裝並透過 ZMQ PUB 發送至主介面"""
    def __init__(self, zmq_socket, topic: str):
        super().__init__()
        self.zmq_socket = zmq_socket
        self.topic = f"{topic}_log" # 例如 "ch1_log"

    def emit(self, record):
        try:
            log_entry = {
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name
            }
            self.zmq_socket.send_multipart([
                self.topic.encode('utf-8'),
                json.dumps(log_entry).encode('utf-8')
            ])
        except Exception:
            self.handleError(record)


def run_command_responder(zmq_cmd_port: int, communicator: SerialCommunicator, channel_id: str, storage_obs: StorageObserver = None):
    """ZMQ REP 控制通道端點，負責接收來自 GUI 的指令"""
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://127.0.0.1:{zmq_cmd_port}")
    logger = logging.getLogger(f"CommandResponder_{channel_id.upper()}")
    logger.info(f"ZMQ REP socket bound to port {zmq_cmd_port} for channel '{channel_id}'")

    lora_handler = LoraProtocolHandler(channel_id)

    while True:
        try:
            msg_bytes = socket.recv()
            msg = json.loads(msg_bytes.decode('utf-8'))
            cmd = msg.get("cmd")
            args = msg.get("args", [])
            logger.info(f"Received GUI command: {cmd} with args {args}")

            if cmd == "set_port":
                new_port = str(args[0])
                logger.info(f"Closing serial and switching port to {new_port}...")
                communicator.stop()
                communicator.port = new_port
                communicator.start()
                save_channel_settings(channel_id, new_port, communicator.baudrate)
                socket.send_json({"status": "ok"})
            elif cmd == "set_baud":
                new_baud = int(args[0])
                logger.info(f"Closing serial and switching baudrate to {new_baud}...")
                communicator.stop()
                communicator.baudrate = new_baud
                communicator.start()
                save_channel_settings(channel_id, communicator.port, new_baud)
                socket.send_json({"status": "ok"})
            elif cmd == "reconnect":
                logger.info("Manually reconnecting serial...")
                communicator.stop()
                communicator.start()
                socket.send_json({"status": "ok"})
            elif cmd == "disconnect":
                logger.info("Manually disconnecting serial...")
                communicator.stop()
                socket.send_json({"status": "ok"})
            elif cmd == "send_remote_cmd":
                action = str(args[0]).lower() if args else ""
                success, count, detail = lora_handler.send_command(communicator, action)
                if success:
                    socket.send_json({"status": "ok", "sent_times": count, "message": detail})
                else:
                    socket.send_json({"status": "error", "error": detail})
            elif cmd == "reset_session":
                new_run_id = uuid.uuid4().hex[:8]
                new_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_raw_log = f"data/raw_{channel_id}_{new_timestamp}_{new_run_id}.log"
                new_storage_prefix = f"data/{channel_id}_all_data_{new_timestamp}_{new_run_id}"

                communicator.raw_log_filepath = new_raw_log
                if storage_obs:
                    storage_obs.filename = new_storage_prefix

                logger.info(f"Session data reset! Saved previous session files. Created new CSV storage: {new_storage_prefix}_sensor.csv, raw log: {new_raw_log}")
                socket.send_json({"status": "ok", "new_prefix": new_storage_prefix, "new_raw_log": new_raw_log})
            else:
                logger.warning(f"Unknown command received: {cmd}")
                socket.send_json({"status": "error", "error": f"Unknown command: {cmd}"})

        except Exception as e:
            logger.error(f"Error handling controller message: {e}")
            try:
                socket.send_json({"status": "error", "error": str(e)})
            except Exception:
                pass


def watch_parent_stdin():
    """監聽父進程的 stdin，若關閉表示父進程已結束，後端自動退出（防禦性自毀）"""
    try:
        sys.stdin.read()
    except Exception:
        pass
    os._exit(0)

def main():
    parser = argparse.ArgumentParser(description="Ground Station Telemetry Daemon")
    parser.add_argument("--channel", type=str, default="ch1", choices=["ch1", "ch2"], help="Channel ID (ch1/ch2)")
    parser.add_argument("--port", type=str, default=None, help="Override Serial Port")
    parser.add_argument("--baud", type=int, default=None, help="Override Baudrate")
    parser.add_argument("--standalone", action="store_true", help="Run in standalone mode without parent process monitoring")
    args = parser.parse_args()

    # 💡 若非獨立運行模式，則啟動父進程自毀監聽執行緒，防止 GUI 崩潰時後端殘留導致 Port 被霸佔
    if not args.standalone:
        watcher_thread = threading.Thread(target=watch_parent_stdin, daemon=True)
        watcher_thread.start()

    channel_id = args.channel

    # 💡 產生每回執行的唯一 UUID 與時間戳，作為獨立日誌與 CSV 的識別檔名
    run_id = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    # 配置 logging 系統，將後端日誌統一收納至 logs/ 目錄中並帶有 session id
    log_filename = f"logs/backend_{channel_id}_{timestamp}_{run_id}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(f"Backend_{channel_id.upper()}")
    logger.info(f"Starting Ground Station Backend Daemon for {channel_id} (Session: {run_id})...")

    # 1. 載入通道設定
    saved_port, saved_baud, zmq_port, zmq_cmd_port = load_channel_settings(channel_id)
    port = args.port if args.port is not None else saved_port
    baudrate = args.baud if args.baud is not None else saved_baud

    # 2. 建立防禦性 Raw Log 儲存路徑 (納入 Session ID，存放在 data/ 之下)
    raw_log_filename = f"data/raw_{channel_id}_{timestamp}_{run_id}.log"
    logger.info(f"Raw telemetry output will be safely logged to: {raw_log_filename}")

    # 3. 初始化 Serial 通訊
    logger.info(f"Initializing serial link on port={port}, baud={baudrate}...")
    communicator = SerialCommunicator(port, baudrate)
    communicator.raw_log_filepath = raw_log_filename

    # 4. 註冊資料儲存觀察者 (CSV)，儲存於專屬 data/ 資料夾中並標註 Session ID
    storage_prefix = f"data/{channel_id}_all_data_{timestamp}_{run_id}"
    logger.info(f"Setting up storage observer with prefix: {storage_prefix}")
    storage_obs = StorageObserver(storage_prefix)
    communicator.add_observer(storage_obs)

    # 5. 註冊 ZMQ 發布觀察者
    zmq_pub_obs = ZmqPublishObserver(zmq_port, topic=channel_id)
    communicator.add_observer(zmq_pub_obs)

    # 💡 註冊 ZMQ 日誌轉發 Handler，用以將背景串列埠連接日誌傳回 GUI
    zmq_log_handler = ZmqLogHandler(zmq_pub_obs.socket, channel_id)
    logging.getLogger().addHandler(zmq_log_handler)

    # 6. 啟動 ZMQ REQ/REP 指令控制端點線程
    cmd_thread = threading.Thread(
        target=run_command_responder,
        args=(zmq_cmd_port, communicator, channel_id, storage_obs),
        daemon=True
    )
    cmd_thread.start()


    # 7. 啟動 Serial 通訊讀取背景執行緒
    communicator.start()

    # 8. 主程式守護，防止進程退出
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    finally:
        logger.info("Stopping communicator...")
        communicator.stop()
        logger.info("Backend daemon terminated successfully")

if __name__ == "__main__":
    main()
