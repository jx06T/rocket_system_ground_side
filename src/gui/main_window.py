import numpy as np
import logging
import threading
import math
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
        

        self.angle_deviation = 0.0
        
        # ─── 快速軸向對應設定區 (Sensor Axis Mapping Configuration) ───
        # 定義：[火箭本體標準軸向] ➔ [感測器原始軸向] (支援正負號，例如 "-ay"、"+ax" 等)
        # 標準本體定義：Z_body=縱向自旋軸, X_body=橫向俯仰軸, Y_body=橫向偏航軸
        self.axis_config = {
            "ax": "+ax",  # 火箭 X 軸對應的感測器資料 (用以推算 Pitch)
            "ay": "+ay",  # 火箭 Y 軸對應的感測器資料 (用以推算 Roll)
            "az": "+az",  # 火箭 Z 軸對應的感測器資料 (用以對齊重力)
            "gx": "+gx",  # 橫向俯仰角速度 (Pitch Rate)
            "gy": "+gy",  # 橫向偏航角速度 (Yaw Rate)
            "gz": "+gz"   # 縱向滾轉/自旋角速度 (Roll/Spin Rate)
        }
        
        self.serial_communicator = serial_communicator
        self.latest_data = None
        self.last_valid_location = None
        self.last_valid_location_time = None
        self.est_pitch = 0.0
        self.est_roll = 0.0
        self.est_yaw = 180.0
        
        # 陀螺儀零點偏置與滑動視窗歷史 (靜止校準用)
        self.gyro_bias_x = 0.0
        self.gyro_bias_y = 0.0
        self.gyro_bias_z = 0.0
        self.gyro_history = []
        
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
            {'label': 'Yaw 旋轉角(°)',   'color': (60, 220, 60),   'width': 2.0},
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
                    
                    # 1. 依據映射後的加速度讀值推算出當前對地角度作為濾波器初始值 (自動校準)
                    ax = self._get_mapped_axis(self.latest_data, "ax")
                    ay = self._get_mapped_axis(self.latest_data, "ay")
                    az = self._get_mapped_axis(self.latest_data, "az")
                    try:
                        roll_rad = math.atan2(ay, az)
                        pitch_rad = math.atan2(-ax, math.sqrt(ay**2 + az**2))
                        self.est_pitch = roll_rad * 180.0 / math.pi
                        self.est_roll = -pitch_rad * 180.0 / math.pi
                    except Exception:
                        self.est_pitch = 0.0
                        self.est_roll = 0.0
                    
                    # 垂直於地面的旋轉角度 (Yaw) 則重置回到正前方 (180.0)
                    self.est_yaw = 180.0
                    
                    # 2. 計算映射後的角速度均值作為靜態陀螺儀零點偏置 (Gyro Bias Calibration)
                    if self.gyro_history:
                        mapped_gyros = []
                        for h_data in self.gyro_history:
                            mgx = self._get_mapped_axis(h_data, "gx")
                            mgy = self._get_mapped_axis(h_data, "gy")
                            mgz = self._get_mapped_axis(h_data, "gz")
                            mapped_gyros.append((mgx, mgy, mgz))
                        
                        self.gyro_bias_x = sum(g[0] for g in mapped_gyros) / len(mapped_gyros)
                        self.gyro_bias_y = sum(g[1] for g in mapped_gyros) / len(mapped_gyros)
                        self.gyro_bias_z = sum(g[2] for g in mapped_gyros) / len(mapped_gyros)
                    else:
                        self.gyro_bias_x = self._get_mapped_axis(self.latest_data, "gx")
                        self.gyro_bias_y = self._get_mapped_axis(self.latest_data, "gy")
                        self.gyro_bias_z = self._get_mapped_axis(self.latest_data, "gz")
                    
                    self.ui.gl_label.setText(f"bias - Y:{round(self.angle_deviation,1)}")
                    self.logger.info(
                        f"Angles calibrated: Yaw reset to 180.0, Pitch gravity={self.est_pitch:.2f}, Roll gravity={self.est_roll:.2f}. "
                        f"Gyro Bias calibrated - X:{self.gyro_bias_x:.4f}, Y:{self.gyro_bias_y:.4f}, Z:{self.gyro_bias_z:.4f}"
                    )
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
        self.ui.map_checkBox.setChecked(True)
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
        self.chart_3.set_curve_visible(3, False)  # GX
        self.chart_3.set_curve_visible(4, False)  # GY
        self.chart_3.set_curve_visible(5, False)  # GZ

        self.ui.listWidget.clear()
        
    def _get_mapped_axis(self, data, key):
        """將 SensorData 的 raw 屬性依據 axis_config 對應轉換並套用正負號"""
        config_val = self.axis_config.get(key, f"+{key}")
        sign = -1.0 if config_val.startswith("-") else 1.0
        var_name = config_val.lstrip("+-")
        val = getattr(data, var_name, 0.0)
        return sign * val

    def handle_angle_change(self, pitch: float, roll: float, yaw: float):
        # euler_to_quaternion 參數對應：第一參數繞 Y 軸 (自旋/縱向), 第二參數繞 X 軸 (俯仰), 第三參數繞 Z 軸 (側向)
        # 1. 繞 Y 軸縱向自旋 (Roll / self-spin)
        spin_q = euler_to_quaternion(roll, 0, 0)
        # 2. 繞 X 軸橫向俯仰 (Pitch)
        pitch_q = euler_to_quaternion(0, pitch, 0)
        # 3. 繞 Z 軸側向傾斜 (Yaw-tilt)
        yaw_q = euler_to_quaternion(0, 0, yaw)
        
        # 組合旋轉：先自旋 ➔ 再俯仰 ➔ 最後套用側向偏航傾斜
        q_temp = quaternion_multiply(pitch_q, spin_q)
        quaternion = quaternion_multiply(yaw_q, q_temp)
        quaternion = quaternion / np.linalg.norm(quaternion)

        return quaternion


    def update_ui(self, data: SensorData):
        # 收集遙測數據歷史以供靜止校準計算陀螺儀偏置 (擷取幀數調長至 100 幀)
        self.gyro_history.append(data)
        if len(self.gyro_history) > 100:
            self.gyro_history.pop(0)

        # Flash the LED green (ON)
        self.rx_led.setStyleSheet("background-color: #00FF00; border-radius: 6px; border: 1px solid #00AA00;")
        self.led_timer.start(80) # Flash for 80ms

        self.ui.serial_label.setText(f'port︰{self.serial_communicator.port}｜baudrate︰{self.serial_communicator.baudrate}｜Status︰Connecting')
        
        # 檢查 GNSS 定位狀態
        has_fix = False
        if data.gnss_state:
            has_fix = "FIX" in data.gnss_state.upper() and "NO_FIX" not in data.gnss_state.upper()
        else:
            # 舊版 JSON 資料相容性檢查 (非預設值即視為有定位)
            has_fix = data.location != (25.0, 121.5) and data.location != (23.5, 121.5)

        if has_fix:
            self.last_valid_location = data.location
            self.last_valid_location_time = data.timestamp
            time_str = self.last_valid_location_time.strftime("%H:%M:%S")
            self.ui.map_label.setText(f'Latitude:{round(data.location[0],5)}|Longitude:{round(data.location[1],5)} (Locked, {time_str})')
            if self.ui.map_checkBox.isChecked():
                self.location_displayer.update(data.location)
        else:
            if self.last_valid_location:
                time_str = self.last_valid_location_time.strftime("%H:%M:%S")
                self.ui.map_label.setText(
                    f'Latitude:{round(self.last_valid_location[0],5)}|Longitude:{round(self.last_valid_location[1],5)} '
                    f'(Lost Lock - Last Update: {time_str})'
                )
            else:
                self.ui.map_label.setText('No Fix (No location data)')

        # 依軸向對應讀取並映射感測器數據，同時扣除靜止校準得到的陀螺儀零點偏置
        ax = self._get_mapped_axis(data, "ax")
        ay = self._get_mapped_axis(data, "ay")
        az = self._get_mapped_axis(data, "az")
        gx = self._get_mapped_axis(data, "gx") - self.gyro_bias_x
        gy = self._get_mapped_axis(data, "gy") - self.gyro_bias_y
        gz = self._get_mapped_axis(data, "gz") - self.gyro_bias_z

        # 基於映射後的對地重力向量計算 Roll / Pitch
        try:
            roll_rad = math.atan2(ay, az)
            pitch_rad = math.atan2(-ax, math.sqrt(ay**2 + az**2))
            body_roll_acc = roll_rad * 180.0 / math.pi
            body_pitch_acc = pitch_rad * 180.0 / math.pi
        except Exception:
            body_roll_acc = 0.0
            body_pitch_acc = 0.0

        # 計算 dt
        dt = 0.1
        if self.latest_data:
            dt = (data.timestamp - self.latest_data.timestamp).total_seconds()
            if data.timestamp_ms and self.latest_data.timestamp_ms:
                dt = (data.timestamp_ms - self.latest_data.timestamp_ms) / 1000.0
            # 限制合理區間以防通訊中斷造成數值暴增
            if dt <= 0 or dt > 1.0:
                dt = 0.1

        # 歐拉角姿態融合 (自適應互補濾波)
        # 計算總加速度大小 (單位為 g)
        total_acc = math.sqrt(ax**2 + ay**2 + az**2)
        acc_deviation = abs(total_acc - 1.0)
        
        # 動態調整互補濾波權重：當運動產生額外加速度時，降低對加速度計的信任，依靠陀螺儀積分
        if acc_deviation < 0.08:
            alpha = 0.05
        elif acc_deviation > 0.25:
            alpha = 0.0
        else:
            alpha = 0.05 * (1.0 - (acc_deviation - 0.08) / 0.17)
        
        # 如果是首幀，直接將估算值對齊感測器讀值
        if not self.latest_data:
            self.est_pitch = body_roll_acc
            self.est_roll = -body_pitch_acc
            self.est_yaw = 180 - ((data.direction - self.angle_deviation + 360) % 360)
        else:
            # 1. Pitch 估算 (對應橫向俯仰)：整合 X 軸陀螺儀 (gx) 並以加速度計 Roll 修正
            self.est_pitch = (1 - alpha) * (self.est_pitch + gx * dt) + alpha * body_roll_acc
            
            # 2. Roll 估算 (對應側向傾斜)：整合 Y 軸陀螺儀 (gy) 並以加速度計 Pitch 修正
            self.est_roll = (1 - alpha) * (self.est_roll - gy * dt) - alpha * body_pitch_acc
            
            # 3. Yaw 估算 (對應縱向自旋)：整合 Z 軸陀螺儀 (gz)，若有有效航向則以 target_yaw 修正
            target_yaw = 180 - ((data.direction - self.angle_deviation + 360) % 360)
            if data.direction != 0.0:
                self.est_yaw = (1 - alpha) * (self.est_yaw + gz * dt) + alpha * target_yaw
            else:
                self.est_yaw = (self.est_yaw + gz * dt) % 360

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
        # Chart 3：姿態角（Pitch, Roll, Yaw）與角速度（GX, GY, GZ）
        self.chart_3.update(
            [self.est_pitch, self.est_yaw - 180.0, self.est_roll, data.gx, data.gy, data.gz],
            auto_scroll=self.ui.chart_checkBox_3.isChecked()
        )

        self.quaternion = self.handle_angle_change(self.est_pitch, self.est_yaw, self.est_roll)
        self.attitude_displayer.update(self.quaternion)

        self.stage_display.update(data.stage,data.failedTasks) 

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