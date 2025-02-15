import sys
from PyQt6.QtWidgets import QApplication
from src.core.communicator import SerialCommunicator
from src.gui.main_window import MainWindow
from src.storage.storage_observer import StorageObserver
# from src.gui.qt_observer import QtGuiObserver


def main():
    communicator = SerialCommunicator("COM3", 115200)
    
    # 數據存儲
    logger_observer = StorageObserver("all_data")
    communicator.add_observer(logger_observer)

    # logger_observer = QtGuiObserver()
    # communicator.add_observer(logger_observer)

    # 啟動通訊
    communicator.start()

    # 啟動 GUI
    app = QApplication(sys.argv)
    window = MainWindow(communicator)
    window.show()

    try:
        app.exec()
    finally:
        communicator.stop()

if __name__ == "__main__":
    main()
