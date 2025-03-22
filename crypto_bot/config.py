"""
Модуль конфигурации для CryptoTrackerBot.
Содержит все константы и настройки приложения.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"

LOGS_DIR.mkdir(exist_ok=True)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise EnvironmentError(
        "TELEGRAM_TOKEN должен быть установлен в окружении.")

ADMIN_ID = os.getenv("ADMIN_ID")
LOGGER_ID = os.getenv(
    "LOGGER_ID")

DB_FILE = BASE_DIR / "bot_data.db"

COINGECKO_API = {
    "endpoint": "https://api.coingecko.com/api/v3/simple/price",
    "key": os.getenv("COINGECKO_API_KEY", ""),
}

DEFAULT_COINS = {
    "fpi-bank": {
        "name": "FPI Bank",
        "currency": "rub"
    }
}

RETRY_PERIOD = int(os.getenv("RETRY_PERIOD", "360"))  # секунды
DEFAULT_THRESHOLD = 0.1

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FILE = LOGS_DIR / "bot.log"


def setup_logger(name: str) -> logging.Logger:
    """
    Настройка логгера с заданным именем.

    Args:
        name: Имя логгера

    Returns:
        Настроенный объект Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
