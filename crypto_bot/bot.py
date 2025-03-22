"""
Основной модуль Telegram-бота для отслеживания курса криптовалют.
"""

import time
from threading import Thread
from typing import Dict, Optional

from telebot import TeleBot, types
from telebot.apihelper import ApiTelegramException
from requests.exceptions import RequestException

from crypto_bot import api
from crypto_bot import database as db
from crypto_bot import admin
from crypto_bot.config import (ADMIN_ID, DEFAULT_COINS, DEFAULT_THRESHOLD,
                               LOGGER_ID,
                               RETRY_PERIOD, TELEGRAM_TOKEN, setup_logger)

logger = setup_logger(__name__)

bot = TeleBot(TELEGRAM_TOKEN)

user_settings = {}

user_states = {}


def load_settings():
    """Загружает настройки пользователей из базы данных в память."""
    global user_settings
    user_settings = db.load_all_user_settings()
    logger.info(f"Загружены настройки для {len(user_settings)} пользователей")


def get_main_keyboard() -> types.ReplyKeyboardMarkup:
    """
    Формирует основную клавиатуру бота.

    Returns:
        types.ReplyKeyboardMarkup: Объект клавиатуры
    """
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_balance = types.KeyboardButton("Изменить количество монет")
    btn_threshold = types.KeyboardButton("Изменить порог уведомлений")
    btn_depozit = types.KeyboardButton("Указать вложение в монету")
    btn_info = types.KeyboardButton("Текущая информация")
    keyboard.add(btn_balance, btn_threshold, btn_depozit, btn_info)
    return keyboard


def send_message(chat_id: int, message: str, reply_markup: Optional[
    types.ReplyKeyboardMarkup] = None) -> None:
    """
    Отправляет сообщение в Telegram.
    Если пользователь заблокировал бота, удаляет его из базы данных.

    Args:
        chat_id: ID чата пользователя
        message: Текст сообщения
        reply_markup: Объект клавиатуры (опционально)
    """
    try:
        bot.send_message(chat_id, message, reply_markup=reply_markup,
                         parse_mode='HTML')
    except ApiTelegramException as error:
        if error.error_code == 403 and "bot was blocked by the user" in error.description:
            logger.warning(
                f"Бот заблокирован пользователем {chat_id}. Удаляем пользователя из БД.")
            db.remove_user(chat_id)

            if chat_id in user_settings:
                del user_settings[chat_id]
        else:
            logger.error(f"Ошибка отправки сообщения в чат {chat_id}: {error}")
    except RequestException as error:
        logger.error(
            f"Ошибка сети при отправке сообщения в чат {chat_id}: {error}")
    except Exception as error:
        logger.error(
            f"Неожиданная ошибка при отправке сообщения в чат {chat_id}: {error}")
    else:
        logger.debug(f"Сообщение отправлено в чат {chat_id}")


def price_checker() -> None:
    """
    Фоновая задача: регулярно проверяет курс криптовалют и отправляет уведомления.
    Запускается в отдельном потоке.
    """
    logger.info("Запущена фоновая задача отслеживания цен")

    while True:
        try:
            coin_ids = set()
            for chat_id, settings in user_settings.items():
                if "coin_id" in settings:
                    coin_ids.add(settings["coin_id"])

            if not coin_ids:
                logger.debug("Нет активных пользователей для отслеживания цен")
                time.sleep(RETRY_PERIOD)
                continue

            prices = api.get_multiple_prices(list(coin_ids))

            for chat_id, settings in list(user_settings.items()):
                coin_id = settings.get("coin_id")
                if not coin_id or coin_id not in prices or prices[
                    coin_id] is None:
                    continue

                current_price = prices[coin_id]
                balance = settings.get("balance")
                threshold = settings.get("threshold", DEFAULT_THRESHOLD)
                depozit = settings.get("depozit", 0)
                last_notified_price = settings.get("last_notified_price")

                if balance is None or last_notified_price is None:
                    user_settings[chat_id][
                        "last_notified_price"] = current_price
                    db.update_user_settings(chat_id,
                                            last_notified_price=current_price)
                    continue

                if abs(current_price - last_notified_price) >= threshold:
                    updated_balance = balance * current_price * 0.97
                    formatted_balance = f"{updated_balance:,.2f}".replace(",",
                                                                          " ")

                    coin_name = DEFAULT_COINS.get(coin_id, {}).get("name",
                                                                   coin_id.upper())
                    currency = DEFAULT_COINS.get(coin_id, {}).get("currency",
                                                                  "rub").upper()

                    message_parts = [
                        f"<b>Стоимость {coin_name}</b>: {current_price:,.2f} {currency}",
                        f"<b>Баланс</b>: {formatted_balance} {currency}"
                    ]

                    if depozit > 0:
                        profit = updated_balance - depozit
                        profit_percent = (profit / depozit) * 100

                        message_parts.append(
                            f"<b>Вложено</b>: {depozit:,.2f} {currency}")
                        message_parts.append(
                            f"<b>Прибыль</b>: {profit:,.2f} {currency} ({profit_percent:+.2f}%)"
                        )

                    message = "\n".join(message_parts)
                    send_message(chat_id, message)

                    if chat_id in user_settings:
                        user_settings[chat_id][
                            "last_notified_price"] = current_price
                        db.update_user_settings(chat_id,
                                                last_notified_price=current_price)

            for coin_id, price in prices.items():
                if price is not None:
                    db.update_coin_price(coin_id, price)

        except api.RateLimitError:
            logger.warning(
                "Превышен лимит запросов к API. Ожидаем перед следующей попыткой.")
            time.sleep(RETRY_PERIOD * 2)
            continue

        except Exception as error:
            logger.exception(f"Ошибка проверки цен: {error}")
            if LOGGER_ID:
                try:
                    send_message(int(LOGGER_ID),
                                 f"Ошибка проверки цен: {error}")
                except Exception:
                    pass

        time.sleep(RETRY_PERIOD)

