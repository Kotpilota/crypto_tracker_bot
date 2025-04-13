from django.db import models
from django.utils import timezone


class TelegramUser(models.Model):
    """Модель пользователя Telegram"""
    chat_id = models.BigIntegerField(primary_key=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    registered_at = models.DateTimeField(default=timezone.now)
    last_active = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Пользователь Telegram'
        verbose_name_plural = 'Пользователи Telegram'

    def __str__(self):
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''} ({self.chat_id})"
        return f"User {self.chat_id}"


class UserSettings(models.Model):
    """Настройки пользователя"""
    user = models.OneToOneField(
        TelegramUser,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='settings'
    )
    coin_id = models.CharField(max_length=50, default='fpi-bank')
    balance = models.FloatField(null=True, blank=True)
    threshold = models.FloatField(default=0.1)
    depozit = models.FloatField(default=0)
    last_notified_price = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = 'Настройки пользователя'
        verbose_name_plural = 'Настройки пользователей'

    def __str__(self):
        return f"Настройки для {self.user}"


class Cryptocurrency(models.Model):
    """Информация о криптовалюте"""
    coin_id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=10, default='rub')
    description = models.TextField(blank=True, null=True)
    icon = models.ImageField(upload_to='crypto_icons/', null=True, blank=True)

    class Meta:
        verbose_name = 'Криптовалюта'
        verbose_name_plural = 'Криптовалюты'

    def __str__(self):
        return f"{self.name} ({self.coin_id})"


class PriceData(models.Model):
    """Данные о ценах криптовалют"""
    id = models.AutoField(primary_key=True)
    cryptocurrency = models.ForeignKey(
        Cryptocurrency,
        on_delete=models.CASCADE,
        related_name='prices'
    )
    price = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Цена криптовалюты'
        verbose_name_plural = 'Цены криптовалют'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['cryptocurrency', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.cryptocurrency.name}: {self.price} ({self.timestamp})"


class AdminBroadcast(models.Model):
    """Модель для хранения рассылок администратора"""
    id = models.AutoField(primary_key=True)
    admin_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='broadcasts'
    )
    message_text = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    total_recipients = models.IntegerField(default=0)
    successful_deliveries = models.IntegerField(default=0)
    failed_deliveries = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Рассылка администратора'
        verbose_name_plural = 'Рассылки администратора'
        ordering = ['-sent_at']

    def __str__(self):
        return f"Рассылка от {self.sent_at.strftime('%d.%m.%Y %H:%M')}"


class BroadcastRecipient(models.Model):
    """Модель для отслеживания получателей рассылки"""
    id = models.AutoField(primary_key=True)
    broadcast = models.ForeignKey(
        AdminBroadcast,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE
    )
    delivered = models.BooleanField(default=False)
    delivery_time = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Получатель рассылки'
        verbose_name_plural = 'Получатели рассылки'
        unique_together = ['broadcast', 'user']

    def __str__(self):
        status = "доставлено" if self.delivered else "не доставлено"
        return f"Сообщение для {self.user}: {status}"