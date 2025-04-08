# VPN Bot

Бот для продажи VPN подписок с оплатой звездами Telegram.

## Функциональность

- Пробный период на 7 дней
- Оплата подписки звездами Telegram
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
```

4. Инициализируйте базу данных:
```bash
python init_database.py
```

5. Запустите бота:
```bash
python main.py
```

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