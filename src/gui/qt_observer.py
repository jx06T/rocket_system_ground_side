from PyQt6.QtCore import QObject, pyqtSignal
from src.core.observer import DataObserver
from src.core.models import SensorData


# Qt 信號發射器
class QtSignalEmitter(QObject):
    data_received = pyqtSignal(object)
    error_occurred = pyqtSignal(object)
    

class QtGuiObserver(DataObserver):
    def __init__(self):
        super().__init__() 
        self.signal_emitter = QtSignalEmitter()
        
    def on_data_received(self, data: SensorData):
        self.signal_emitter.data_received.emit(data)

    def on_error(self, error: Exception):
        self.signal_emitter.error_occurred.emit(error)