@bot.message_handler(commands=["start"])
def send_welcome(message: types.Message) -> None:
    """
    Обработчик команды /start.
    Отправляет приветственное сообщение и инструкции по использованию.
    """
    chat_id = message.chat.id

    if chat_id not in user_settings:
        user_settings[chat_id] = {
            "coin_id": "fpi-bank",
            "balance": None,
            "threshold": DEFAULT_THRESHOLD,
            "depozit": 0,
            "last_notified_price": None
        }
        db.update_user_settings(chat_id)
        logger.info(f"Новый пользователь: {chat_id}")

    welcome_text = (
        "👋 <b>Привет!</b>\n\n"
        "Я бот для отслеживания курса криптовалюты.\n"
        "По умолчанию я отслеживаю монету <b>FPI Bank</b>, но в будущем смогу отслеживать и другие.\n\n"
        "<b>Для работы мне нужны следующие параметры:</b>\n"
        "• Количество монет (обязательно)\n"
        "• Порог уведомлений (по умолчанию 0.1)\n"
        "• Вложение в монету (опционально, для расчёта прибыли)\n\n"
        "Используйте кнопки ниже для быстрого ввода нужных параметров."
    )

    keyboard = get_main_keyboard()
    send_message(chat_id, welcome_text, reply_markup=keyboard)


@bot.message_handler(
    func=lambda message: message.text == "Изменить количество монет")
def request_balance(message: types.Message) -> None:
    """Запрашивает у пользователя количество монет."""
    chat_id = message.chat.id
    send_message(chat_id, "Введите новое количество монет:")
    user_states[chat_id] = "awaiting_balance"


@bot.message_handler(
    func=lambda message: message.text == "Изменить порог уведомлений")
def request_threshold(message: types.Message) -> None:
    """Запрашивает у пользователя порог уведомлений."""
    chat_id = message.chat.id
    send_message(chat_id, "Введите новый порог уведомлений (например, 0.1):")
    user_states[chat_id] = "awaiting_threshold"


@bot.message_handler(
    func=lambda message: message.text == "Указать вложение в монету")
def request_depozit(message: types.Message) -> None:
    """Запрашивает у пользователя сумму вложения."""
    chat_id = message.chat.id
    send_message(chat_id, "Введите сумму вложения в рублях:")
    user_states[chat_id] = "awaiting_depozit"


