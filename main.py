import signal
import sys
from threading import Thread

from crypto_bot import bot
from crypto_bot import database as db
from crypto_bot.config import setup_logger

logger = setup_logger(__name__)


def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы."""
    logger.info("Получен сигнал завершения работы. Завершаем работу бота...")
    sys.exit(0)


def main():
    """
    Основная функция запуска бота.
    Инициализирует базу данных, загружает настройки и запускает потоки.
    """
    try:
        logger.info("Инициализация базы данных...")
        db.init_db()

        logger.info("Загрузка настроек пользователей...")
        bot.load_settings()

        logger.info("Запуск фонового потока проверки курса...")
        price_thread = Thread(target=bot.price_checker)
        price_thread.daemon = True
        price_thread.start()

        # Регистрация обработчика сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Запуск бота...")
        bot.bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
