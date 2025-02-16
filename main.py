import sys
import logging
from PyQt6.QtWidgets import QApplication
from src.core.communicator import SerialCommunicator
from src.gui.main_window import MainWindow
from src.storage.storage_observer import StorageObserver
# from src.gui.qt_observer import QtGuiObserver


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

    app = QApplication(sys.argv)

    logging.info("Initializing serial communication...")
    communicator = SerialCommunicator("COM3", 115200)
    
    # 數據存儲
    logging.info("Setting up storage observer...")
    logger_observer = StorageObserver("all_data")
    communicator.add_observer(logger_observer)

    # 啟動 GUI
    logging.info("Creating main window...")
    window = MainWindow(communicator)
    window.show()

    logging.info("Starting serial communication...")
    communicator.start()

    try:
        app.exec()
    finally:
        communicator.stop()

if __name__ == "__main__":
    main()
