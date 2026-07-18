import csv
import logging
from src.core.models import SensorData
from src.storage.base import DataStorage

class CsvDataStorage(DataStorage):
    """CSV 數據存儲"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def save(self, data: SensorData,filename:str):
        try:
            with open(filename, 'a', newline='') as f:
                fieldnames = [
                    "timestamp", "rotationRoll", "rotationPitch", "direction", "stage", "location",
                    "timestamp_ms", "ax", "ay", "az", "gx", "gy", "gz", "pressure",
                    "rel_height", "kfh_height", "vz", "total_accel", "temp", "raw_adc",
                    "flight_state", "module_state", "gnss_state", "sv_visible", "sv_used",
                    "buffer_val", "count_val", "cond_a_raw", "cond_a_eff", "cond_b_raw",
                    "cond_b_eff", "peak_height", "sd_writes", "lora_seq", "lora_success", "lora_total"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                if f.tell() == 0:
                    writer.writeheader()
                    
                writer.writerow({
                    "timestamp": data.timestamp,
                    "rotationRoll": data.rotationRoll,
                    "rotationPitch": data.rotationPitch,
                    "direction": data.direction,
                    "stage": data.stage,
                    "location": f"{data.location[0]},{data.location[1]}",
                    "timestamp_ms": data.timestamp_ms,
                    "ax": data.ax,
                    "ay": data.ay,
                    "az": data.az,
                    "gx": data.gx,
                    "gy": data.gy,
                    "gz": data.gz,
                    "pressure": data.pressure,
                    "rel_height": data.rel_height,
                    "kfh_height": data.kfh_height,
                    "vz": data.vz,
                    "total_accel": data.total_accel,
                    "temp": data.temp,
                    "raw_adc": data.raw_adc,
                    "flight_state": data.flight_state,
                    "module_state": data.module_state,
                    "gnss_state": data.gnss_state,
                    "sv_visible": data.sv_visible,
                    "sv_used": data.sv_used,
                    "buffer_val": data.buffer_val,
                    "count_val": data.count_val,
                    "cond_a_raw": data.cond_a_raw,
                    "cond_a_eff": data.cond_a_eff,
                    "cond_b_raw": data.cond_b_raw,
                    "cond_b_eff": data.cond_b_eff,
                    "peak_height": data.peak_height,
                    "sd_writes": data.sd_writes,
                    "lora_seq": data.lora_seq,
                    "lora_success": data.lora_success,
                    "lora_total": data.lora_total
                })
                
        except Exception as e:
            self.logger.error(f"CSV storage error: {e}")
