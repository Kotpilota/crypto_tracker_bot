# CryptoTrackerBot

Telegram-бот для отслеживания курса криптовалют с возможностью настройки уведомлений об изменении цены.

## Функциональные возможности

- 📈 Отслеживание курса криптовалют (по умолчанию FPI Bank)
- 🔔 Настраиваемые уведомления об изменении цены
- 💰 Расчет текущего баланса с учетом количества монет
- 💹 Расчет прибыли/убытка относительно вложенной суммы
- 🔐 Безопасное хранение пользовательских настроек в базе данных SQLite
- 📊 Административная статистика использования бота

## Технологии

- Python 3.7+
- pyTelegramBotAPI для взаимодействия с Telegram API
- Requests для работы с CoinGecko API
- SQLite для хранения данных пользователей
- Python-dotenv для работы с переменными окружения

## Установка и запуск

### Предварительные требования

- Python 3.7 или выше
- Токен Telegram-бота (получите у [@BotFather](https://t.me/BotFather))
- Желательно: API ключ CoinGecko для увеличения лимита запросов

### Шаги по установке

1. Клонируйте репозиторий:
   ```
   git clone https://github.com/your-username/crypto-tracker-bot.git
   cd crypto-tracker-bot
   ```

2. Создайте и активируйте виртуальное окружение:
   ```
   python -m venv venv
   source venv/bin/activate  # На Windows: venv\Scripts\activate
   ```

3. Установите зависимости:
   ```
   pip install -r requirements.txt
   ```

4. Создайте файл `.env` на основе примера:
   ```
   cp .env.example .env
   ```

5. Отредактируйте файл `.env`, добавив свои значения:
   ```
   TELEGRAM_TOKEN=your_telegram_bot_token
   ADMIN_ID=your_telegram_id  # опционально
   LOGGER_ID=your_telegram_id  # опционально
   COINGECKO_API_KEY=your_coingecko_api_key  # опционально
   ```

6. Запустите бота:
   ```
   python main.py
   ```

## Использование

1. Найдите своего бота в Telegram и отправьте команду `/start`
2. Используйте кнопки меню для настройки:
   - "Изменить количество монет" - указать количество монет
   - "Изменить порог уведомлений" - настроить чувствительность уведомлений
   - "Указать вложение в монету" - для расчета прибыли/убытка
   - "Текущая информация" - просмотр текущего курса и баланса

## Структура проекта

```
crypto_tracker_bot/
├── main.py                  # Точка входа в приложение
├── crypto_bot/              # Основной пакет приложения
│   ├── __init__.py          # Инициализация пакета
│   ├── logs/                # Директория для логов
│   ├── config.py            # Конфигурационные переменные и константы
│   ├── database.py          # Модуль для работы с базой данных
│   ├── api.py               # Модуль для работы с внешними API
│   ├── bot.py               # Основная логика бота
│   └── utils.py             # Вспомогательные функции
├── requirements.txt         # Зависимости проекта
└── .env.example             # Пример файла переменных окружения
```

## Расширение функциональности

Вы можете легко расширить функциональность бота:

### Добавление новых криптовалют

Для добавления новой криптовалюты отредактируйте константу `DEFAULT_COINS` в файле `config.py`:

```python
DEFAULT_COINS = {
    "fpi-bank": {
        "name": "FPI Bank",
        "currency": "rub"
    },
    "bitcoin": {
        "name": "Bitcoin",
        "currency": "usd"
    },
    # Добавьте сюда новые монеты
}
```

### Настройка уведомлений

Частоту проверки курса можно настроить через переменную окружения `RETRY_PERIOD` в файле `.env` (значение указывается в секундах).

## Администрирование

Если вы указали свой Telegram ID в переменной `ADMIN_ID`, вы можете использовать команду `/admin` для получения статистики:
- Количество активных пользователей
- Текущие цены отслеживаемых монет

## Поддержка и содействие

Если у вас есть предложения по улучшению бота или вы нашли ошибку, пожалуйста, создайте Issue или Pull Request.

## Автор

Данил Шифман - [@Kotpilota](https://github.com/Kotpilota)