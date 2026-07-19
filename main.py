import sys
import os
import logging
import subprocess
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow

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

    # 💡 啟動無頭背景 Telemetry Daemon 行程 (預設啟動 ch1)
    backend_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "backend_daemon.py")
    logging.info(f"Spawning backend daemon process: {backend_script}")
    
    backend_process = None
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