@bot.message_handler(func=lambda message: message.text == "Текущая информация")
def show_current_info(message: types.Message) -> None:
    """Показывает текущую информацию о цене и настройках пользователя."""
    chat_id = message.chat.id
    settings = user_settings.get(chat_id)

    if not settings:
        send_message(chat_id,
                     "Ваши настройки не найдены. Используйте /start для настройки бота.")
        return

    coin_id = settings.get("coin_id", "fpi-bank")
    balance = settings.get("balance")
    threshold = settings.get("threshold", DEFAULT_THRESHOLD)
    depozit = settings.get("depozit", 0)

    try:
        price, error = api.get_coin_price(coin_id)

        if price is None:
            send_message(chat_id, f"Не удалось получить текущую цену: {error}")
            return

        coin_name = DEFAULT_COINS.get(coin_id, {}).get("name", coin_id.upper())
        currency = DEFAULT_COINS.get(coin_id, {}).get("currency",
                                                      "rub").upper()

        info_parts = [
            f"<b>Монета</b>: {coin_name}",
            f"<b>Текущая цена</b>: {price:,.2f} {currency}",
            f"<b>Порог уведомлений</b>: {threshold:,.2f} {currency}"
        ]

        if balance is not None:
            updated_balance = balance * price * 0.97
            formatted_balance = f"{updated_balance:,.2f}".replace(",", " ")
            info_parts.append(f"<b>Количество монет</b>: {balance:,.2f}")
            info_parts.append(
                f"<b>Текущий баланс</b>: {formatted_balance} {currency}")

            if depozit > 0:
                profit = updated_balance - depozit
                profit_percent = (profit / depozit) * 100
                info_parts.append(f"<b>Вложено</b>: {depozit:,.2f} {currency}")
                info_parts.append(
                    f"<b>Прибыль/убыток</b>: {profit:,.2f} {currency} ({profit_percent:+.2f}%)"
                )
        else:
            info_parts.append("<b>Количество монет</b>: не указано")

        message = "\n".join(info_parts)
        send_message(chat_id, message, reply_markup=get_main_keyboard())

    except Exception as error:
        logger.error(f"Ошибка при получении информации: {error}")
        send_message(
            chat_id,
            "Произошла ошибка при получении информации. Пожалуйста, попробуйте позже.",
            reply_markup=get_main_keyboard()
        )


@bot.message_handler(func=lambda message: user_states.get(
    message.chat.id) == "awaiting_balance")
def set_balance(message: types.Message) -> None:
    """Устанавливает количество монет."""
    chat_id = message.chat.id
    try:
        balance = float(message.text.replace(',', '.'))

        if balance <= 0:
            send_message(chat_id,
                         "Количество монет должно быть положительным числом.")
            return

        user_settings[chat_id]["balance"] = balance
        db.update_user_settings(chat_id, balance=balance)

        send_message(
            chat_id,
            f"Количество монет обновлено: <b>{balance:,.2f}</b>",
            reply_markup=get_main_keyboard()
        )

        user_states.pop(chat_id, None)

    except ValueError:
        send_message(chat_id,
                     "Ошибка. Введите корректное число для количества монет:")


@bot.message_handler(func=lambda message: user_states.get(
    message.chat.id) == "awaiting_threshold")
def set_threshold(message: types.Message) -> None:
    """Устанавливает порог уведомлений."""
    chat_id = message.chat.id
    try:
        threshold = float(message.text.replace(',', '.'))

        if threshold <= 0:
            send_message(chat_id,
                         "Порог уведомлений должен быть положительным числом.")
            return

        user_settings[chat_id]["threshold"] = threshold
        db.update_user_settings(chat_id, threshold=threshold)

        send_message(
            chat_id,
            f"Порог уведомлений обновлен: <b>{threshold:,.2f}</b>",
            reply_markup=get_main_keyboard()
        )

        user_states.pop(chat_id, None)

    except ValueError:
        send_message(chat_id,
                     "Ошибка. Введите корректное число для порога уведомлений:")


@bot.message_handler(func=lambda message: user_states.get(
    message.chat.id) == "awaiting_depozit")
def set_depozit(message: types.Message) -> None:
    """Устанавливает сумму вложения."""
    chat_id = message.chat.id
    try:
        depozit = float(message.text.replace(',', '.'))

        if depozit < 0:
            send_message(chat_id,
                         "Сумма вложения не может быть отрицательной.")
            return

        user_settings[chat_id]["depozit"] = depozit
        db.update_user_settings(chat_id, depozit=depozit)

        send_message(
            chat_id,
            f"Сумма вложения обновлена: <b>{depozit:,.2f}</b>",
            reply_markup=get_main_keyboard()
        )

        user_states.pop(chat_id, None)

    except ValueError:
        send_message(chat_id,
                     "Ошибка. Введите корректное число для суммы вложения:")


admin.register_admin_handlers(bot, send_message)


@bot.message_handler(func=lambda message: True)
def echo_all(message: types.Message) -> None:
    """Обрабатывает все остальные сообщения."""
    chat_id = message.chat.id
    send_message(
        chat_id,
        "Я не понимаю эту команду. Используйте кнопки меню или /start для настройки бота.",
        reply_markup=get_main_keyboard()
    )
