from http import HTTPStatus
from typing import Dict, Optional, Tuple

import requests
from requests.exceptions import RequestException, Timeout

from crypto_bot.config import COINGECKO_API, setup_logger

logger = setup_logger(__name__)


class CryptoAPIError(Exception):
    """Базовый класс для ошибок API криптовалют."""
    pass


class RateLimitError(CryptoAPIError):
    """Ошибка превышения лимита запросов."""
    pass


class APIConnectionError(CryptoAPIError):
    """Ошибка соединения с API."""
    pass


class APIResponseError(CryptoAPIError):
    """Ошибка ответа API."""
    pass


def get_coin_price(coin_id: str, currency: str = "rub") -> Tuple[
    Optional[float], Optional[str]]:
    """
    Получает текущую цену криптовалюты через CoinGecko API.

    Args:
        coin_id: Идентификатор монеты в CoinGecko
        currency: Валюта для конвертации (по умолчанию "rub")

    Returns:
        Tuple[Optional[float], Optional[str]]: Кортеж из текущей цены и сообщения об ошибке

    Raises:
        RateLimitError: Если превышен лимит запросов
        APIConnectionError: При проблемах с соединением
        APIResponseError: При проблемах с ответом API
    """
    endpoint = COINGECKO_API["endpoint"]
    api_key = COINGECKO_API["key"]

    params = {
        "ids": coin_id,
        "vs_currencies": currency,
    }

    if api_key:
        params["x_cg_demo_api_key"] = api_key

    headers = {
        "Accept": "application/json",
        "User-Agent": "CryptoTrackerBot/1.0.0"
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers,
                                timeout=10)

        if response.status_code == HTTPStatus.OK:
            data = response.json()
            if coin_id in data and currency in data[coin_id]:
                price = float(data[coin_id][currency])
                logger.info(
                    f"Получена цена для {coin_id}: {price} {currency.upper()}")
                return price, None
            else:
                error_msg = f"Некорректная структура ответа API: {data}"
                logger.error(error_msg)
                return None, error_msg
        elif response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            error_msg = "Превышен лимит запросов к API"
            logger.error(error_msg)
            raise RateLimitError(error_msg)
        else:
            error_msg = f"API вернул ошибку: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise APIResponseError(error_msg)

    except Timeout:
        error_msg = "Таймаут при запросе к API"
        logger.error(error_msg)
        raise APIConnectionError(error_msg)
    except RequestException as e:
        error_msg = f"Ошибка запроса к API: {e}"
        logger.error(error_msg)
        raise APIConnectionError(error_msg)
    except Exception as e:
        error_msg = f"Неожиданная ошибка при запросе к API: {e}"
        logger.error(error_msg)
        return None, error_msg


def get_multiple_prices(coin_ids: list, currency: str = "rub") -> Dict[
    str, Optional[float]]:
    """
    Получает цены для нескольких криптовалют.

    Args:
        coin_ids: Список идентификаторов монет
        currency: Валюта для конвертации

    Returns:
        Dict[str, Optional[float]]: Словарь с ценами монет
    """
    endpoint = COINGECKO_API["endpoint"]
    api_key = COINGECKO_API["key"]

    params = {
        "ids": ",".join(coin_ids),
        "vs_currencies": currency,
    }

    if api_key:
        params["x_cg_demo_api_key"] = api_key

    headers = {
        "Accept": "application/json",
        "User-Agent": "CryptoTrackerBot/1.0.0"
    }

    result = {}

    try:
        response = requests.get(endpoint, params=params, headers=headers,
                                timeout=10)

        if response.status_code == HTTPStatus.OK:
            data = response.json()
            for coin_id in coin_ids:
                if coin_id in data and currency in data[coin_id]:
                    result[coin_id] = float(data[coin_id][currency])
                else:
                    result[coin_id] = None
            return result
        else:
            logger.error(
                f"Ошибка при получении цен: {response.status_code} - {response.text}")
            return {coin_id: None for coin_id in coin_ids}

    except Exception as e:
        logger.error(f"Неожиданная ошибка при запросе цен: {e}")
        return {coin_id: None for coin_id in coin_ids}
