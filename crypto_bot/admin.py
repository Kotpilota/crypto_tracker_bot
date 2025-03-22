from typing import Callable, Dict, Union
import time

from telebot import TeleBot, types
from telebot.apihelper import ApiTelegramException

from crypto_bot import database as db
from crypto_bot.config import ADMIN_ID, DEFAULT_COINS, setup_logger

logger = setup_logger(__name__)

admin_states: Dict[int, str] = {}


def check_admin(chat_id: Union[int, str]) -> bool:
    """
    Проверяет, является ли пользователь администратором.

    Args:
        chat_id: ID чата пользователя

    Returns:
        bool: True если пользователь администратор, иначе False
    """
    return ADMIN_ID and str(chat_id) == str(ADMIN_ID)


def get_admin_keyboard() -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру для административных функций.

    Returns:
        types.InlineKeyboardMarkup: Объект клавиатуры
    """
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    broadcast_btn = types.InlineKeyboardButton(
        "Отправить сообщение всем",
        callback_data="admin_broadcast"
    )

    stats_btn = types.InlineKeyboardButton(
        "Статистика использования",
        callback_data="admin_stats"
    )

    keyboard.add(broadcast_btn, stats_btn)
    return keyboard


def register_admin_handlers(bot: TeleBot, send_message_func: Callable) -> None:
    """
    Регистрирует обработчики команд администратора.

    Args:
        bot: Экземпляр бота
        send_message_func: Функция для отправки сообщений
    """

    @bot.message_handler(commands=["admin"])
    def admin_command(message: types.Message) -> None:
        """
        Обработчик команды /admin.
        Доступен только администратору.
        Показывает административную панель.
        """
        chat_id = message.chat.id

        if not check_admin(chat_id):
            send_message_func(chat_id,
                              "У вас нет прав доступа к этой команде.")
            return

        admin_menu_text = (
            "<b>Панель администратора</b>\n\n"
            "Выберите действие из меню ниже:"
        )

        keyboard = get_admin_keyboard()
        send_message_func(chat_id, admin_menu_text, reply_markup=keyboard)

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("admin_"))
    def admin_callback_handler(call: types.CallbackQuery) -> None:
        """
        Обработчик кнопок административной панели.
        """
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if not check_admin(chat_id):
            bot.answer_callback_query(call.id,
                                      "У вас нет прав доступа к этой функции.")
            return

        if call.data == "admin_broadcast":
            bot.answer_callback_query(call.id, "Режим рассылки активирован")

            broadcast_request = (
                "<b>Режим рассылки сообщений</b>\n\n"
                "Введите текст сообщения, которое будет отправлено всем пользователям бота.\n\n"
                "Поддерживается HTML-форматирование.\n"
                "Для отмены отправьте /cancel"
            )

            admin_states[chat_id] = "awaiting_broadcast_text"

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=broadcast_request,
                parse_mode='HTML',
                reply_markup=None
            )

        elif call.data == "admin_stats":
            bot.answer_callback_query(call.id, "Загрузка статистики...")

            stats_text = get_admin_stats()

            back_keyboard = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton(
                "Назад",
                callback_data="admin_back_to_menu"
            )
            back_keyboard.add(back_btn)

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=stats_text,
                parse_mode='HTML',
                reply_markup=back_keyboard
            )

        elif call.data == "admin_back_to_menu":
            admin_menu_text = (
                "<b>Панель администратора</b>\n\n"
                "Выберите действие из меню ниже:"
            )

            keyboard = get_admin_keyboard()

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=admin_menu_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )

    @bot.message_handler(func=lambda message: admin_states.get(
        message.chat.id) == "awaiting_broadcast_text")
    def process_broadcast_text(message: types.Message) -> None:
        """
        Обработчик текста для рассылки.
        """
        chat_id = message.chat.id

        if message.text.strip().lower() == '/cancel':
            admin_states.pop(chat_id, None)
            send_message_func(
                chat_id,
                "Рассылка отменена. Для возврата в панель администратора используйте /admin"
            )
            return

        broadcast_text = message.text

        confirmation_text = (
            "<b>Подтверждение рассылки</b>\n\n"
            "Вы собираетесь отправить следующее сообщение всем пользователям:\n\n"
            f"{broadcast_text}\n\n"
            "Для подтверждения отправьте <b>y</b> или <b>да</b>\n"
            "Для отмены отправьте <b>n</b> или <b>нет</b>"
        )

        admin_states[chat_id] = f"confirming_broadcast:{broadcast_text}"
        send_message_func(chat_id, confirmation_text)

    @bot.message_handler(func=lambda message: admin_states.get(
        message.chat.id, "").startswith("confirming_broadcast:"))
    def process_broadcast_confirmation_text(message: types.Message) -> None:
        """
        Обработчик текстового подтверждения рассылки (y/n).
        """
        chat_id = message.chat.id
        response = message.text.strip().lower()

        logger.info(f"Получен ответ: {response} от пользователя {chat_id}")

        if not check_admin(chat_id):
            logger.info(f"Пользователь {chat_id} не является администратором")
            send_message_func(chat_id,
                              "У вас нет прав доступа к этой функции.")
            return

        state = admin_states.get(chat_id, "")
        if not state.startswith("confirming_broadcast:"):
            logger.error("Сессия подтверждения рассылки истекла")
            send_message_func(chat_id,
                              "Сессия подтверждения рассылки истекла.")
            return

        if response in ('n', 'н', 'нет', 'no', 'cancel', 'отмена'):
            logger.info("Рассылка отменена администратором")
            admin_states.pop(chat_id, None)
            send_message_func(
                chat_id,
                "Рассылка отменена. Для возврата в панель администратора используйте /admin"
            )
            return

        if response in ('y', 'д', 'да', 'yes', 'ok', 'ок'):
            logger.info("Администратор подтвердил рассылку")

            broadcast_text = state.split(":", 1)[1]
            logger.info(f"Текст для рассылки: {broadcast_text[:50]}...")

            send_message_func(chat_id, "Начинаем рассылку сообщений...")

            logger.info("Вызываем функцию broadcast_message")
            result = broadcast_message(bot, broadcast_text)
            logger.info(f"Функция broadcast_message вернула: {result}")

            report = (
                "<b>Результаты рассылки</b>\n\n"
                f"Сообщение успешно отправлено: {result['success']} пользователям\n"
                f"Не отправлено: {result['failed']} пользователям\n\n"
                "Для возврата в панель администратора используйте /admin"
            )

            logger.info("Отправляем отчет администратору")
            send_message_func(chat_id, report)

            # Сбрасываем состояние
            admin_states.pop(chat_id, None)
            logger.info("Состояние сброшено, рассылка завершена")
            return

        send_message_func(
            chat_id,
            "Не понял ваш ответ. Отправьте <b>y</b> для подтверждения или <b>n</b> для отмены."
        )


def get_admin_stats() -> str:
    """
    Получает статистику использования бота.

    Returns:
        str: Текст со статистикой
    """
    user_count = db.get_users_count()

    coin_info = []
    for coin_id, coin_data in DEFAULT_COINS.items():
        price = db.get_coin_price(coin_id)
        currency = coin_data.get('currency', 'rub').upper()
        name = coin_data.get('name', coin_id)

        if price:
            coin_info.append(f"{name}: {price:,.2f} {currency}")
        else:
            coin_info.append(f"{name}: цена недоступна")

    users_with_balance = 0
    users_with_deposit = 0

    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM user_settings WHERE balance IS NOT NULL")
        row = cursor.fetchone()
        if row:
            users_with_balance = row[0]

        cursor.execute("SELECT COUNT(*) FROM user_settings WHERE depozit > 0")
        row = cursor.fetchone()
        if row:
            users_with_deposit = row[0]

    stats_parts = [
        "<b>📊 Статистика использования бота</b>",
        f"👥 Всего пользователей: <b>{user_count}</b>",
        f"📈 Пользователей с указанным балансом: <b>{users_with_balance}</b>",
        f"💰 Пользователей с указанными вложениями: <b>{users_with_deposit}</b>",
    ]

    if coin_info:
        stats_parts.append("\n<b>💲 Текущие цены криптовалют:</b>")
        stats_parts.extend(coin_info)

    return "\n".join(stats_parts)


def broadcast_message(bot: TeleBot, text: str) -> Dict[str, int]:
    """
    Отправляет сообщение всем пользователям бота с увеличенной задержкой.
    """
    logger.info("Начинаем рассылку сообщений")

    user_ids = []
    try:
        with db.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id FROM user_settings")
            rows = cursor.fetchall()
            user_ids = [row[0] for row in rows]
        logger.info(f"Получен список пользователей: {user_ids}")
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
        return {"success": 0, "failed": 0}

    results = {"success": 0, "failed": 0}

    header = "<b>📣 Объявление от администратора</b>\n\n"
    full_message = f"{header}{text}"

    logger.info(f"Начинаем отправку сообщений {len(user_ids)} пользователям")

    for i, chat_id in enumerate(user_ids):
        try:
            logger.info(
                f"Отправляем сообщение пользователю {chat_id} ({i + 1}/{len(user_ids)})")
            if i > 0:
                logger.info(
                    f"Ждем 3 секунды перед отправкой следующего сообщения")
                time.sleep(0.5)

            bot.send_message(chat_id, full_message, parse_mode='HTML')
            logger.info(f"Сообщение успешно отправлено пользователю {chat_id}")
            results["success"] += 1

        except ApiTelegramException as error:
            logger.error(
                f"Telegram API ошибка для пользователя {chat_id}: {error}")
            if error.error_code == 403 and "bot was blocked by the user" in error.description:
                logger.warning(
                    f"Пользователь {chat_id} заблокировал бота. Удаляем из базы данных.")
                db.remove_user(chat_id)
            results["failed"] += 1

        except Exception as e:
            logger.error(
                f"Неизвестная ошибка при отправке сообщения пользователю {chat_id}: {e}")
            results["failed"] += 1

    logger.info(
        f"Рассылка завершена. Успешно: {results['success']}, Ошибок: {results['failed']}")
    return results
