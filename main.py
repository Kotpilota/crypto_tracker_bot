import signal
import sys
import os
from threading import Thread

from crypto_bot import bot
from crypto_bot import database as db
from crypto_bot.config import setup_logger

logger = setup_logger(__name__)


def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы."""
    logger.info("Получен сигнал завершения работы. Завершаем работу бота...")
    sys.exit(0)


def check_assets_folder():
    """Проверяет наличие папки assets для медиаресурсов."""
    if not os.path.exists('assets'):
        os.makedirs('assets')
        logger.info("Создана директория assets для хранения медиафайлов")


def main():
    """
    Основная функция запуска бота.
    Инициализирует базу данных, загружает настройки и запускает потоки.
    """
    try:
        logger.info("Проверка наличия директории для медиафайлов...")
        check_assets_folder()

        logger.info("Инициализация базы данных...")
        db.init_db()

        logger.info("Загрузка настроек пользователей...")
        bot.load_settings()

        logger.info("Настройка кнопки меню...")
        bot.set_menu_button()

        logger.info("Запуск фонового потока проверки курса...")
        price_thread = Thread(target=bot.price_checker)
        price_thread.daemon = True
        price_thread.start()

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
