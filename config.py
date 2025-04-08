import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
print(f"Загруженный токен: {BOT_TOKEN}")  # Отладочный вывод

# ID администраторов (список)
ADMIN_IDS = [int(id_) for id_ in os.getenv('ADMIN_IDS', '').split(',') if id_]

# Настройки Crypto Pay
CRYPTO_PAY_TOKEN = os.getenv('CRYPTO_PAY_TOKEN')
CRYPTO_PAY_TESTNET = bool(int(os.getenv('CRYPTO_PAY_TESTNET', '1')))

# Цены на подписку (в USDT)
SUBSCRIPTION_PRICES = {
    1: 5,     # 1 месяц
    3: 13,    # 3 месяца
    6: 23,    # 6 месяцев
    12: 43,   # 12 месяцев
}

# Цены на подписку (в звездах)
STAR_PRICES = {
    1: 50,     # 1 месяц
    3: 140,    # 3 месяца
    6: 260,    # 6 месяцев
    12: 480,   # 12 месяцев
}

# Длительность пробного периода (в днях)
TRIAL_DURATION = 7

# Настройки базы данных
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///vpn_bot.db')

# Настройки VPN
TRIAL_PERIOD_DAYS = 7
VPN_CONFIG_PATH = 'vpn_configs'

# ID разработчика для отправки уведомлений
DEVELOPER_ID = int(os.getenv('DEVELOPER_ID', '0'))

# Настройки V2Ray
V2RAY_SERVER_HOST = os.getenv('V2RAY_SERVER_HOST', 'your.server.ip')
V2RAY_SERVER_PORT = int(os.getenv('V2RAY_SERVER_PORT', '443'))
V2RAY_SERVER_PASSWORD = os.getenv('V2RAY_SERVER_PASSWORD', 'your_password')
V2RAY_SERVER_UUID = os.getenv('V2RAY_SERVER_UUID', 'your_uuid')
V2RAY_SERVER_ALTER_ID = int(os.getenv('V2RAY_SERVER_ALTER_ID', '0'))
V2RAY_SERVER_NETWORK = os.getenv('V2RAY_SERVER_NETWORK', 'tcp')
V2RAY_SERVER_TYPE = os.getenv('V2RAY_SERVER_TYPE', 'none')
V2RAY_SERVER_TLS = os.getenv('V2RAY_SERVER_TLS', 'tls')
V2RAY_SERVER_PATH = os.getenv('V2RAY_SERVER_PATH', '')
V2RAY_SERVER_HOSTNAME = os.getenv('V2RAY_SERVER_HOSTNAME', '')

# Настройки поддержки
SUPPORT_CHAT_URL = os.getenv('SUPPORT_CHAT_URL', 'https://t.me/your_support_chat')

# Токен платежного провайдера для Telegram Payments
PAYMENT_PROVIDER_TOKEN = os.getenv('PAYMENT_PROVIDER_TOKEN') 