import sys
import os
import logging
import subprocess
import argparse
import socket
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
from src.utils.settings import load_channel_settings

def setup_logging():
    # 創建基礎配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            # 同時輸出到文件和控制台
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )
    
    # 獲取 root logger
    logger = logging.getLogger()
    logger.info("Logging system initialized")
    
def main():
    setup_logging()

    # 解析命令列參數 (使用 parse_known_args 避免干擾 PyQt6 的參數)
    parser = argparse.ArgumentParser(description="Ground Station GUI Launcher")
    parser.add_argument("--gui-only", action="store_true", help="Launch GUI only without starting backend daemon")
    args, unknown = parser.parse_known_args()

    # 檢查預設通道 ch1 的 ZMQ 連接埠是否已被佔用
    _, _, zmq_port, zmq_cmd_port = load_channel_settings("ch1")
    backend_already_running = False
    for port in [zmq_port, zmq_cmd_port]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
            except socket.error:
                backend_already_running = True
                break

    backend_process = None
    if args.gui_only:
        logging.info("GUI-only mode requested. Skipping backend daemon spawn.")
    elif backend_already_running:
        logging.info(f"ZMQ port {zmq_port} or {zmq_cmd_port} is already in use. Assuming backend daemon is already running. Skipping spawn.")
    else:
        # 💡 啟動無頭背景 Telemetry Daemon 行程 (預設啟動 ch1)
        backend_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "backend_daemon.py")
        logging.info(f"Spawning backend daemon process: {backend_script}")
        try:
            backend_process = subprocess.Popen(
                [sys.executable, backend_script, "--channel", "ch1"],
                stdin=subprocess.PIPE,
                stdout=None, # 保留標準輸出供調試
                stderr=None
            )
        except Exception as e:
            logging.error(f"Failed to spawn backend daemon process: {e}")
            sys.exit(1)


    try:
        app = QApplication(sys.argv)

        # 啟動 GUI (傳入通道 ch1)
        logging.info("Creating main window...")
        window = MainWindow(["ch1"])
        window.show()

        app.exec()
    except Exception as e:
        logging.exception("FATAL ERROR IN GUI INITIATION OR RUNTIME:")
        sys.exit(1)
    finally:
        if backend_process:
            logging.info("GUI exited. Terminating backend daemon process...")
            try:
                backend_process.terminate()
                backend_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                logging.warning("Backend daemon did not terminate in time. Killing it...")
                backend_process.kill()
            except Exception as ex:
                logging.error(f"Error cleaning up backend process: {ex}")

if __name__ == "__main__":
    main()
