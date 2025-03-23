import time

from telebot import TeleBot, types
from telebot.apihelper import ApiTelegramException
from requests.exceptions import RequestException

from crypto_bot import api
from crypto_bot import database as db
from crypto_bot import admin
from crypto_bot.config import (DEFAULT_COINS, DEFAULT_THRESHOLD,
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


def set_menu_button():
    """
    Устанавливает кнопку меню в левой части интерфейса бота.
    """
    commands = [
        types.BotCommand(command="start", description="Запустить бота"),
        types.BotCommand(command="menu", description="Открыть главное меню")
    ]
    bot.set_my_commands(commands)


def get_main_menu_keyboard() -> types.InlineKeyboardMarkup:
    """
    Формирует основную встроенную клавиатуру бота для управления настройками криптовалют.

    Returns:
        types.InlineKeyboardMarkup: Объект встроенной клавиатуры
    """
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    btn_info = types.InlineKeyboardButton("Текущая информация 📊", callback_data="current_info")
    btn_balance = types.InlineKeyboardButton("Изменить кол-во монет 🪙", callback_data="set_balance")
    keyboard.row(btn_info, btn_balance)

    btn_threshold = types.InlineKeyboardButton("Порог уведомлений ⚙️", callback_data="set_threshold")
    btn_deposit = types.InlineKeyboardButton("Указать вложение 💰", callback_data="set_deposit")
    keyboard.row(btn_threshold, btn_deposit)

    btn_price_alerts = types.InlineKeyboardButton("Настройка уведомлений о цене 🔔", callback_data="price_alerts")
    keyboard.row(btn_price_alerts)

    btn_help = types.InlineKeyboardButton("Помощь ❓", callback_data="help_info")
    keyboard.row(btn_help)

    return keyboard


def get_back_to_menu_keyboard() -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой возврата в меню.
    """
    keyboard = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("« Вернуться в меню", callback_data="back_to_menu")
    keyboard.add(btn_back)
    return keyboard


def send_message(chat_id: int, message: str, reply_markup=None, parse_mode='HTML') -> None:
    """
    Отправляет сообщение в Telegram.
    Если пользователь заблокировал бота, удаляет его из базы данных.

    Args:
        chat_id: ID чата пользователя
        message: Текст сообщения
        reply_markup: Объект клавиатуры (опционально)
        parse_mode: Режим разметки текста (по умолчанию HTML)
    """
    try:
        bot.send_message(chat_id, message, reply_markup=reply_markup,
                         parse_mode=parse_mode)
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


@bot.message_handler(commands=["start", "menu"])
def send_welcome(message: types.Message) -> None:
    """
    Обработчик команд /start и /menu.
    Отправляет приветственное сообщение и меню.
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
        "<b>👋 Добро пожаловать в Crypto Tracker!</b>\n\n"
        "Я бот для отслеживания курса криптовалюты FPI Bank.\n"
        "Вы можете настроить количество монет, получать уведомления "
        "об изменении курса и отслеживать вашу прибыль.\n\n"
        "Используйте кнопки ниже для настройки."
    )

    keyboard = get_main_menu_keyboard()
    send_message(chat_id, welcome_text, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call: types.CallbackQuery) -> None:
    """
    Обработчик нажатий на встроенные кнопки.
    """
    chat_id = call.message.chat.id

    bot.answer_callback_query(call.id)

    if call.data == "current_info":
        show_current_info(call.message)
    elif call.data == "set_balance":
        request_balance(call.message)
    elif call.data == "set_threshold":
        request_threshold(call.message)
    elif call.data == "set_deposit":
        request_depozit(call.message)
    elif call.data == "price_alerts":
        threshold = user_settings.get(chat_id, {}).get("threshold", DEFAULT_THRESHOLD)
        alerts_info = (
            "<b>🔔 Настройка уведомлений о цене</b>\n\n"
            "Уведомления отправляются когда цена изменяется на величину, "
            "большую или равную указанному порогу.\n\n"
            f"Текущий порог: <b>{threshold}</b> руб.\n\n"
            "Используйте кнопку 'Порог уведомлений' для изменения этого значения."
        )

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=alerts_info,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode='HTML'
        )
    elif call.data == "help_info":
        help_text = (
            "<b>❓ Справка</b>\n\n"
            "<b>Как пользоваться ботом:</b>\n"
            "1. Укажите количество имеющихся у вас монет\n"
            "2. При желании укажите сумму вложения для расчета прибыли\n"
            "3. Настройте порог уведомлений\n\n"
            "Бот будет автоматически отслеживать изменения курса и уведомлять вас "
            "когда цена изменится на величину, превышающую указанный порог.\n\n"
            "По любым вопросам обращайтесь к администратору: @kotpilota"
        )

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=help_text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode='HTML'
        )
    elif call.data == "back_to_menu":
        back_to_menu(call)
    elif call.data == "open_menu":
        open_menu_from_button(call)


