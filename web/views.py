from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import TelegramUser, Cryptocurrency, PriceData


def index(request):
    """Главная страница"""
    users_count = TelegramUser.objects.count()
    cryptocurrencies = Cryptocurrency.objects.all()

    # Получаем последние цены для каждой криптовалюты
    for crypto in cryptocurrencies:
        latest_price = PriceData.objects.filter(
            cryptocurrency=crypto
        ).order_by('-timestamp').first()

        if latest_price:
            crypto.current_price = latest_price.price
            crypto.price_timestamp = latest_price.timestamp

    context = {
        'users_count': users_count,
        'cryptocurrencies': cryptocurrencies,
    }
    return render(request, 'index.html', context)


@login_required
def dashboard(request):
    """Панель управления (только для авторизованных пользователей)"""
    users = TelegramUser.objects.all().order_by('-last_active')
    context = {
        'users': users,
    }
    return render(request, 'dashboard.html', context)