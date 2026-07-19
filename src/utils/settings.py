import os
import json
import logging

SETTINGS_FILE = "settings.json"
DEFAULT_PORT = "COM3"
DEFAULT_BAUDRATE = 115200

# 預設雙通道與 ZMQ 通訊埠設定
DEFAULT_CHANNELS = {
    "ch1": {
        "port": "COM3",
        "baudrate": 115200,
        "zmq_port": 5555,
        "zmq_cmd_port": 5565
    },
    "ch2": {
        "port": "COM4",
        "baudrate": 115200,
        "zmq_port": 5556,
        "zmq_cmd_port": 5566
    }
}

logger = logging.getLogger(__name__)

def _get_default_settings():
    return {"channels": DEFAULT_CHANNELS}

def load_channel_settings(channel_id: str = "ch1"):
    """
    載入指定通道的序列埠與 ZMQ 設定。
    傳回 (port, baudrate, zmq_port, zmq_cmd_port)
    """
    config = _get_default_settings()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # 相容性轉換：舊版扁平格式轉為新版通道格式
            if "channels" not in data:
                logger.info("Migrating legacy settings to channel-based settings...")
                legacy_port = data.get("port", DEFAULT_PORT)
                legacy_baud = data.get("baudrate", DEFAULT_BAUDRATE)
                data = {"channels": DEFAULT_CHANNELS}
                data["channels"]["ch1"]["port"] = legacy_port
                data["channels"]["ch1"]["baudrate"] = legacy_baud
                with open(SETTINGS_FILE, "w", encoding="utf-8") as f_out:
                    json.dump(data, f_out, indent=4)
            
            config = data
        except Exception as e:
            logger.error(f"Error reading {SETTINGS_FILE}: {e}. Using defaults.")

    channels = config.get("channels", DEFAULT_CHANNELS)
    ch_config = channels.get(channel_id, DEFAULT_CHANNELS.get(channel_id))
    
    port = str(ch_config.get("port", DEFAULT_PORT))
    baudrate = int(ch_config.get("baudrate", DEFAULT_BAUDRATE))
    zmq_port = int(ch_config.get("zmq_port", DEFAULT_CHANNELS[channel_id]["zmq_port"]))
    zmq_cmd_port = int(ch_config.get("zmq_cmd_port", DEFAULT_CHANNELS[channel_id]["zmq_cmd_port"]))
    
    logger.info(f"Loaded channel={channel_id}: port={port}, baud={baudrate}, zmq_port={zmq_port}, zmq_cmd={zmq_cmd_port}")
    return port, baudrate, zmq_port, zmq_cmd_port

def save_channel_settings(channel_id: str, port: str, baudrate: int):
    """
    儲存指定通道的序列埠設定。
    """
    config = _get_default_settings()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "channels" not in config:
                config = {"channels": DEFAULT_CHANNELS}
        except Exception as e:
            logger.error(f"Failed to read settings before save: {e}")
            config = {"channels": DEFAULT_CHANNELS}

    if "channels" not in config:
        config["channels"] = {}
    if channel_id not in config["channels"]:
        config["channels"][channel_id] = DEFAULT_CHANNELS.get(channel_id, {}).copy()
        
    config["channels"][channel_id]["port"] = port
    config["channels"][channel_id]["baudrate"] = baudrate

    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        logger.info(f"Saved channel={channel_id}: port={port}, baudrate={baudrate}")
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")

def load_settings():
    """
    相容性包裝：載入 ch1 的設定。
    傳回 (port, baudrate)
    """
    port, baudrate, _, _ = load_channel_settings("ch1")
    return port, baudrate

def save_settings(port: str, baudrate: int):
    """
    相容性包裝：儲存 ch1 的設定。
    """
    save_channel_settings("ch1", port, baudrate)
