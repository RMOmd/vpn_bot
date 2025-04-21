# VPN Bot

Бот для продажи VPN подписок с оплатой звездами Telegram и через платежный шлюз TelegaPay.

## Функциональность

- Пробный период на 7 дней
- Оплата подписки звездами Telegram
- Оплата подписки через TelegaPay (карты, СБП)
- Выбор страны для VPN
- Управление серверами через админ-панель
- Статистика и финансы

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/vpn_bot.git
cd vpn_bot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` и заполните его:
```env
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789,987654321
V2RAY_SERVER_HOST=your.server.ip
V2RAY_SERVER_PORT=443
V2RAY_SERVER_PASSWORD=your_password
V2RAY_SERVER_UUID=your_uuid
V2RAY_SERVER_ALTER_ID=0
V2RAY_SERVER_NETWORK=tcp
V2RAY_SERVER_TYPE=none
V2RAY_SERVER_TLS=tls
V2RAY_SERVER_PATH=
V2RAY_SERVER_HOSTNAME=
SUPPORT_CHAT_URL=https://t.me/your_support_chat
TELEGAPAY_API_KEY=your_telegapay_api_key
TELEGAPAY_BASE_URL=https://secure.telegapay.link
TELEGAPAY_WEBHOOK_URL=https://your-webhook-url.com/telegapay/webhook
```

4. Инициализируйте базу данных:
```bash
python init_database.py
```

5. Запустите бота:
```bash
python main.py
```

## Платежная система

Бот поддерживает два способа оплаты:

1. **Оплата звездами Telegram** - пользователи могут оплачивать подписку звездами Telegram Premium.
2. **Оплата через TelegaPay** - пользователи могут оплачивать подписку через различные методы оплаты:
   - Банковские карты
   - Система быстрых платежей (СБП)
   - QR-коды

Для работы с TelegaPay вам необходимо:
1. Зарегистрироваться на сайте [TelegaPay](https://telegapay.link)
2. Получить API ключ
3. Настроить вебхук в личном кабинете TelegaPay, указав URL вашего сервера

## Админ-панель

Команда `/admin` открывает админ-панель с следующими функциями:

- Управление пользователями:
  - Просмотр статистики
  - Поиск пользователей
  - Фильтр по времени

- Управление странами:
  - Добавление стран
  - Удаление стран
  - Включение/выключение стран

- Управление серверами:
  - Добавление серверов
  - Удаление серверов
  - Включение/выключение серверов

- Финансы:
  - Статистика по дням/неделям/месяцам
  - Фильтр по времени

## Лицензия

MIT 