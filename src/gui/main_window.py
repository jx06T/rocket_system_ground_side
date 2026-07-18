import numpy as np
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow ,QVBoxLayout
from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface

from src.gui.ui_main import Ui_MainWindow  
from src.gui.qt_observer import QtGuiObserver
from src.gui.visualizers.line_chart import LineChartDrawer
from src.gui.visualizers.stage_display import StageDisplayer
from src.gui.visualizers.log_displayer import LogDisplayer
from src.gui.visualizers.location_displayer import LocationDisplayer
from src.gui.visualizers.visualization_tools import euler_to_quaternion,quaternion_multiply
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
        self.ui.widget_3.layout().addWidget(QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL))
        self.init_gui()

        self.chart_1 = LineChartDrawer(self.ui.chart_widget_1,1,100)
        self.chart_2 = LineChartDrawer(self.ui.chart_widget_2,1,100)
        self.chart_3 = LineChartDrawer(self.ui.chart_widget_3,1,100,(0,360))

        self.stage_display = StageDisplayer(self.ui.listWidget)
        
        self.cube_widget = CubeGLWidget()
        self.ui.gl_gridLayout.addWidget(self.cube_widget)
        self.attitude_displayer = AttitudeDisplayer(self.cube_widget)

        self.ui.lineEdit.setPlaceholderText("Command-Line...")
        self.ui.lineEdit.returnPressed.connect(self.on_enter_pressed)
        
        self.location_displayer = LocationDisplayer(self.ui.map_widget)

        self.log_display = LogDisplayer(self.ui.log_textEdit) 

        self.logger = logging.getLogger(__name__)

    def on_enter_pressed(self):
        text = self.ui.lineEdit.text().strip()
        if not text:
            return
            
        self.ui.lineEdit.clear()
        
        if text.startswith("/"):
            parts = text.split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            if cmd == "/port":
                if not args:
                    self.logger.error("Usage: /port <PORT> (e.g. /port COM4)")
                    return
                new_port = args[0]
                self.logger.info(f"Switching serial port to {new_port}...")
                self.serial_communicator.stop()
                self.serial_communicator.port = new_port
                self.serial_communicator.start()
                self.logger.info(f"Serial port set to {new_port}. Reconnecting...")
            elif cmd == "/baud":
                if not args:
                    self.logger.error("Usage: /baud <BAUDRATE> (e.g. /baud 115200)")
                    return
                try:
                    new_baud = int(args[0])
                    self.logger.info(f"Switching baudrate to {new_baud}...")
                    self.serial_communicator.stop()
                    self.serial_communicator.baudrate = new_baud
                    self.serial_communicator.start()
                    self.logger.info(f"Baudrate set to {new_baud}. Reconnecting...")
                except ValueError:
                    self.logger.error("Invalid baudrate value. Must be an integer.")
            elif cmd == "/connect":
                self.logger.info("Reconnecting serial...")
                self.serial_communicator.stop()
                self.serial_communicator.start()
            elif cmd == "/disconnect":
                self.logger.info("Disconnecting serial...")
                self.serial_communicator.stop()
            elif cmd == "/reset-angle":
                if self.latest_data:
                    self.angle_deviation = self.latest_data.direction
                    self.ui.gl_label.setText(f"angle_deviation:{self.angle_deviation}")
                    self.logger.info('Reset angle deviation successfully')
                else:
                    self.logger.error('No data received yet, cannot reset angle')
            elif cmd == "/help":
                self.logger.info("Available terminal commands:")
                self.logger.info("  /port <PORT>      - Switch serial port (e.g. /port COM4)")
                self.logger.info("  /baud <BAUDRATE>  - Switch baudrate (e.g. /baud 115200)")
                self.logger.info("  /connect          - Start/Reconnect serial communication")
                self.logger.info("  /disconnect       - Stop serial communication")
                self.logger.info("  /reset-angle      - Reset IMU angle deviation")
            else:
                self.logger.error(f"Unknown terminal command: {cmd}")
        else:
            self.logger.error(f"Unknown command: {text}. Type /help for commands.")


    def init_gui(self):
        self.ui.version_label.setText("v1.0.5")
        self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Connecting')
        self.ui.chart_label_1.setText("rotation pitch")
        self.ui.chart_label_2.setText("rotation roll")
        self.ui.chart_label_3.setText("direction")
        self.ui.chart_checkBox_1.setChecked(True)
        self.ui.chart_checkBox_2.setChecked(True)
        self.ui.chart_checkBox_3.setChecked(True)
        self.ui.gl_label.setText(f"angle_deviation:{self.angle_deviation}")
     
        self.ui.listWidget.clear()
        
    def handle_angle_change(self,pitch: float, roll: float, yaw: float):
        yaw_quaternion = euler_to_quaternion(yaw, 0, 0)
        pitch_roll_quaternion = euler_to_quaternion(0, pitch, roll)
        quaternion = quaternion_multiply(yaw_quaternion,pitch_roll_quaternion)
        quaternion = quaternion / np.linalg.norm(quaternion)

        return quaternion


    def update_ui(self, data: SensorData):
        self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Connecting')
        self.ui.map_label.setText(f'Latitude:{round(data.location[0],4)}|Longitude:{round(data.location[1],4)}')

        self.chart_1.update([data.rotationPitch],self.ui.chart_checkBox_1.isChecked())
        self.chart_2.update([data.rotationRoll],self.ui.chart_checkBox_2.isChecked())
        self.chart_3.update([data.direction],self.ui.chart_checkBox_3.isChecked()) 

        self.quaternion = self.handle_angle_change(data.rotationRoll, -data.rotationPitch, 180-((data.direction-self.angle_deviation+360)%360))
        self.attitude_displayer.update(self.quaternion)

        self.stage_display.update(data.stage,data.failedTasks) 

        if self.latest_data and self.ui.map_checkBox.isChecked() and self.latest_data.location != data.location:
            self.location_displayer.update(self.latest_data.location)

        self.latest_data = data

    
        
    def handle_error(self, error):
        if error == "disconnect":
            self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Disconnect')

if __name__ == "__main__":
    communicator = SerialCommunicator("COM3", 115200)
    app = QApplication([])
    window = MainWindow(communicator)
    window.show()
    app.exec()