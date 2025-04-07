import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
print(f"Загруженный токен: {BOT_TOKEN}")  # Отладочный вывод

# Токен платежного провайдера
PAYMENT_PROVIDER_TOKEN = os.getenv('PROVIDER_TOKEN')
if not PAYMENT_PROVIDER_TOKEN:
    print("⚠️ Не задан токен платежного провайдера!")

# Настройки базы данных
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///vpn_bot.db')

# Настройки VPN
TRIAL_PERIOD_DAYS = 7
VPN_CONFIG_PATH = 'vpn_configs'

# Цены подписок (в рублях)
SUBSCRIPTION_PRICES = {
    '1_month': 299,
    '3_months': 799,
    '6_months': 1499,
    '12_months': 2699
}

# ID разработчика для отправки уведомлений
DEVELOPER_ID = int(os.getenv('DEVELOPER_ID', '0'))

# Настройки V2Ray
V2RAY_SERVER_HOST = os.getenv('V2RAY_SERVER_HOST', 'your.server.ip')
V2RAY_SERVER_PORT = int(os.getenv('V2RAY_SERVER_PORT', '443'))

# Настройки поддержки
SUPPORT_CHAT_URL = os.getenv('SUPPORT_CHAT_URL', 'https://t.me/your_support_chat')

# ID администраторов (список)
ADMIN_IDS = [40916643]  # Ваш ID жестко прописан для надежности 