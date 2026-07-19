import numpy as np
import logging
import threading
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QCheckBox, QLabel
from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface
from PyQt6.QtCore import QTimer

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
from src.utils.settings import save_settings

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
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)

        # Chart 1：高度與速度
        self.chart_1 = LineChartDrawer(self.ui.chart_widget_1, window_width=200, curve_configs=[
            {'label': 'KH 融合高度(m)', 'color': (0, 180, 80),    'width': 2.0},
            {'label': 'RH 相對高度(m)', 'color': (230, 140, 0),   'width': 1.5},
            {'label': 'VZ 垂直速度(m/s)', 'color': (60, 120, 220), 'width': 1.5},
        ])
        # Chart 2：動力加速度
        self.chart_2 = LineChartDrawer(self.ui.chart_widget_2, window_width=200, curve_configs=[
            {'label': 'GA 合加速度(g)', 'color': (0, 180, 80),    'width': 3.0},
            {'label': 'AX (g)',         'color': (220, 60, 60),   'width': 1.5},
            {'label': 'AY (g)',         'color': (60, 120, 220),  'width': 1.5},
            {'label': 'AZ (g)',         'color': (230, 140, 0),   'width': 1.5},
        ])
        # Chart 3：姿態與角速度
        self.chart_3 = LineChartDrawer(self.ui.chart_widget_3, window_width=200, curve_configs=[
            {'label': 'Pitch 俯仰角(°)', 'color': (60, 120, 220),  'width': 2.0},
            {'label': 'Roll 滾轉角(°)',  'color': (220, 60, 60),   'width': 2.0},
            {'label': 'GX 角速度(°/s)', 'color': (0, 200, 200),   'width': 1.0},
            {'label': 'GY 角速度(°/s)', 'color': (200, 0, 200),   'width': 1.0},
            {'label': 'GZ 角速度(°/s)', 'color': (180, 180, 0),   'width': 1.0},
        ])

        self.init_gui()

        self.stage_display = StageDisplayer(self.ui.listWidget)
        
        self.cube_widget = CubeGLWidget()
        self.ui.gl_gridLayout.addWidget(self.cube_widget)
        self.attitude_displayer = AttitudeDisplayer(self.cube_widget)

        self.ui.lineEdit.setPlaceholderText("Command-Line...")
        self.ui.lineEdit.returnPressed.connect(self.on_enter_pressed)
        
        self.location_displayer = LocationDisplayer(self.ui.map_widget)

        self.log_display = LogDisplayer(self.ui.log_textEdit) 

        # Create a receiver status LED (circle)
        self.rx_led = QLabel()
        self.rx_led.setFixedSize(12, 12)
        self.rx_led.setStyleSheet("background-color: #555555; border-radius: 6px;") # Grey (OFF)
        self.ui.horizontalLayout_4.insertWidget(0, self.rx_led)
        
        # Single-shot timer to turn off LED
        self.led_timer = QTimer()
        self.led_timer.setSingleShot(True)
        self.led_timer.timeout.connect(self._turn_off_led)

        self.logger = logging.getLogger(__name__)

    def _turn_off_led(self):
        # Set back to grey (OFF)
        self.rx_led.setStyleSheet("background-color: #555555; border-radius: 6px;")

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
                
                def run_port_switch():
                    self.serial_communicator.stop()
                    self.serial_communicator.port = new_port
                    self.serial_communicator.start()
                    self.logger.info(f"Serial port set to {new_port}. Reconnecting...")
                    save_settings(new_port, self.serial_communicator.baudrate)
                
                threading.Thread(target=run_port_switch, daemon=True).start()
            elif cmd == "/baud":
                if not args:
                    self.logger.error("Usage: /baud <BAUDRATE> (e.g. /baud 115200)")
                    return
                try:
                    new_baud = int(args[0])
                    self.logger.info(f"Switching baudrate to {new_baud}...")
                    
                    def run_baud_switch():
                        self.serial_communicator.stop()
                        self.serial_communicator.baudrate = new_baud
                        self.serial_communicator.start()
                        self.logger.info(f"Baudrate set to {new_baud}. Reconnecting...")
                        save_settings(self.serial_communicator.port, new_baud)
                    
                    threading.Thread(target=run_baud_switch, daemon=True).start()
                except ValueError:
                    self.logger.error("Invalid baudrate value. Must be an integer.")
            elif cmd == "/connect":
                self.logger.info("Reconnecting serial...")
                threading.Thread(
                    target=lambda: (self.serial_communicator.stop(), self.serial_communicator.start()),
                    daemon=True
                ).start()
            elif cmd == "/disconnect":
                self.logger.info("Disconnecting serial...")
                threading.Thread(target=self.serial_communicator.stop, daemon=True).start()
            elif cmd == "/reset-angle":
                if self.latest_data:
                    self.angle_deviation = self.latest_data.direction
                    self.ui.gl_label.setText(f"angle_deviation:{self.angle_deviation}")
                    self.logger.info('Reset angle deviation successfully')
                else:
                    self.logger.error('No data received yet, cannot reset angle')
            elif cmd == "/help":
                help_msg = (
                    "Available terminal commands:\n"
                    "  /port <PORT>      - Switch serial port (e.g. /port COM4)\n"
                    "  /baud <BAUDRATE>  - Switch baudrate (e.g. /baud 115200)\n"
                    "  /connect          - Start/Reconnect serial communication\n"
                    "  /disconnect       - Stop serial communication\n"
                    "  /reset-angle      - Reset IMU angle deviation"
                )
                self.logger.info(help_msg)
            else:
                self.logger.error(f"Unknown terminal command: {cmd}")
        else:
            self.logger.error(f"Unknown command: {text}. Type /help for commands.")


    def _add_curve_checkboxes(self, layout, chart, curve_labels: list, default_visible: list):
        """在指定 layout 中動態插入每條曲線的勾選框，插入在 Auto 勾選框之前。"""
        # 找到 Auto 勾選框的位置（layout 的最後一個 widget）
        insert_pos = layout.count() - 1
        for i, label in enumerate(curve_labels):
            cb = QCheckBox(label)
            cb.setChecked(default_visible[i])
            # 使用預設參數捕捉 i 與 chart，避免閉包陷阱
            cb.stateChanged.connect(
                lambda state, idx=i, ch=chart: ch.set_curve_visible(idx, state == 2)
            )
            layout.insertWidget(insert_pos + i, cb)

    def init_gui(self):
        self.ui.version_label.setText("v1.0.5")
        self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Connecting')
        # 更新圖表標題
        self.ui.chart_label_1.setText("高度與速度")
        self.ui.chart_label_2.setText("動力加速度")
        self.ui.chart_label_3.setText("姿態角速度")
        # Auto 捲動開關預設啟用
        self.ui.chart_checkBox_1.setChecked(True)
        self.ui.chart_checkBox_2.setChecked(True)
        self.ui.chart_checkBox_3.setChecked(True)
        self.ui.gl_label.setText(f"angle_deviation:{self.angle_deviation}")

        # 動態插入各圖表的曲線勾選框 (暫時隱藏，因為使用者可以直接操作圖例)
        # self._add_curve_checkboxes(
        #     self.ui.horizontalLayout_5, self.chart_1,
        #     ['KH', 'RH', 'VZ'],
        #     [True, True, True]
        # )
        # self._add_curve_checkboxes(
        #     self.ui.horizontalLayout_7, self.chart_2,
        #     ['GA', 'AX', 'AY', 'AZ'],
        #     [True, True, False, False]  # 預設只顯示 GA 和 AX
        # )
        # self._add_curve_checkboxes(
        #     self.ui.horizontalLayout_8, self.chart_3,
        #     ['Pitch', 'Roll', 'GX', 'GY', 'GZ'],
        #     [True, True, False, False, False]  # 預設只顯示姿態角
        # )
        # 初始化時同步非預設可見的曲線狀態
        self.chart_2.set_curve_visible(2, False)  # AY
        self.chart_2.set_curve_visible(3, False)  # AZ
        self.chart_3.set_curve_visible(2, False)  # GX
        self.chart_3.set_curve_visible(3, False)  # GY
        self.chart_3.set_curve_visible(4, False)  # GZ

        self.ui.listWidget.clear()
        
    def handle_angle_change(self,pitch: float, roll: float, yaw: float):
        yaw_quaternion = euler_to_quaternion(yaw, 0, 0)
        pitch_roll_quaternion = euler_to_quaternion(0, pitch, roll)
        quaternion = quaternion_multiply(yaw_quaternion,pitch_roll_quaternion)
        quaternion = quaternion / np.linalg.norm(quaternion)

        return quaternion


    def update_ui(self, data: SensorData):
        # Flash the LED green (ON)
        self.rx_led.setStyleSheet("background-color: #00FF00; border-radius: 6px; border: 1px solid #00AA00;")
        self.led_timer.start(80) # Flash for 80ms

        self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Connecting')
        self.ui.map_label.setText(f'Latitude:{round(data.location[0],4)}|Longitude:{round(data.location[1],4)}')

        # Chart 1：高度（融合高度 KH、相對高度 RH）與垂直速度（VZ）
        self.chart_1.update(
            [data.kfh_height, data.rel_height, data.vz],
            auto_scroll=self.ui.chart_checkBox_1.isChecked()
        )
        # Chart 2：合加速度（GA）與三軸加速度（AX, AY, AZ）
        self.chart_2.update(
            [data.total_accel, data.ax, data.ay, data.az],
            auto_scroll=self.ui.chart_checkBox_2.isChecked()
        )
        # Chart 3：姿態角（Pitch, Roll）與角速度（GX, GY, GZ）
        self.chart_3.update(
            [data.rotationPitch, data.rotationRoll, data.gx, data.gy, data.gz],
            auto_scroll=self.ui.chart_checkBox_3.isChecked()
        )

        self.quaternion = self.handle_angle_change(data.rotationRoll, -data.rotationPitch, 180-((data.direction-self.angle_deviation+360)%360))
        self.attitude_displayer.update(self.quaternion)

        self.stage_display.update(data.stage,data.failedTasks) 

        if self.latest_data and self.ui.map_checkBox.isChecked() and self.latest_data.location != data.location:
            self.location_displayer.update(self.latest_data.location)

        self.latest_data = data

    
        
    def handle_error(self, error):
        if error == "disconnect":
            self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Disconnect')
            # Turn LED red when disconnected
            self.rx_led.setStyleSheet("background-color: #FF0000; border-radius: 6px; border: 1px solid #AA0000;")

if __name__ == "__main__":
    communicator = SerialCommunicator("COM3", 115200)
    app = QApplication([])
    window = MainWindow(communicator)
    window.show()
    app.exec()