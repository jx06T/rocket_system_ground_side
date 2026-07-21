import sys
import time
import math
import random
import serial  # pip install pyserial

# 預設串列埠與鮑率
DEFAULT_PORT = "COM32"
BAUDRATE = 115200

# 模擬初始位置 (發射場坐標，例如臺北科大附近)
START_LAT = 25.04213
START_LON = 121.53489

# 12 階段/事件對照表
STAGE_MAP = {
    0: "IDLE",
    1: "ARMED",
    2: "IGNITION",            # Event (連發 4 幀)
    3: "POWERED_FLIGHT",
    4: "BURNOUT",             # Event (連發 4 幀)
    5: "COASTING",
    6: "APOGEE",              # Event (連發 4 幀)
    7: "PARACHUTE_DEPLOY",    # Event (連發 4 幀)
    8: "DESCENT",
    9: "TOUCHDOWN",           # Event (連發 4 幀)
    10: "AIRBAG_DEPLOY",      # Event (連發 4 幀)
    11: "LANDED"
}

def generate_telemetry_stream(port: str):
    """模擬發射物理過程並生成符合最新規範的 ASCII 遙測數據與 MSG 事件封包"""
    t_start = time.time()
    
    # 物理與運動學變數
    alt = 0.0          # 高度 (m)
    vel_z = 0.0        # 垂直速度 (m/s)
    accel_g = 1.0      # 總合加速度大小 (g)
    
    gyro_x = 0.0
    gyro_y = 0.0
    gyro_z = 0.0
    
    # 經緯度與移動狀態初始化
    current_lat = START_LAT
    current_lon = START_LON
    vel_x = 0.0
    vel_y = 0.0
    
    target_pitch = 0.0
    target_roll = 0.0
    last_pitch = 0.0
    last_roll = 0.0
    peak_alt = 0.0
    
    # 主狀態與連發事件控制器
    main_stage = 0          # 0=IDLE
    event_repeat_count = 0  # 瞬態事件 4 次連發計數
    active_st_code = 0     # 當前傳送於 ST: 欄位的代碼
    
    # 故障模擬狀態
    prev_mod_status = "E"
    FAULT_SCENARIOS = [
        (12.0, 6.0, "sd"),   # POWERED_FLIGHT 期間 SD 寫入忙碌異常
        (18.0, 4.0, "imu"),  # COASTING 滑行期間震動干擾 IMU
        (28.0, 5.0, "bmp"),  # DESCENT 高速降落衝擊導致 BMP 數據異常
    ]
    
    # 連接序列埠
    try:
        ser = serial.Serial(port, BAUDRATE, timeout=1)
        print(f"[*] 成功開啟模擬發射端序列埠: {port}，鮑率: {BAUDRATE}")
        print("[*] 正在發射符合最新 telemetry_format.md 規範的遙測數據...")
        print("[*] 按 Ctrl+C 可結束模擬器。\n")
    except Exception as e:
        print(f"[!] 無法開啟序列埠 {port}。錯誤原因: {e}")
        print("[!] 請確認虛擬序列埠（如 com0com / VSPE）設定正確且埠未被佔用。")
        return

    dt = 0.5  # 2Hz (500ms 更新一次)
    t_state_start = 0.0

    def send_msg(level: str, content: str):
        """發送符合 MSG <LEVEL> <CONTENT> 規範的特殊事件封包"""
        msg_str = f"MSG {level} {content}\r\n"
        try:
            ser.write(msg_str.encode('utf-8'))
            print(f"\n[📡 MSG 發送] {msg_str.strip()}")
        except Exception as ex:
            print(f"[!] MSG 發送失敗: {ex}")

    def trigger_event(event_st: int, next_stage_st: int, msg_level: str = None, msg_text: str = None):
        """觸發 4 次連發事件，發送完畢後進入下一個主狀態」"""
        nonlocal main_stage, active_st_code, event_repeat_count, t_state_start
        active_st_code = event_st
        event_repeat_count = 4
        main_stage = next_stage_st
        t_state_start = t_elapsed
        st_name = STAGE_MAP.get(event_st, str(event_st))
        next_name = STAGE_MAP.get(next_stage_st, str(next_stage_st))
        print(f"\n[⚡ EVENT 觸發] {st_name} (連發 4 幀) ➔ 預備切換至階段: {next_name}")
        if msg_level and msg_text:
            send_msg(msg_level, msg_text)

    try:
        while True:
            loop_start = time.time()
            t_elapsed = loop_start - t_start
            
            vibe_x, vibe_y, vibe_z = 0.0, 0.0, 0.0

            # --- 1. 火箭 12 階段狀態機與物理模擬 ---
            if main_stage == 0:  # IDLE
                alt, vel_z, accel_g = 0.0, 0.0, 1.0
                target_pitch = random.uniform(-0.5, 0.5)
                target_roll = random.uniform(-0.5, 0.5)
                gyro_x = random.uniform(-0.2, 0.2)
                gyro_y = random.uniform(-0.2, 0.2)
                gyro_z = random.uniform(-0.1, 0.1)
                
                if t_elapsed > 5.0:
                    main_stage = 1  # 進入 ARMED
                    active_st_code = 1
                    t_state_start = t_elapsed
                    print("\n[+] >>> 安全解鎖完成！進入 1: ARMED 上架待發階段 <<<")

            elif main_stage == 1:  # ARMED
                alt, vel_z, accel_g = 0.0, 0.0, 1.0
                target_pitch = random.uniform(-0.5, 0.5)
                target_roll = random.uniform(-0.5, 0.5)
                gyro_x, gyro_y, gyro_z = random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2), random.uniform(-0.1, 0.1)
                
                # 10 秒時點火觸發 ST:2 (IGNITION) 事件 (連發 4 幀後進入 ST:3 POWERED_FLIGHT)
                if t_elapsed > 10.0:
                    trigger_event(2, 3, "INFO", "Rocket ignition pulse triggered")

            elif main_stage == 3:  # POWERED_FLIGHT
                phase_time = t_elapsed - t_state_start
                accel_g = 1.0 + 7.5 * math.sin(math.pi * (phase_time + 0.5) / 4.0)
                gyro_z = 720.0 + random.uniform(-20, 20)
                gyro_x = random.uniform(-10.0, 10.0)
                gyro_y = random.uniform(-10.0, 10.0)
                target_roll = (target_roll + gyro_z * dt) % 360.0
                target_pitch = 4.0 * math.cos(math.radians(target_roll)) + random.uniform(-0.5, 0.5)
                
                vibe_x, vibe_y, vibe_z = random.gauss(0, 0.25), random.gauss(0, 0.25), random.gauss(0, 0.40)
                vel_z += (accel_g - 1.0) * 9.8 * dt
                alt += vel_z * dt
                vel_x, vel_y = 10.0, 15.0
                
                # 推進 3.5 秒後引擎熄火 觸發 ST:4 (BURNOUT) 事件
                if phase_time >= 3.5:
                    trigger_event(4, 5, "INFO", "Engine burnout detected")

            elif main_stage == 5:  # COASTING
                phase_time = t_elapsed - t_state_start
                drag_accel = 0.0003 * (vel_z ** 2) / 9.8
                accel_g = max(0.0, 0.0 - drag_accel)
                vel_z -= (1.0 + drag_accel) * 9.8 * dt
                alt += vel_z * dt
                
                spin_rate = 720.0 * math.exp(-0.35 * phase_time)
                gyro_z = spin_rate
                gyro_x, gyro_y = random.uniform(-2.0, 2.0), random.uniform(-2.0, 2.0)
                target_roll = (target_roll + gyro_z * dt) % 360.0
                wobble_amp = 4.0 + 4.0 * (phase_time / 6.0)
                target_pitch = wobble_amp * math.cos(math.radians(target_roll))
                
                vibe_x, vibe_y, vibe_z = random.gauss(0, 0.03), random.gauss(0, 0.03), random.gauss(0, 0.05)
                vel_x *= math.exp(-0.05 * dt)
                vel_y *= math.exp(-0.05 * dt)
                
                # 到達最高頂點 觸發 ST:6 (APOGEE) 事件
                if vel_z <= 0.0:
                    peak_alt = alt
                    last_pitch, last_roll = target_pitch, target_roll
                    trigger_event(6, 7, "INFO", f"Apogee reached at {peak_alt:.1f}m")

            elif main_stage == 7:  # 觸發開傘事件
                # 開傘觸發 4 連發事件後自動轉為 ST:8 (DESCENT)
                trigger_event(7, 8, "SUCCESS", "Parachute deployed successfully")

            elif main_stage == 8:  # DESCENT
                phase_time = t_elapsed - t_state_start
                vel_z += (-8.0 - vel_z) * 0.3
                accel_g = 1.0
                alt += vel_z * dt
                
                if phase_time < 1.5:
                    progress = phase_time / 1.5
                    target_pitch = last_pitch + (0.0 - last_pitch) * progress
                    target_roll = last_roll + (180.0 - last_roll) * progress
                    gyro_x = (0.0 - last_pitch) / 1.5
                    gyro_y = 0.0
                    gyro_z = (180.0 - last_roll) / 1.5
                else:
                    sway_time = phase_time - 1.5
                    sway_angle = 15.0 * math.sin(2.0 * math.pi * 0.4 * sway_time)
                    target_pitch = sway_angle
                    target_roll = 180.0 + 10.0 * math.cos(2.0 * math.pi * 0.4 * sway_time)
                    gyro_x = 15.0 * (2.0 * math.pi * 0.4) * math.cos(2.0 * math.pi * 0.4 * sway_time)
                    gyro_y = random.uniform(-1.0, 1.0)
                    gyro_z = -10.0 * (2.0 * math.pi * 0.4) * math.sin(2.0 * math.pi * 0.4 * sway_time)
                
                vel_x, vel_y = 8.0, -5.0
                vibe_x, vibe_y, vibe_z = random.gauss(0, 0.05), random.gauss(0, 0.05), random.gauss(0, 0.05)
                
                # 觸地判定 觸發 ST:9 (TOUCHDOWN)
                if alt <= 0.5:
                    alt, vel_z = 0.0, 0.0
                    trigger_event(9, 10, "INFO", "Ground touchdown impact detected")

            elif main_stage == 10: # AIRBAG_DEPLOY
                # 氣囊充氣連發事件 4 幀後進入 ST:11 (LANDED)
                trigger_event(10, 11, "INFO", "Airbag inflation started")

            elif main_stage == 11: # LANDED
                target_pitch, target_roll = 75.0, 15.0
                gyro_x, gyro_y, gyro_z = 0.0, 0.0, 0.0
                accel_g, vel_x, vel_y = 1.0, 0.0, 0.0

            # --- 2. 決定當前發送的 ST 欄位代碼 (去重連發機制) ---
            if event_repeat_count > 0:
                current_st_code = active_st_code
                event_repeat_count -= 1
            else:
                current_st_code = main_stage

            # --- 3. 姿態與三軸加速度逆計算 ---
            roll_rad = math.radians(target_roll)
            pitch_rad = math.radians(target_pitch)
            ax = -accel_g * math.sin(pitch_rad) + vibe_x
            ay = accel_g * math.sin(roll_rad) * math.cos(pitch_rad) + vibe_y
            az = accel_g * math.cos(roll_rad) * math.cos(pitch_rad) + vibe_z
            
            # --- 4. 經緯度積分計算 ---
            current_lat += vel_y * dt / 111195.0
            current_lon += vel_x * dt / 100800.0
            
            # --- 5. 氣壓與健康模組計算 ---
            pressure = 1013.25 * math.pow((1 - 2.25577e-5 * max(0.0, alt)), 5.25588)
            
            bmp_ok, imu_ok, lora_ok, sd_ok = 1, 1, 1, 1
            for fault_start, fault_duration, fault_module in FAULT_SCENARIOS:
                if fault_start <= t_elapsed < fault_start + fault_duration:
                    if fault_module == "bmp": bmp_ok = 0
                    elif fault_module == "imu": imu_ok = 0
                    elif fault_module == "lora": lora_ok = 0
                    elif fault_module == "sd": sd_ok = 0
            
            # 4-bit 十六進制：BMP(b3), IMU(b2), LoRa(b1), SD(b0)
            mod_val = (bmp_ok << 3) | (imu_ok << 2) | (lora_ok << 1) | sd_ok
            mod_hex = f"{mod_val:X}"

            if mod_hex != prev_mod_status:
                if mod_hex != "F":
                    send_msg("WARN", f"Module health degradation: MOD:{mod_hex}")
                else:
                    send_msg("INFO", "All modules restored to healthy state (MOD:F)")
                prev_mod_status = mod_hex

            # GPS 定位狀態 (0=NO_FIX, 1=FIX)
            gps_val = "1,8" if t_elapsed > 3.0 else "0,0"

            # --- 6. 構造全新規格 ASCII 遙測數據包 ---
            # 規範欄位：T, AX, AY, AZ, GX, GY, GZ, P, RH, KH, VZ, GA, ST, MOD, GPS, C (, LAT, LON)
            t_ms = int(t_elapsed * 1000)
            payload = (
                f"T{t_ms} "
                f"AX{ax:+.3f} AY{ay:+.3f} AZ{az:+.3f} "
                f"GX{gyro_x:+.2f} GY{gyro_y:+.2f} GZ{gyro_z:+.2f} "
                f"P{pressure:.2f} RH{alt:.1f} KH{alt + random.uniform(-0.1, 0.1):.1f} VZ{vel_z:+.2f} "
                f"GA{accel_g:.2f} ST:{current_st_code} MOD:{mod_hex} GPS:{gps_val} C:A"
            )
            
            if t_elapsed > 3.0:
                payload += f" LAT{current_lat:+.5f} LON{current_lon:+.5f}"
                
            telemetry_line = payload + "\r\n"
            ser.write(telemetry_line.encode('utf-8'))
            
            st_str = STAGE_MAP.get(current_st_code, str(current_st_code))
            print(f"[{st_str:16s}] Alt:{alt:6.1f}m | Vz:{vel_z:+5.1f}m/s | Lat:{current_lat:.5f} Lon:{current_lon:.5f} | TX: {payload[:45]}...", end="\r")
            
            elapsed = time.time() - loop_start
            time.sleep(max(0.0, dt - elapsed))
            
    except KeyboardInterrupt:
        print("\n\n[-] 模擬遙測發送已由使用者終止。")
    finally:
        ser.close()
        print("[*] 序列埠已安全關閉。")

if __name__ == "__main__":
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    print("=" * 60)
    print("        🚀 新版航電遙測與 12 階段事件模擬器 (Mock Generator) 🚀")
    print("=" * 60)
    generate_telemetry_stream(port)
