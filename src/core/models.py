from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple
import re
import math

# 數據模型
@dataclass
class SensorData:
    rotationRoll : float
    rotationPitch : float
    direction : float
    timestamp: datetime
    stage:int
    failedTasks:List[int]
    location:Tuple[float, float]
    
    # 擴展新版航電遙測屬性，全部設置預設值以防向後相容報錯
    timestamp_ms: int = 0
    ax: float = 0.0
    ay: float = 0.0
    az: float = 0.0
    gx: float = 0.0
    gy: float = 0.0
    gz: float = 0.0
    pressure: float = 0.0
    rel_height: float = 0.0
    kfh_height: float = 0.0
    vz: float = 0.0
    total_accel: float = 0.0
    temp: float = 0.0
    raw_adc: int = 0
    flight_state: str = ""
    module_state: str = ""
    gnss_state: str = ""
    sv_visible: int = 0
    sv_used: int = 0
    buffer_val: int = 0
    count_val: int = 0
    cond_a_raw: int = 0
    cond_a_eff: int = 0
    cond_b_raw: int = 0
    cond_b_eff: int = 0
    peak_height: float = 0.0
    sd_writes: int = 0
    lora_seq: int = 0
    lora_success: int = 0
    lora_total: int = 0
    gs_timestamp: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any], timestamp: datetime = None) -> 'SensorData':
        """從 JSON 格式的字典創建 SensorData 物件"""
        try:
            # 轉換時間戳 (若傳入的是字串)
            ts = data.get('timestamp')
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except ValueError:
                    ts = timestamp or datetime.now()
            else:
                ts = ts or timestamp or datetime.now()

            # 建立包含基本欄位字典
            location_val = data.get('location', [25.0, 121.5])
            if isinstance(location_val, (list, tuple)) and len(location_val) >= 2:
                location = (float(location_val[0]), float(location_val[1]))
            else:
                location = (25.0, 121.5)

            kwargs = {
                "rotationRoll": float(data['rotationRoll']),
                "rotationPitch": float(data['rotationPitch']),
                "direction": float(data['direction']),
                "timestamp": ts,
                "stage": int(data.get('stage', 0)),
                "failedTasks": list(data.get('failedTasks', [])),
                "location": location
            }

            # 動態填寫其他可選欄位 (若存在於字典中)
            optional_fields = [
                "timestamp_ms", "ax", "ay", "az", "gx", "gy", "gz", "pressure",
                "rel_height", "kfh_height", "vz", "total_accel", "temp", "raw_adc",
                "flight_state", "module_state", "gnss_state", "sv_visible", "sv_used",
                "buffer_val", "count_val", "cond_a_raw", "cond_a_eff", "cond_b_raw",
                "cond_b_eff", "peak_height", "sd_writes", "lora_seq", "lora_success",
                "lora_total", "gs_timestamp"
            ]
            for field in optional_fields:
                if field in data:
                    val = data[field]
                    if val is not None:
                        # 進行適當的型別轉換
                        if field in ["flight_state", "module_state", "gnss_state"]:
                            kwargs[field] = str(val)
                        elif field in ["timestamp_ms", "raw_adc", "sv_visible", "sv_used", 
                                      "buffer_val", "count_val", "cond_a_raw", "cond_a_eff", 
                                      "cond_b_raw", "cond_b_eff", "sd_writes", "lora_seq", 
                                      "lora_success", "lora_total"]:
                            kwargs[field] = int(val)
                        elif field == "gs_timestamp":
                            kwargs[field] = float(val)
                        else:
                            kwargs[field] = float(val)

            return cls(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required field: {e}")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid data format: {e}")

    @classmethod
    def from_new_format(cls, line: str, timestamp: datetime = None) -> 'SensorData':
        """從新版航電板優化後的 ASCII 格式解析數據"""
        patterns = {
            'T': r'\bT(-?\d+)\b',
            'AX': r'\bAX([+-]?\d*\.?\d+)\b',
            'AY': r'\bAY([+-]?\d*\.?\d+)\b',
            'AZ': r'\bAZ([+-]?\d*\.?\d+)\b',
            'GX': r'\bGX([+-]?\d*\.?\d+)\b',
            'GY': r'\bGY([+-]?\d*\.?\d+)\b',
            'GZ': r'\bGZ([+-]?\d*\.?\d+)\b',
            'P': r'\bP([+-]?\d*\.?\d+)\b',
            'RH': r'\bRH([+-]?\d*\.?\d+)\b',
            'KH': r'\bKH([+-]?\d*\.?\d+)\b',
            'VZ': r'\bVZ([+-]?\d*\.?\d+)\b',
            'GA': r'\bGA([+-]?\d*\.?\d+)\b',
            'TC': r'\bTC([+-]?\d*\.?\d+)\b',
            'RAW': r'\bRAW(0x[0-9a-fA-F]+|\d+)\b',
            'ST': r'\bST:([A-Za-z0-9_-]+)\b',
            'MOD': r'\bMOD:?([0-9a-fA-F]+)\b',
            'GPS': r'\bGPS:([A-Za-z0-9_-]+(?:,\d+)?)\b',
            'SV': r'\bSV:(\d+),(\d+)\b',
            'BF': r'\bBF:(\d+),(\d+)\b',
            'CA': r'\bCA:(\d+),(\d+)\b',
            'CB': r'\bCB:(\d+),(\d+)\b',
            'C': r'\bC:([0-9a-fA-F]+)\b',
            'PK': r'\bPK([+-]?\d*\.?\d+)\b',
            'SD': r'\bSD(\d+)\b',
            'LR': r'\bLR:(\d+),(\d+),(\d+)\b',
            'LAT': r'\bLAT([+-]?\d*\.?\d+)\b',
            'LON': r'\bLON([+-]?\d*\.?\d+)\b',
        }
        
        extracted = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                if len(match.groups()) == 1:
                    extracted[key] = match.group(1)
                else:
                    extracted[key] = match.groups()
            else:
                extracted[key] = None

        if extracted['T'] is None:
            raise ValueError("Not in telemetry format: missing 'T' field")

        t_val = int(extracted['T'])
        ax = float(extracted['AX']) if extracted['AX'] else 0.0
        ay = float(extracted['AY']) if extracted['AY'] else 0.0
        az = float(extracted['AZ']) if extracted['AZ'] else 0.0
        gx = float(extracted['GX']) if extracted['GX'] else 0.0
        gy = float(extracted['GY']) if extracted['GY'] else 0.0
        gz = float(extracted['GZ']) if extracted['GZ'] else 0.0
        p_val = float(extracted['P']) if extracted['P'] else 0.0
        rel_h = float(extracted['RH']) if extracted['RH'] else 0.0
        kfh_h = float(extracted['KH']) if extracted['KH'] else 0.0
        vz = float(extracted['VZ']) if extracted['VZ'] else 0.0
        g_val = float(extracted['GA']) if extracted['GA'] else 0.0
        tc = float(extracted['TC']) if extracted['TC'] else 0.0
        
        raw_adc = 0
        if extracted['RAW']:
            raw_str = extracted['RAW']
            raw_adc = int(raw_str, 16) if raw_str.lower().startswith('0x') else int(raw_str)
            
        flight_state_val = extracted['ST'] or ""
        flight_state = ""
        if flight_state_val.isdigit():
            stage = int(flight_state_val)
            # Map stage back to string representation
            reverse_stage_map = {0: "IDLE", 1: "ARMED", 2: "LAUNCHED", 3: "BOOST", 4: "APOGEE", 5: "DESCENT", 6: "LANDED"}
            flight_state = reverse_stage_map.get(stage, "IDLE")
        else:
            flight_state = flight_state_val
            stage_map = {
                "IDLE": 0, "ARMED": 1, "LAUNCH": 2, "LAUNCHED": 2, "BOOST": 3, "APOGEE": 4, "DESCENT": 5, "LANDED": 6
            }
            stage = stage_map.get(flight_state.upper(), 0)

        mod_str = extracted['MOD'] or ""
        failedTasks = []
        if len(mod_str) == 4 and all(c in '01' for c in mod_str):
            if mod_str[0] == '0': failedTasks.append(0)
            if mod_str[1] == '0': failedTasks.append(1)
            if mod_str[2] == '0': failedTasks.append(2)
            if mod_str[3] == '0': failedTasks.append(3)
        elif mod_str:
            try:
                val = int(mod_str, 16)
                if not (val & (1 << 3)): failedTasks.append(0)
                if not (val & (1 << 2)): failedTasks.append(1)
                if not (val & (1 << 1)): failedTasks.append(2)
                if not (val & (1 << 0)): failedTasks.append(3)
            except ValueError:
                pass

        gps_val = extracted['GPS'] or ""
        gnss_state = ""
        sv_visible, sv_used = 0, 0
        if "," in gps_val:
            parts = gps_val.split(",")
            status_code = parts[0]
            sv_visible = int(parts[1])
            sv_used = sv_visible
            gnss_state = "FIX_3D" if status_code == "1" else "NO_FIX"
        else:
            gnss_state = gps_val
            if extracted['SV']:
                sv_visible = int(extracted['SV'][0])
                sv_used = int(extracted['SV'][1])
            
        buffer_val, count_val = 0, 0
        if extracted['BF']:
            buffer_val = int(extracted['BF'][0])
            count_val = int(extracted['BF'][1])
            
        ca_raw, ca_eff, cb_raw, cb_eff = 0, 0, 0, 0
        if extracted.get('C'):
            try:
                val = int(extracted['C'], 16)
                ca_raw = 1 if (val & (1 << 3)) else 0
                ca_eff = 1 if (val & (1 << 2)) else 0
                cb_raw = 1 if (val & (1 << 1)) else 0
                cb_eff = 1 if (val & (1 << 0)) else 0
            except ValueError:
                pass
        else:
            if extracted['CA']:
                ca_raw = int(extracted['CA'][0])
                ca_eff = int(extracted['CA'][1])
            if extracted['CB']:
                cb_raw = int(extracted['CB'][0])
                cb_eff = int(extracted['CB'][1])
            
        pk_val = float(extracted['PK']) if extracted['PK'] else 0.0
        sd_val = int(extracted['SD']) if extracted['SD'] else 0
        
        lora_seq, lora_success, lora_total = 0, 0, 0
        if extracted['LR']:
            lora_seq = int(extracted['LR'][0])
            lora_success = int(extracted['LR'][1])
            lora_total = int(extracted['LR'][2])

        # 加速度估算 Roll/Pitch
        try:
            roll_rad = math.atan2(ay, az)
            pitch_rad = math.atan2(-ax, math.sqrt(ay**2 + az**2))
            rotationRoll = roll_rad * 180.0 / math.pi
            rotationPitch = pitch_rad * 180.0 / math.pi
        except Exception:
            rotationRoll = 0.0
            rotationPitch = 0.0
            
        direction = 0.0

        # GPS 經緯度解析
        lat = float(extracted['LAT']) if extracted['LAT'] else 25.0
        lon = float(extracted['LON']) if extracted['LON'] else 121.5
        location = (lat, lon)

        return cls(
            rotationRoll=rotationRoll,
            rotationPitch=rotationPitch,
            direction=direction,
            timestamp=timestamp or datetime.now(),
            stage=stage,
            failedTasks=failedTasks,
            location=location,
            timestamp_ms=t_val,
            ax=ax, ay=ay, az=az,
            gx=gx, gy=gy, gz=gz,
            pressure=p_val,
            rel_height=rel_h,
            kfh_height=kfh_h,
            vz=vz,
            total_accel=g_val,
            temp=tc,
            raw_adc=raw_adc,
            flight_state=flight_state,
            module_state=mod_str,
            gnss_state=gnss_state,
            sv_visible=sv_visible,
            sv_used=sv_used,
            buffer_val=buffer_val,
            count_val=count_val,
            cond_a_raw=ca_raw,
            cond_a_eff=ca_eff,
            cond_b_raw=cb_raw,
            cond_b_eff=cb_eff,
            peak_height=pk_val,
            sd_writes=sd_val,
            lora_seq=lora_seq,
            lora_success=lora_success,
            lora_total=lora_total
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rotationRoll": self.rotationRoll,
            "rotationPitch": self.rotationPitch,
            "direction": self.direction,
            "timestamp": self.timestamp,
            "stage": self.stage,
            "failedTasks": self.failedTasks,
            "location": self.location,
            "timestamp_ms": self.timestamp_ms,
            "ax": self.ax,
            "ay": self.ay,
            "az": self.az,
            "gx": self.gx,
            "gy": self.gy,
            "gz": self.gz,
            "pressure": self.pressure,
            "rel_height": self.rel_height,
            "kfh_height": self.kfh_height,
            "vz": self.vz,
            "total_accel": self.total_accel,
            "temp": self.temp,
            "raw_adc": self.raw_adc,
            "flight_state": self.flight_state,
            "module_state": self.module_state,
            "gnss_state": self.gnss_state,
            "sv_visible": self.sv_visible,
            "sv_used": self.sv_used,
            "buffer_val": self.buffer_val,
            "count_val": self.count_val,
            "cond_a_raw": self.cond_a_raw,
            "cond_a_eff": self.cond_a_eff,
            "cond_b_raw": self.cond_b_raw,
            "cond_b_eff": self.cond_b_eff,
            "peak_height": self.peak_height,
            "sd_writes": self.sd_writes,
            "lora_seq": self.lora_seq,
            "lora_success": self.lora_success,
            "lora_total": self.lora_total
        }
@dataclass
class LogData:
    content : str
    timestamp: datetime

    @classmethod
    def new(cls, content:str, timestamp: datetime = None) -> 'LogData':
        """依照 content 創建 LogData 物件"""
        try:
            return cls(
                content=content,
                timestamp=timestamp or datetime.now()
            )
        except KeyError as e:
            raise ValueError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValueError(f"Invalid data format: {e}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "timestamp": self.timestamp,
        }