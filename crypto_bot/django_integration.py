import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crypto_django.settings')
django.setup()

# Импорт моделей Django
from web.models import TelegramUser, UserSettings, Cryptocurrency, PriceData


def get_or_create_user(chat_id, username=None, first_name=None, last_name=None):
    """
    Получает или создает пользователя Telegram
    """
    user, created = TelegramUser.objects.get_or_create(
        chat_id=chat_id,
        defaults={
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
        }
    )

    if not created and (username or first_name or last_name):
        # Обновляем информацию о пользователе
        if username and user.username != username:
            user.username = username
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        if last_name and user.last_name != last_name:
            user.last_name = last_name
        user.save()

    return user, created


def get_user_settings(chat_id):
    """
    Получает настройки пользователя
    """
    try:
        user = TelegramUser.objects.get(chat_id=chat_id)
        settings, created = UserSettings.objects.get_or_create(
            user=user,
            defaults={
                'coin_id': 'fpi-bank',
                'threshold': 0.1
            }
        )
        return settings
    except (TelegramUser.DoesNotExist, UserSettings.DoesNotExist):
        return None


def update_user_settings(chat_id, **kwargs):
    """
    Обновляет настройки пользователя
    """
    user, _ = get_or_create_user(chat_id)

    settings, created = UserSettings.objects.get_or_create(
        user=user,
        defaults={
            'coin_id': kwargs.get('coin_id', 'fpi-bank'),
            'balance': kwargs.get('balance'),
            'threshold': kwargs.get('threshold', 0.1),
            'depozit': kwargs.get('depozit', 0),
            'last_notified_price': kwargs.get('last_notified_price')
        }
    )

    if not created:
        for key, value in kwargs.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        settings.save()

    return settings


def get_or_create_cryptocurrency(coin_id, name=None, currency=None):
    """
    Получает или создает запись о криптовалюте
    """
    crypto, created = Cryptocurrency.objects.get_or_create(
        coin_id=coin_id,
        defaults={
            'name': name or coin_id.upper(),
            'currency': currency or 'rub'
        }
    )
    return crypto


def update_coin_price(coin_id, price):
    """
    Обновляет цену монеты и создает запись в истории
    """
    crypto = get_or_create_cryptocurrency(coin_id)

    # Создаем запись в истории цен
    price_record = PriceData.objects.create(
        cryptocurrency=crypto,
        price=price
    )

    return price_record


def get_all_users_settings():
    """
    Получает настройки всех пользователей
    """
    settings = {}
    for user_setting in UserSettings.objects.select_related('user').all():
        chat_id = user_setting.user.chat_id
        settings[chat_id] = {
            'coin_id': user_setting.coin_id,
            'balance': user_setting.balance,
            'threshold': user_setting.threshold,
            'depozit': user_setting.depozit,
            'last_notified_price': user_setting.last_notified_price
        }
    return settings


def get_coin_price(coin_id):
    """
    Получает текущую цену монеты
    """
    try:
        latest_price = PriceData.objects.filter(
            cryptocurrency__coin_id=coin_id
        ).order_by('-timestamp').first()

        if latest_price:
            return latest_price.price
        return None
    except Exception:
        return None


def get_users_count():
    """
    Получает количество пользователей
    """
    return TelegramUser.objects.count()


def remove_user(chat_id):
    """
    Удаляет пользователя
    """
    try:
        user = TelegramUser.objects.get(chat_id=chat_id)
        user.delete()
        return True
    except TelegramUser.DoesNotExist:
        return False