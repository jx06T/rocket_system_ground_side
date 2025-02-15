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

        self.chart_1 = LineChartDrawer(self.ui.chart_widget_1,2,100)
        self.chart_2 = LineChartDrawer(self.ui.chart_widget_2,1,100,(0,360))

    def init_gui(self):
        self.ui.version_label.setText("v1.0.0")
        self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Connecting')
        self.ui.chart_label_1.setText("rotationPitch&Roll")
        self.ui.chart_label_2.setText("direction")
        self.ui.chart_checkBox_1.setChecked(True)
        self.ui.chart_checkBox_2.setChecked(True)
        self.ui.chart_checkBox_3.setChecked(True)
           
        self.ui.listWidget.clear()
        stages = [
            "Pre-launch Preparation",
            "Ignition & Liftoff",
            "Ascent - 25% Altitude",
            "Ascent - 50% Altitude",
            "Ascent - 75% Altitude",
            "Apogee ",
            "Parachute Deployment",
            "Descent Altitude",
            "Landing"
        ]

        # 用 new_items 填充 listWidget
        self.ui.listWidget.addItems(stages)
        

    def update_ui(self, data: SensorData):
        self.chart_1.update_chart([data.rotationRoll,data.rotationPitch],self.ui.chart_checkBox_1.isChecked())
        self.chart_2.update_chart([data.direction],self.ui.chart_checkBox_2.isChecked()) 
        # print(data)
        
    def handle_error(self, error: Exception):
        print(error)        

if __name__ == "__main__":
    communicator = SerialCommunicator("COM3", 115200)
    app = QApplication([])
    window = MainWindow(communicator)
    window.show()
    app.exec()