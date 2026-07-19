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
import zmq
import time
import json
from src.core.models import SensorData
from src.utils.settings import load_channel_settings, save_channel_settings

class MainWindow(QMainWindow):
    def __init__(self, channel_ids=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.angle_deviation = 0.0
        self.max_total_accel = 0.0
        self.max_deviation_angle = 0.0
        self.calib_q = None
        
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
        if channel_ids is None:
            channel_ids = ["ch1"]
        elif not isinstance(channel_ids, list):
            # 相容性包裝：若傳入的是 SerialCommunicator 或是其他型別，就用預設的 ch1
            channel_ids = ["ch1"]
        self.channel_ids = channel_ids

        # 載入通訊通道的序列埠與 ZMQ 埠設定
        self.channel_configs = {}
        for ch in self.channel_ids:
            port, baud, zmq_port, zmq_cmd_port = load_channel_settings(ch)
            self.channel_configs[ch] = {
                "port": port,
                "baud": baud,
                "zmq_port": zmq_port,
                "zmq_cmd_port": zmq_cmd_port
            }
        
        self.focus_channel = "ch1"
        self.start_time = time.time()
        self.last_recv_time = {ch: None for ch in self.channel_ids}

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

        # 💡 在主執行緒中直接建立 ZMQ SUB Socket 進行非阻塞輪詢，避免 Windows 下 QThread 與 Chromium Winsock 發生 Access Violation 記憶體衝突
        self.zmq_context = zmq.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.SUB)
        
        connected_any = False
        for ch in self.channel_ids:
            try:
                _, _, zmq_port, _ = load_channel_settings(ch)
                address = f"tcp://127.0.0.1:{zmq_port}"
                self.zmq_socket.connect(address)
                self.zmq_socket.setsockopt_string(zmq.SUBSCRIBE, "")
                self.logger.info(f"Main thread connected to ZMQ PUB: {address}")
                connected_any = True
            except Exception as e:
                self.logger.error(f"Failed to connect to ZMQ PUB for channel {ch}: {e}")

        # 啟動 100Hz (10ms) 非阻塞資料輪詢定時器
        self.zmq_poll_timer = QTimer(self)
        self.zmq_poll_timer.timeout.connect(self.poll_zmq_data)
        self.zmq_poll_timer.start(10)

        # 啟動 5Hz 心跳偵測定時器
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self.check_heartbeats)
        self.heartbeat_timer.start(200) 
        
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

    def send_backend_command(self, cmd: str, args: list) -> bool:
        """透過 ZMQ REQ 槽向後端 Daemon 發送控制命令 (具備超時機制防死鎖)"""
        focus_ch = self.focus_channel
        cfg = self.channel_configs.get(focus_ch)
        if not cfg:
            self.logger.error("No active config for focus channel")
            return False

        zmq_cmd_port = cfg.get("zmq_cmd_port")
        self.logger.info(f"Sending command '{cmd}' to backend daemon of {focus_ch} on port {zmq_cmd_port}...")

        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.RCVTIMEO, 1000) # 1000 毫秒接收超時
        socket.setsockopt(zmq.SNDTIMEO, 1000) # 1000 毫秒傳送超時
        socket.connect(f"tcp://127.0.0.1:{zmq_cmd_port}")

        try:
            socket.send_json({"cmd": cmd, "args": args})
            reply = socket.recv_json()
            if reply.get("status") == "ok":
                self.logger.info(f"Command '{cmd}' executed successfully by backend.")
                return True
            else:
                error_msg = reply.get("error", "Unknown error")
                self.logger.error(f"Backend failed command '{cmd}': {error_msg}")
                return False
        except zmq.error.Again:
            self.logger.error(f"Backend command '{cmd}' timed out! Is the daemon running?")
            return False
        except Exception as e:
            self.logger.error(f"ZMQ command channel error: {e}")
            return False
        finally:
            try:
                socket.close()
                context.term()
            except Exception:
                pass

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
                self.logger.info(f"Requesting backend to switch port to {new_port}...")
                
                def run_port_switch():
                    success = self.send_backend_command("set_port", [new_port])
                    if success:
                        self.channel_configs[self.focus_channel]["port"] = new_port
                        self.logger.info(f"GUI updated focus port to {new_port}")
                
                threading.Thread(target=run_port_switch, daemon=True).start()
            elif cmd == "/baud":
                if not args:
                    self.logger.error("Usage: /baud <BAUDRATE> (e.g. /baud 115200)")
                    return
                try:
                    new_baud = int(args[0])
                    self.logger.info(f"Requesting backend to switch baudrate to {new_baud}...")
                    
                    def run_baud_switch():
                        success = self.send_backend_command("set_baud", [new_baud])
                        if success:
                            self.channel_configs[self.focus_channel]["baud"] = new_baud
                            self.logger.info(f"GUI updated focus baudrate to {new_baud}")
                    
                    threading.Thread(target=run_baud_switch, daemon=True).start()
                except ValueError:
                    self.logger.error("Invalid baudrate value. Must be an integer.")
            elif cmd == "/connect":
                self.logger.info("Requesting backend to reconnect serial...")
                threading.Thread(
                    target=lambda: self.send_backend_command("reconnect", []),
                    daemon=True
                ).start()
            elif cmd == "/disconnect":
                self.logger.info("Requesting backend to disconnect serial...")
                threading.Thread(
                    target=lambda: self.send_backend_command("disconnect", []),
                    daemon=True
                ).start()
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
                    
                    self.calib_q = self.handle_angle_change(self.est_pitch, self.est_yaw, self.est_roll)
                    self.max_deviation_angle = 0.0
                    self.max_total_accel = 0.0
                    self.ui.gl_label.setText(
                        f"當前偏角: 0.0° | 最大偏角: 0.0° (校正偏置 Y: {round(self.angle_deviation, 1)}°)"
                    )
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
        cfg = self.channel_configs.get(self.focus_channel, {})
        port = cfg.get("port", "N/A")
        baud = cfg.get("baud", "N/A")
        self.ui.serial_label.setText(f'port︰{port}｜baudrate︰{baud}｜Status︰Connecting')
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

    def get_deviation_angle(self, q1, q2):
        """計算兩個四元數代表的縱向 Y 軸方向向量之間的 3D 偏航夾角 (度)"""
        if q1 is None or q2 is None:
            return 0.0
        # 縱向指向在相對於四元數旋轉後的單位向量公式為 R * [0, 1, 0]^T
        # 即旋轉矩陣 R 的第二列 (Y列):
        # vx = 2 * (x*y - w*z)
        # vy = 1 - 2*(x*x + z*z)
        # vz = 2 * (y*z + w*x)
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        
        # 確保單位四元數
        n1 = math.sqrt(w1*w1 + x1*x1 + y1*y1 + z1*z1)
        if n1 > 0:
            w1, x1, y1, z1 = w1/n1, x1/n1, y1/n1, z1/n1
        n2 = math.sqrt(w2*w2 + x2*x2 + y2*y2 + z2*z2)
        if n2 > 0:
            w2, x2, y2, z2 = w2/n2, x2/n2, y2/n2, z2/n2

        v1x = 2.0 * (x1 * y1 - w1 * z1)
        v1y = 1.0 - 2.0 * (x1 * x1 + z1 * z1)
        v1z = 2.0 * (y1 * z1 + w1 * x1)

        v2x = 2.0 * (x2 * y2 - w2 * z2)
        v2y = 1.0 - 2.0 * (x2 * x2 + z2 * z2)
        v2z = 2.0 * (y2 * z2 + w2 * x2)

        # 點積求夾角
        dot = v1x * v2x + v1y * v2y + v1z * v2z
        dot = max(-1.0, min(1.0, dot))
        return math.degrees(math.acos(dot))

    def update_ui(self, data: SensorData):
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
            self.calib_q = self.handle_angle_change(self.est_pitch, self.est_yaw, self.est_roll)
            self.max_deviation_angle = 0.0
            self.max_total_accel = data.total_accel
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

        # 💡 使用地面站接收的高精度相對時間軸 X
        x_val = data.gs_timestamp - self.start_time

        # Chart 1：高度（融合高度 KH、相對高度 RH）與垂直速度（VZ）
        self.chart_1.update(
            [data.kfh_height, data.rel_height, data.vz],
            auto_scroll=self.ui.chart_checkBox_1.isChecked(),
            x_value=x_val
        )
        # Chart 2：合加速度（GA）與三軸加速度（AX, AY, AZ）
        self.chart_2.update(
            [data.total_accel, data.ax, data.ay, data.az],
            auto_scroll=self.ui.chart_checkBox_2.isChecked(),
            x_value=x_val
        )
        # Chart 3：姿態角（Pitch, Roll, Yaw）與角速度（GX, GY, GZ）
        self.chart_3.update(
            [self.est_pitch, self.est_yaw - 180.0, self.est_roll, data.gx, data.gy, data.gz],
            auto_scroll=self.ui.chart_checkBox_3.isChecked(),
            x_value=x_val
        )

        self.quaternion = self.handle_angle_change(self.est_pitch, self.est_yaw, self.est_roll)
        self.attitude_displayer.update(self.quaternion)

        if self.calib_q is None:
            self.calib_q = self.quaternion

        self.max_total_accel = max(self.max_total_accel, data.total_accel)
        current_dev = self.get_deviation_angle(self.quaternion, self.calib_q)
        self.max_deviation_angle = max(self.max_deviation_angle, current_dev)

        # 動態更新圖表上方標籤顯示具體數值
        self.ui.chart_label_1.setText(
            f"高度與速度 | 當前高度: {data.kfh_height:.1f} m (相對: {data.rel_height:.1f} m) | 垂直速度: {data.vz:.1f} m/s"
        )
        self.ui.chart_label_2.setText(
            f"動力加速度 | 當前總加速度: {data.total_accel:.2f} g | 最大總加速度: {self.max_total_accel:.2f} g"
        )
        self.ui.chart_label_3.setText(
            f"姿態角速度 | Pitch: {self.est_pitch:.1f}° | Roll: {self.est_roll:.1f}° | Yaw: {(self.est_yaw - 180.0):.1f}°"
        )
        self.ui.gl_label.setText(
            f"當前偏角: {current_dev:.1f}° | 最大偏角: {self.max_deviation_angle:.1f}° (校正偏置 Y: {round(self.angle_deviation, 1)}°)"
        )

        self.stage_display.update(data.stage, data.failedTasks, data.timestamp) 

        self.latest_data = data

    def update_ui_from_zmq(self, topic: str, data: SensorData):
        """ZMQ 資料接收槽，會更新心跳時間戳並視焦點分發"""
        self.last_recv_time[topic] = time.time()
        if topic == self.focus_channel:
            # 💡 隨遙測資料接收閃爍綠燈，並重置定時器
            self.rx_led.setStyleSheet("background-color: #00FF00; border-radius: 6px; border: 1px solid #00AA00;")
            self.led_timer.start(100) # 100ms 後自動呼叫 _turn_off_led 變回灰色
            self.update_ui(data)

    def check_heartbeats(self):
        """定期 (5Hz) 檢查通道接收心跳並刷新狀態 LED 與顯示字串"""
        now = time.time()
        focus_ch = self.focus_channel
        last_time = self.last_recv_time.get(focus_ch)
        
        cfg = self.channel_configs.get(focus_ch, {})
        port = cfg.get("port", "N/A")
        baud = cfg.get("baud", "N/A")
        
        if last_time is None:
            self.ui.serial_label.setText(f"port︰{port}｜baudrate︰{baud}｜Status︰No Data")
            self.rx_led.setStyleSheet("background-color: #FF0000; border-radius: 6px; border: 1px solid #AA0000;")
        else:
            elapsed = now - last_time
            if elapsed < 1.5:
                # 正常綠燈
                self.ui.serial_label.setText(f"port︰{port}｜baudrate︰{baud}｜Status︰Connected ({elapsed:.1f}s ago)")
                self.rx_led.setStyleSheet("background-color: #00FF00; border-radius: 6px; border: 1px solid #00AA00;")
            elif elapsed < 5.0:
                # 遲滯閃爍橘色
                self.ui.serial_label.setText(f"port︰{port}｜baudrate︰{baud}｜Status︰Stale ({elapsed:.1f}s ago)")
                if int(now * 5) % 2 == 0:
                    self.rx_led.setStyleSheet("background-color: #FFA500; border-radius: 6px; border: 1px solid #CC8400;")
                else:
                    self.rx_led.setStyleSheet("background-color: #555555; border-radius: 6px;")
            else:
                # 斷線紅燈
                self.ui.serial_label.setText(f"port︰{port}｜baudrate︰{baud}｜Status︰Lost ({elapsed:.1f}s ago)")
                self.rx_led.setStyleSheet("background-color: #FF0000; border-radius: 6px; border: 1px solid #AA0000;")

    def poll_zmq_data(self):
        """非阻塞讀取 ZMQ 消息，保證 UI 流暢不被卡死"""
        while True:
            try:
                # 採用 zmq.NOBLOCK，若無新消息會立刻拋出 zmq.Again 異常並 break 結束
                topic_bytes, payload_bytes = self.zmq_socket.recv_multipart(flags=zmq.NOBLOCK)
                topic = topic_bytes.decode('utf-8')
                payload_dict = json.loads(payload_bytes.decode('utf-8'))
                
                if topic.endswith("_log"):
                    # 💡 本地接收背景連線/重試日誌並分發，使其自動呈現於 GUI Log 視窗中
                    level_str = payload_dict.get("level", "INFO")
                    message = payload_dict.get("message", "")
                    logger_name = payload_dict.get("logger", "backend")
                    level = getattr(logging, level_str, logging.INFO)
                    logging.getLogger(logger_name).log(level, message)
                    continue

                sensor_data = SensorData.from_dict(payload_dict)
                self.update_ui_from_zmq(topic, sensor_data)
            except zmq.Again:
                break
            except Exception as e:
                self.logger.error(f"Error polling ZMQ message: {e}")
                break

    def _turn_off_led(self):
        """關閉接收指示燈 (變灰色)"""
        self.rx_led.setStyleSheet("background-color: #555555; border-radius: 6px;")

    def closeEvent(self, event):
        """視窗關閉時釋放 ZMQ 資源"""
        self.logger.info("MainWindow close event detected. Releasing ZMQ context and sockets...")
        try:
            self.zmq_poll_timer.stop()
            self.zmq_socket.close()
            self.zmq_context.term()
        except Exception as e:
            self.logger.error(f"Error terminating ZMQ connection on exit: {e}")
        event.accept()

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow(["ch1"])
    window.show()
    app.exec()