from django.contrib import admin
from .models import TelegramUser, UserSettings, Cryptocurrency, PriceData, AdminBroadcast, BroadcastRecipient


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('chat_id', 'username', 'first_name', 'last_name', 'registered_at', 'last_active')
    search_fields = ('chat_id', 'username', 'first_name', 'last_name')
    list_filter = ('registered_at', 'last_active')
    date_hierarchy = 'registered_at'


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'coin_id', 'balance', 'threshold', 'depozit', 'last_notified_price')
    search_fields = ('user__chat_id',)
    list_filter = ('coin_id',)
    list_editable = ('threshold',)


@admin.register(Cryptocurrency)
class CryptocurrencyAdmin(admin.ModelAdmin):
    list_display = ('coin_id', 'name', 'currency')
    search_fields = ('coin_id', 'name')
    list_filter = ('currency',)


@admin.register(PriceData)
class PriceDataAdmin(admin.ModelAdmin):
    list_display = ('cryptocurrency', 'price', 'timestamp')
    search_fields = ('cryptocurrency__name', 'cryptocurrency__coin_id')
    list_filter = ('cryptocurrency', 'timestamp')
    date_hierarchy = 'timestamp'


class BroadcastRecipientInline(admin.TabularInline):
    model = BroadcastRecipient
    extra = 0
    readonly_fields = ('user', 'delivered', 'delivery_time', 'error_message')
    can_delete = False
    max_num = 0


@admin.register(AdminBroadcast)
class AdminBroadcastAdmin(admin.ModelAdmin):
    list_display = ('id', 'admin_user', 'sent_at', 'total_recipients', 'successful_deliveries', 'failed_deliveries')
    search_fields = ('message_text', 'admin_user__username')
    list_filter = ('sent_at',)
    date_hierarchy = 'sent_at'
    readonly_fields = ('admin_user', 'sent_at', 'total_recipients', 'successful_deliveries', 'failed_deliveries')
    inlines = [BroadcastRecipientInline]


@admin.register(BroadcastRecipient)
class BroadcastRecipientAdmin(admin.ModelAdmin):
    list_display = ('broadcast', 'user', 'delivered', 'delivery_time')
    search_fields = ('user__chat_id', 'user__username')
    list_filter = ('delivered', 'delivery_time')
    readonly_fields = ('broadcast', 'user', 'delivered', 'delivery_time', 'error_message')

