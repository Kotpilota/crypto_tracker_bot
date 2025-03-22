import re
from datetime import datetime
from typing import Optional, Tuple

from crypto_bot.config import setup_logger

logger = setup_logger(__name__)


def format_price(price: float, precision: int = 2) -> str:
    """
    Форматирует цену с разделителями групп разрядов.

    Args:
        price: Цена для форматирования
        precision: Количество знаков после запятой

    Returns:
        str: Отформатированная строка цены
    """
    return f"{price:,.{precision}f}".replace(",", " ")


def parse_number(text: str) -> Optional[float]:
    """
    Безопасное преобразование строки в число.
    Поддерживает разные разделители (точка, запятая).

    Args:
        text: Строка для преобразования

    Returns:
        Optional[float]: Число или None в случае ошибки
    """
    try:
        clean_text = text.replace(",", ".").replace(" ", "")
        return float(clean_text)
    except (ValueError, TypeError):
        return None


def calculate_profit(amount: float, buy_price: float, current_price: float,
                     fee_percent: float = 3.0) -> Tuple[float, float]:
    """
    Рассчитывает прибыль от инвестиции.

    Args:
        amount: Количество монет
        buy_price: Цена покупки
        current_price: Текущая цена
        fee_percent: Процент комиссии при продаже

    Returns:
        Tuple[float, float]: (прибыль в валюте, процент прибыли)
    """
    initial_investment = amount * buy_price
    current_value = amount * current_price * (1 - fee_percent / 100)
    profit = current_value - initial_investment
    profit_percent = (profit / initial_investment) * 100 if initial_investment > 0 else 0

    return profit, profit_percent


def format_timestamp(timestamp: Optional[float] = None) -> str:
    """
    Форматирует временную метку в человекочитаемый формат.

    Args:
        timestamp: Unix timestamp или None для текущего времени

    Returns:
        str: Отформатированная дата и время
    """
    if timestamp is None:
        dt = datetime.now()
    else:
        dt = datetime.fromtimestamp(timestamp)

    return dt.strftime("%d.%m.%Y %H:%M:%S")


def extract_command(text: str) -> Optional[str]:
    """
    Извлекает команду из текста сообщения.

    Args:
        text: Текст сообщения

    Returns:
        Optional[str]: Команда или None, если команда не найдена
    """
    command_match = re.match(r'^/([a-zA-Z0-9_]+)(@\w+)?', text)
    if command_match:
        return command_match.group(1)
    return None