def request_balance(message: types.Message) -> None:
    """Запрашивает у пользователя количество монет."""
    chat_id = message.chat.id

    text = (
        "<b>🪙 Изменение количества монет</b>\n\n"
        "Введите новое количество монет:"
    )

    if hasattr(message, 'message_id'):
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message.message_id,
            text=text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode='HTML'
        )
    else:
        send_message(chat_id, text, reply_markup=get_back_to_menu_keyboard())

    user_states[chat_id] = "awaiting_balance"


def request_threshold(message: types.Message) -> None:
    """Запрашивает у пользователя порог уведомлений."""
    chat_id = message.chat.id

    text = (
        "<b>⚙️ Настройка порога уведомлений</b>\n\n"
        "Введите новый порог уведомлений (например, 0.1):"
    )

    if hasattr(message, 'message_id'):
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message.message_id,
            text=text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode='HTML'
        )
    else:
        send_message(chat_id, text, reply_markup=get_back_to_menu_keyboard())

    user_states[chat_id] = "awaiting_threshold"


def request_depozit(message: types.Message) -> None:
    """Запрашивает у пользователя сумму вложения."""
    chat_id = message.chat.id

    text = (
        "<b>💰 Указание вложения</b>\n\n"
        "Введите сумму вложения в рублях:"
    )

    if hasattr(message, 'message_id'):
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message.message_id,
            text=text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode='HTML'
        )
    else:
        send_message(chat_id, text, reply_markup=get_back_to_menu_keyboard())

    user_states[chat_id] = "awaiting_depozit"


