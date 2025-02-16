import numpy as np
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow ,QVBoxLayout
from src.gui.ui_main import Ui_MainWindow  
from src.gui.qt_observer import QtGuiObserver
from src.gui.visualizers.line_chart import LineChartDrawer
from src.gui.visualizers.stage_display import StageDisplayer
from src.gui.visualizers.log_displayer import LogDisplayer
from src.gui.visualizers.visualization_tools import euler_to_quaternion
from src.gui.visualizers.attitude_displayer import AttitudeDisplayer, CubeGLWidget  
from src.core.communicator import SerialCommunicator
from src.core.models import SensorData

class MainWindow(QMainWindow):
    def __init__(self, serial_communicator: SerialCommunicator):
        super().__init__()
        self.angle_deviation = 0
        self.serial_communicator = serial_communicator
        self.latest_data = None
        self.quaternion = np.array([1.0, 0.0, 0.0, 0.0])  # w, x, y, z

        
        self.qt_observer = QtGuiObserver()
        self.qt_observer.signal_emitter.data_received.connect(self.update_ui)
        self.qt_observer.signal_emitter.error_occurred.connect(self.handle_error)

        self.serial_communicator.add_observer(self.qt_observer) 
        
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.init_gui()

        self.chart_1 = LineChartDrawer(self.ui.chart_widget_1,2,100)
        self.chart_2 = LineChartDrawer(self.ui.chart_widget_2,1,100,(0,360))

        self.stage_display = StageDisplayer(self.ui.listWidget)
        
        self.cube_widget = CubeGLWidget()
        self.ui.gl_gridLayout.addWidget(self.cube_widget)
        self.attitude_displayer = AttitudeDisplayer(self.cube_widget)

        self.ui.lineEdit.setPlaceholderText("Command-Line...")
        self.ui.lineEdit.returnPressed.connect(self.on_enter_pressed)
        
        self.log_display = LogDisplayer(self.ui.log_textEdit) 

        self.logger = logging.getLogger(__name__)

    def on_enter_pressed(self):
        text = self.ui.lineEdit.text()
        match text:
            case "reset-angle":
                self.angle_deviation = self.latest_data.direction
                self.ui.gl_label.setText(f"angle_deviation:{self.angle_deviation}")
                self.logger.info('Reset angle deviation successfully')
                self.ui.lineEdit.clear() 
            case _:
                self.logger.error('Unknown command')

    def init_gui(self):
        self.ui.version_label.setText("v1.0.0")
        self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Connecting')
        self.ui.chart_label_1.setText("rotationPitch&Roll")
        self.ui.chart_label_2.setText("direction")
        self.ui.chart_checkBox_1.setChecked(True)
        self.ui.chart_checkBox_2.setChecked(True)
        self.ui.chart_checkBox_3.setChecked(True)
        self.ui.gl_label.setText(f"angle_deviation:{self.angle_deviation}")
           
        self.ui.listWidget.clear()
        
    def handle_angle_change(self,):

    def update_ui(self, data: SensorData):
        self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Connecting')
        self.chart_1.update([data.rotationRoll,data.rotationPitch],self.ui.chart_checkBox_1.isChecked())
        self.chart_2.update([data.direction],self.ui.chart_checkBox_2.isChecked()) 

        # 處理角度，之後要用累積的方式
        self.quaternion = euler_to_quaternion(-data.rotationPitch, data.rotationRoll,180-((data.direction - self.angle_deviation+360)%360)) 
        self.attitude_displayer.update(self.quaternion)

        self.stage_display.update(data.stage,data.failedTasks) 
        self.latest_data = data
        
    
        
    def handle_error(self, error):
        # self.logger.error(error)
        if error == "disconnect":
            self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Disconnect')

if __name__ == "__main__":
    communicator = SerialCommunicator("COM3", 115200)
    app = QApplication([])
    window = MainWindow(communicator)
    window.show()
    app.exec()