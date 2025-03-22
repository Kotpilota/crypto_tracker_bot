import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from crypto_bot.config import DB_FILE, setup_logger

logger = setup_logger(__name__)


@contextmanager
def get_db_connection():
    """
    Контекстный менеджер для соединения с базой данных.
    Автоматически закрывает соединение после использования.

    Yields:
        sqlite3.Connection: Соединение с базой данных
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_db() -> None:
    """
    Инициализирует базу данных, создавая необходимые таблицы.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    chat_id INTEGER PRIMARY KEY,
                    coin_id TEXT NOT NULL,
                    balance REAL,
                    threshold REAL,
                    depozit REAL DEFAULT 0,
                    last_notified_price REAL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS coin_prices (
                    coin_id TEXT PRIMARY KEY,
                    current_price REAL,
                    last_updated TEXT
                )
            ''')

            conn.commit()
            logger.info("База данных инициализирована")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


def load_all_user_settings() -> Dict[int, Dict[str, Any]]:
    """
    Загружает все настройки пользователей из базы данных.

    Returns:
        Dict[int, Dict[str, Any]]: Словарь настроек пользователей по chat_id
    """
    settings = {}

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chat_id, coin_id, balance, threshold, depozit, last_notified_price FROM user_settings"
            )
            rows = cursor.fetchall()

            for row in rows:
                chat_id, coin_id, balance, threshold, depozit, last_notified_price = row
                settings[chat_id] = {
                    "coin_id": coin_id,
                    "balance": balance,
                    "threshold": threshold,
                    "depozit": depozit,
                    "last_notified_price": last_notified_price
                }

            logger.info(
                f"Загружены настройки для {len(settings)} пользователей")
            return settings
    except sqlite3.Error as e:
        logger.error(f"Ошибка при загрузке настроек пользователей: {e}")
        return {}


def get_user_settings(chat_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает настройки конкретного пользователя.

    Args:
        chat_id: ID чата пользователя

    Returns:
        Optional[Dict[str, Any]]: Настройки пользователя или None, если не найдены
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT coin_id, balance, threshold, depozit, last_notified_price FROM user_settings WHERE chat_id = ?",
                (chat_id,)
            )
            row = cursor.fetchone()

            if row:
                coin_id, balance, threshold, depozit, last_notified_price = row
                return {
                    "coin_id": coin_id,
                    "balance": balance,
                    "threshold": threshold,
                    "depozit": depozit,
                    "last_notified_price": last_notified_price
                }
            return None
    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при получении настроек пользователя {chat_id}: {e}")
        return None


def update_user_settings(
        chat_id: int,
        coin_id: Optional[str] = None,
        balance: Optional[float] = None,
        threshold: Optional[float] = None,
        depozit: Optional[float] = None,
        last_notified_price: Optional[float] = None
) -> bool:
    """
    Обновляет настройки пользователя (или добавляет новую запись).

    Args:
        chat_id: ID чата пользователя
        coin_id: ID криптовалюты (опционально)
        balance: Количество монет (опционально)
        threshold: Порог уведомлений (опционально)
        depozit: Сумма вложения (опционально)
        last_notified_price: Последняя цена, о которой уведомляли (опционально)

    Returns:
        bool: True если обновление успешно, иначе False
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT coin_id, balance, threshold, depozit, last_notified_price FROM user_settings WHERE chat_id = ?",
                (chat_id,)
            )
            row = cursor.fetchone()

            if row:
                current_coin_id, current_balance, current_threshold, current_depozit, current_last_price = row

                new_coin_id = coin_id if coin_id is not None else current_coin_id
                new_balance = balance if balance is not None else current_balance
                new_threshold = threshold if threshold is not None else current_threshold
                new_depozit = depozit if depozit is not None else current_depozit
                new_last_price = last_notified_price if last_notified_price is not None else current_last_price

                cursor.execute('''
                    UPDATE user_settings
                    SET coin_id = ?, balance = ?, threshold = ?, depozit = ?, last_notified_price = ?
                    WHERE chat_id = ?
                ''', (new_coin_id, new_balance, new_threshold, new_depozit,
                      new_last_price, chat_id))
            else:
                default_coin_id = coin_id or "fpi-bank"
                default_threshold = threshold or 0.1
                default_depozit = depozit or 0
                default_last_price = last_notified_price or 0

                cursor.execute('''
                    INSERT INTO user_settings (chat_id, coin_id, balance, threshold, depozit, last_notified_price)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (chat_id, default_coin_id, balance, default_threshold,
                      default_depozit, default_last_price))

            conn.commit()
            logger.info(f"Обновлены настройки для пользователя {chat_id}")
            return True
    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при обновлении настроек пользователя {chat_id}: {e}")
        return False


def remove_user(chat_id: int) -> bool:
    """
    Удаляет пользователя из базы данных.

    Args:
        chat_id: ID чата пользователя

    Returns:
        bool: True если удаление успешно, иначе False
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_settings WHERE chat_id = ?",
                           (chat_id,))
            conn.commit()

            rows_affected = cursor.rowcount
            if rows_affected > 0:
                logger.info(f"Пользователь {chat_id} удален из базы данных")
                return True
            else:
                logger.warning(
                    f"Пользователь {chat_id} не найден в базе данных")
                return False
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении пользователя {chat_id}: {e}")
        return False


def update_coin_price(coin_id: str, price: float) -> None:
    """
    Обновляет текущую цену монеты в базе данных.

    Args:
        coin_id: ID криптовалюты
        price: Текущая цена
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO coin_prices (coin_id, current_price, last_updated)
                VALUES (?, ?, datetime('now'))
            ''', (coin_id, price))
            conn.commit()
            logger.debug(f"Обновлена цена для {coin_id}: {price}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении цены для {coin_id}: {e}")


def get_coin_price(coin_id: str) -> Optional[float]:
    """
    Получает текущую цену монеты из базы данных.

    Args:
        coin_id: ID криптовалюты

    Returns:
        Optional[float]: Текущая цена или None, если не найдена
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT current_price FROM coin_prices WHERE coin_id = ?",
                (coin_id,))
            row = cursor.fetchone()

            if row:
                return row[0]
            return None
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении цены для {coin_id}: {e}")
        return None


def get_users_count() -> int:
    """
    Получает количество пользователей бота.

    Returns:
        int: Количество пользователей
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user_settings")
            row = cursor.fetchone()

            if row:
                return row[0]
            return 0
    except sqlite3.Error as e:
        logger.error(f"Ошибка при подсчете пользователей: {e}")
        return 0