def show_current_info(message: types.Message) -> None:
    """Показывает текущую информацию о цене и настройках пользователя."""
    chat_id = message.chat.id
    settings = user_settings.get(chat_id)

    if not settings:
        text = "Ваши настройки не найдены. Используйте /menu для настройки бота."
        if hasattr(message, 'message_id'):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message.message_id,
                text=text,
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            send_message(chat_id, text)
        return

    coin_id = settings.get("coin_id", "fpi-bank")
    balance = settings.get("balance")
    threshold = settings.get("threshold", DEFAULT_THRESHOLD)
    depozit = settings.get("depozit", 0)

    try:
        price, error = api.get_coin_price(coin_id)

        if price is None:
            text = f"Не удалось получить текущую цену: {error}"
            if hasattr(message, 'message_id'):
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message.message_id,
                    text=text,
                    reply_markup=get_back_to_menu_keyboard()
                )
            else:
                send_message(chat_id, text, reply_markup=get_back_to_menu_keyboard())
            return

        coin_name = DEFAULT_COINS.get(coin_id, {}).get("name", coin_id.upper())
        currency = DEFAULT_COINS.get(coin_id, {}).get("currency", "rub").upper()

        info_parts = [
            f"<b>📊 Информация о {coin_name}</b>",
            f"<b>💵 Текущая цена</b>: {price:,.2f} {currency}",
            f"<b>⚙️ Порог уведомлений</b>: {threshold:,.2f} {currency}"
        ]

        if balance is not None:
            updated_balance = balance * price * 0.97
            formatted_balance = f"{updated_balance:,.2f}".replace(",", " ")
            info_parts.append(f"<b>🪙 Количество монет</b>: {balance:,.2f}")
            info_parts.append(
                f"<b>💰 Текущий баланс</b>: {formatted_balance} {currency}")

            if depozit > 0:
                profit = updated_balance - depozit
                profit_percent = (profit / depozit) * 100
                info_parts.append(f"<b>💸 Вложено</b>: {depozit:,.2f} {currency}")
                info_parts.append(
                    f"<b>📈 Прибыль/убыток</b>: {profit:,.2f} {currency} ({profit_percent:+.2f}%)"
                )
        else:
            info_parts.append("<b>🪙 Количество монет</b>: не указано")

        message_text = "\n\n".join(info_parts)

        if hasattr(message, 'message_id'):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message.message_id,
                text=message_text,
                reply_markup=get_back_to_menu_keyboard(),
                parse_mode='HTML'
            )
        else:
            send_message(
                chat_id,
                message_text,
                reply_markup=get_back_to_menu_keyboard()
            )

    except Exception as error:
        logger.error(f"Ошибка при получении информации: {error}")

        error_text = "Произошла ошибка при получении информации. Пожалуйста, попробуйте позже."

        if hasattr(message, 'message_id'):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message.message_id,
                text=error_text,
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            send_message(
                chat_id,
                error_text,
                reply_markup=get_back_to_menu_keyboard()
            )


@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call: types.CallbackQuery) -> None:
    """Возвращает пользователя в главное меню."""
    chat_id = call.message.chat.id

    user_states.pop(chat_id, None)

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="Выберите действие:",
        reply_markup=get_main_menu_keyboard()
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

        success_text = (
            "<b>✅ Успешно!</b>\n\n"
            f"Количество монет обновлено: <b>{balance:,.2f}</b>"
        )

        send_message(chat_id, success_text)

        keyboard = get_main_menu_keyboard()
        send_message(chat_id, "Выберите действие:", reply_markup=keyboard)

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

        success_text = (
            "<b>✅ Успешно!</b>\n\n"
            f"Порог уведомлений обновлен: <b>{threshold:,.2f}</b>"
        )

        send_message(chat_id, success_text)

        keyboard = get_main_menu_keyboard()
        send_message(chat_id, "Выберите действие:", reply_markup=keyboard)

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

        success_text = (
            "<b>✅ Успешно!</b>\n\n"
            f"Сумма вложения обновлена: <b>{depozit:,.2f}</b>"
        )

        send_message(chat_id, success_text)

        keyboard = get_main_menu_keyboard()
        send_message(chat_id, "Выберите действие:", reply_markup=keyboard)

        user_states.pop(chat_id, None)

    except ValueError:
        send_message(chat_id,
                     "Ошибка. Введите корректное число для суммы вложения:")


@bot.callback_query_handler(func=lambda call: call.data == "open_menu")
def open_menu_from_button(call: types.CallbackQuery) -> None:
    """Открывает меню при нажатии на кнопку."""
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    keyboard = get_main_menu_keyboard()
    send_message(chat_id, "Выберите действие:", reply_markup=keyboard)


@bot.message_handler(func=lambda message: True)
def echo_all(message: types.Message) -> None:
    """Обрабатывает все остальные сообщения."""
    chat_id = message.chat.id

    if message.text.lower() == '/menu':
        send_welcome(message)
        return

    if chat_id in user_states:
        return

    send_message(
        chat_id,
        "Я не понимаю эту команду. Используйте /menu для вызова меню бота."
    )
    menu_button = types.InlineKeyboardMarkup()
    btn_menu = types.InlineKeyboardButton("Открыть меню", callback_data="open_menu")
    menu_button.add(btn_menu)
    send_message(chat_id, "Или нажмите на кнопку ниже:", reply_markup=menu_button)


admin.register_admin_handlers(bot, send_message)
