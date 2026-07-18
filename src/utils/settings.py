import os
import json
import logging

SETTINGS_FILE = "settings.json"
DEFAULT_PORT = "COM3"
DEFAULT_BAUDRATE = 115200

logger = logging.getLogger(__name__)

def load_settings():
    """
    Loads serial settings from settings.json.
    Returns (port, baudrate).
    """
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                port = data.get("port", DEFAULT_PORT)
                baudrate = data.get("baudrate", DEFAULT_BAUDRATE)
                # Ensure types are correct
                if not isinstance(port, str):
                    port = str(port)
                if not isinstance(baudrate, int):
                    baudrate = int(baudrate)
                logger.info(f"Loaded settings from {SETTINGS_FILE}: port={port}, baudrate={baudrate}")
                return port, baudrate
        except Exception as e:
            logger.error(f"Error reading {SETTINGS_FILE}: {e}. Using defaults.")
    
    logger.info(f"Settings file not found. Using defaults: port={DEFAULT_PORT}, baudrate={DEFAULT_BAUDRATE}")
    return DEFAULT_PORT, DEFAULT_BAUDRATE

def save_settings(port: str, baudrate: int):
    """
    Saves serial settings to settings.json.
    """
    try:
        data = {
            "port": port,
            "baudrate": baudrate
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logger.info(f"Saved settings to {SETTINGS_FILE}: port={port}, baudrate={baudrate}")
    except Exception as e:
        logger.error(f"Failed to save settings to {SETTINGS_FILE}: {e}")
