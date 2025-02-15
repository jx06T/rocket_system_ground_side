from PyQt6.QtWidgets import QApplication, QMainWindow 
from src.gui.ui_main import Ui_MainWindow  
from src.gui.qt_observer import QtGuiObserver
from src.gui.visualizers.line_chart import LineChartDrawer
from src.core.communicator import SerialCommunicator
from src.core.models import SensorData

class MainWindow(QMainWindow):
    def __init__(self, serial_communicator: SerialCommunicator):
        super().__init__()
        self.serial_communicator = serial_communicator
        
        self.qt_observer = QtGuiObserver()
        self.qt_observer.signal_emitter.data_received.connect(self.update_ui)
        self.qt_observer.signal_emitter.error_occurred.connect(self.handle_error)

        self.serial_communicator.add_observer(self.qt_observer) 
        
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.init_gui()

        self.chart_1 = LineChartDrawer(self.ui.graphicsView)
        self.chart_2 = LineChartDrawer(self.ui.graphicsView_3)

    def init_gui(self):
        self.ui.label_4.setText("v1.0.0")
        self.ui.label_5.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Connecting')

    def update_ui(self, data: SensorData):
        self.chart_1.update_chart(data.rotationPitch)
        self.chart_2.update_chart(data.rotationRoll) 
        # print(data)
        
    def handle_error(self, error: Exception):
        print(error)        

if __name__ == "__main__":
    communicator = SerialCommunicator("COM3", 115200)
    app = QApplication([])
    window = MainWindow(communicator)
    window.show()
    app.exec()