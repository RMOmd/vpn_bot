import os
import hashlib
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUBSCRIPTION_PRICES, ADMIN_IDS
from database import init_db, get_or_create_user, create_trial_subscription, Session, User, Subscription
from admin import register_admin_handlers
from v2ray import V2RayManager
from datetime import datetime, timedelta, UTC
from dotenv import load_dotenv
from payments import PaymentManager
from aiogram.exceptions import TelegramBadRequest

# Загрузка переменных окружения
load_dotenv()

# Временно добавляем токен напрямую для тестирования
BOT_TOKEN = "8186217723:AAGl4sBwC6qJN5y1E8hD1dtMbCUJRqlun2U"
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

# Регистрация хендлеров админки
register_admin_handlers(dp)

# Инициализация V2Ray менеджера
v2ray_manager = V2RayManager(
    server_host=os.getenv('V2RAY_SERVER_HOST'),
    server_port=int(os.getenv('V2RAY_SERVER_PORT', 443))
)

# Инициализация менеджера платежей
payment_manager = PaymentManager()

# Цены на подписки
SUBSCRIPTION_PRICES = {
    "1_month": 299,
    "3_months": 799,
    "6_months": 1499,
    "12_months": 2699
}

# URL чата поддержки
SUPPORT_CHAT_URL = os.getenv('SUPPORT_CHAT_URL', 'https://t.me/your_support_chat')

def generate_fingerprint(telegram_id: int, username: str) -> str:
    data = f"{telegram_id}{username}{os.urandom(16).hex()}"
    return hashlib.sha256(data.encode()).hexdigest()

def get_main_keyboard():
    """Создание основной клавиатуры"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить пробный период (7 дней)", callback_data="get_trial")],
        [InlineKeyboardButton(text="💎 Купить VPN", callback_data="show_prices")],
        [InlineKeyboardButton(text="🛟 Техническая поддержка", url=SUPPORT_CHAT_URL)]
    ])

def get_subscription_keyboard():
    """Создание клавиатуры с подписками"""
    keyboard = []
    
    # Добавляем только кнопку оплаты звездами
    keyboard.append([InlineKeyboardButton(text="⭐️ Оплата звездами ⭐️", callback_data="show_stars")])
    
    # Добавляем кнопку назад
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_stars_keyboard():
    """Создание клавиатуры с ценами в звездах"""
    keyboard = []
    
    # Получаем цены в звездах
    star_prices = payment_manager.star_prices
    
    # Добавляем кнопки для оплаты звездами
    keyboard.extend([
        [InlineKeyboardButton(
            text=f"⭐️ 1 месяц - {star_prices[1]} звезд", 
            callback_data="buy_stars_1"
        )],
        [InlineKeyboardButton(
            text=f"⭐️ 3 месяца - {star_prices[3]} звезд", 
            callback_data="buy_stars_3"
        )],
        [InlineKeyboardButton(
            text=f"⭐️ 6 месяцев - {star_prices[6]} звезд", 
            callback_data="buy_stars_6"
        )],
        [InlineKeyboardButton(
            text=f"⭐️ 12 месяцев - {star_prices[12]} звезд", 
            callback_data="buy_stars_12"
        )]
    ])
    
    # Добавляем только кнопку назад
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    session = Session()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    
    # Добавляем логирование
    print(f"Данные пользователя из Telegram:")
    print(f"ID: {message.from_user.id}")
    print(f"Username: {message.from_user.username}")
    print(f"First Name: {message.from_user.first_name}")
    print(f"Last Name: {message.from_user.last_name}")
    
    if not user:
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            created_at=datetime.now(UTC)
        )
        session.add(user)
        session.commit()
        
        # Проверяем созданного пользователя
        print("\nСозданный пользователь в базе:")
        print(f"ID: {user.telegram_id}")
        print(f"Username: {user.username}")
        print(f"First Name: {user.first_name}")
        print(f"Last Name: {user.last_name}")
    else:
        # Обновляем данные существующего пользователя
        user.username = message.from_user.username
        user.first_name = message.from_user.first_name
        user.last_name = message.from_user.last_name
        session.commit()
        
        print("\nОбновлен существующий пользователь:")
        print(f"ID: {user.telegram_id}")
        print(f"Username: {user.username}")
        print(f"First Name: {user.first_name}")
        print(f"Last Name: {user.last_name}")
    
    welcome_text = (
        "👋 Добро пожаловать в наш VPN сервис!\n\n"
        "🚀 Наши преимущества:\n"
        "• Высокая скорость соединения\n"
        "• Защищенный протокол V2Ray\n"
        "• Серверы в разных странах\n"
        "• Работает на всех устройствах\n"
        "• Обход блокировок\n"
        "• Техническая поддержка 24/7\n\n"
        "🎁 Попробуйте бесплатно в течение 7 дней!"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())
    session.close()

@dp.callback_query()
async def process_callback(callback_query: types.CallbackQuery):
    if callback_query.data == "back_to_main":
        welcome_text = (
            "🔙 Главное меню\n\n"
            "Выберите нужный пункт меню:"
        )
        await callback_query.message.edit_text(welcome_text, reply_markup=get_main_keyboard())
        
    elif callback_query.data == "show_prices":
        prices_text = (
            "💎 Выберите способ оплаты и период подписки:\n\n"
            "⭐️ Оплата звездами Telegram Premium\n\n"
            "✨ Чем дольше период - тем выгоднее!\n"
            "🔒 Гарантия возврата средств в течение 24 часов\n\n"
            "💳 Оплата картой временно недоступна"
        )
        await callback_query.message.edit_text(prices_text, reply_markup=get_subscription_keyboard())
        
    elif callback_query.data == "show_stars":
        stars_text = (
            "⭐️ Оплата звездами Telegram Premium\n\n"
            "Используйте звезды Telegram Premium для оплаты подписки!\n"
            "✨ Чем дольше период - тем выгоднее!\n\n"
            "❓ Как получить звезды:\n"
            "1. Подключите Telegram Premium\n"
            "2. Получайте звезды за активность\n"
            "3. Используйте их для оплаты"
        )
        await callback_query.message.edit_text(stars_text, reply_markup=get_stars_keyboard())
        
    elif callback_query.data == "get_trial":
        session = Session()
        user = session.query(User).filter_by(telegram_id=callback_query.from_user.id).first()
        
        # Проверяем активную подписку
        active_sub = user.get_active_subscription()
        if active_sub:
            days_left = user.get_days_left()
            await callback_query.message.edit_text(
                f"У вас уже есть активная подписка!\n\n"
                f"Тип подписки: {'Пробная' if active_sub.is_trial else 'Платная'}\n"
                f"Осталось дней: {days_left}\n\n"
                f"Хотите продлить подписку?",
                reply_markup=get_subscription_keyboard()
            )
            session.close()
            return
        
        # Проверяем возможность использования пробного периода
        if not user.can_use_trial():
            await callback_query.message.edit_text(
                "❌ Вы уже использовали пробный период.\n\n"
                "💎 Приобретите подписку для продолжения использования VPN:",
                reply_markup=get_subscription_keyboard()
            )
            session.close()
            return
        
        # Создаем пробную подписку
        subscription = Subscription(
            user_id=user.telegram_id,
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC) + timedelta(days=7),
            price=0,
            is_trial=True,
            is_active=True,
            payment_type="trial"
        )
        session.add(subscription)
        
        # Отмечаем, что пробный период использован
        user.trial_used = True
        user.is_active = True
        session.commit()
        
        await callback_query.message.edit_text("⏳ Генерируем конфигурацию VPN...")
        
        # Создаем и отправляем конфигурацию
        success, client_uuid = await v2ray_manager.create_and_send_config(user.telegram_id, bot)
        
        if success:
            await callback_query.message.edit_text(
                "✅ Пробный период активирован!\n\n"
                "📱 Как подключиться:\n"
                "1. Установите приложение V2Ray\n"
                "2. Импортируйте конфигурацию одним из способов:\n"
                "   • Отсканируйте QR-код\n"
                "   • Нажмите на ссылку vmess://\n"
                "   • Импортируйте файл конфигурации\n"
                "3. Включите VPN\n\n"
                "⏰ Пробный период действует 7 дней\n"
                "❓ Если нужна помощь - обратитесь в поддержку",
                reply_markup=get_main_keyboard()
            )
        else:
            await callback_query.message.edit_text(
                "❌ Произошла ошибка при создании конфигурации.\n"
                "Пожалуйста, обратитесь в поддержку.",
                reply_markup=get_main_keyboard()
            )
        
        session.close()
        
    elif callback_query.data.startswith("buy_"):
        _, payment_type, duration = callback_query.data.split("_")
        months = int(duration)
        
        if payment_type == "money":
            # Получаем цену из словаря цен
            duration_key = f"{duration}_months" if months != 1 else "1_month"
            price = SUBSCRIPTION_PRICES.get(duration_key)
            
            if not price:
                await callback_query.answer(
                    "❌ Ошибка при получении цены. Пожалуйста, попробуйте позже.",
                    show_alert=True
                )
                return
            
            try:
                # Создаем платеж через Telegram Payments
                invoice_data = await payment_manager.create_payment(
                    user_id=callback_query.from_user.id,
                    amount=price,
                    duration_months=months
                )
                
                await bot.send_invoice(
                    chat_id=callback_query.from_user.id,
                    **invoice_data
                )
                
                # Отправляем сообщение с инструкцией
                await callback_query.message.edit_text(
                    "💳 Для оплаты подписки:\n\n"
                    "1. Нажмите на сообщение с оплатой выше\n"
                    "2. Выберите способ оплаты\n"
                    "3. Подтвердите оплату\n\n"
                    "После успешной оплаты вы автоматически получите доступ к VPN!\n\n"
                    "❓ Если возникли проблемы - обратитесь в поддержку",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="◀️ Назад к тарифам", callback_data="show_prices")],
                        [InlineKeyboardButton(text="🛟 Техническая поддержка", url=SUPPORT_CHAT_URL)]
                    ])
                )
            except ValueError as e:
                await callback_query.message.edit_text(
                    "❌ Оплата временно недоступна.\n"
                    "Пожалуйста, выберите оплату звездами или обратитесь в поддержку.",
                    reply_markup=get_subscription_keyboard()
                )
        
        elif payment_type == "stars":
            # Создаем платеж звездами
            payment_data = await payment_manager.create_star_payment(
                user_id=callback_query.from_user.id,
                duration_months=months
            )
            
            if not payment_data:
                await callback_query.answer(
                    "❌ Ошибка при создании платежа. Попробуйте позже.",
                    show_alert=True
                )
                return
            
            # Формируем текст в зависимости от периода
            if months == 1:
                title = "VPN на 1 месяц"
                description = f"Доступ к VPN на 1 месяц\nСтоимость: {payment_data['stars']} ⭐️"
            elif months == 3:
                title = "VPN на 3 месяца"
                description = f"Доступ к VPN на 3 месяца\nСтоимость: {payment_data['stars']} ⭐️\nВыгода 30%"
            elif months == 6:
                title = "VPN на 6 месяцев"
                description = f"Доступ к VPN на 6 месяцев\nСтоимость: {payment_data['stars']} ⭐️\nВыгода 45%"
            else:  # 12 месяцев
                title = "VPN на 12 месяцев"
                description = f"Доступ к VPN на 12 месяцев\nСтоимость: {payment_data['stars']} ⭐️\nВыгода 60%"
            
            # Создаем клавиатуру с кнопкой оплаты
            payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="💫 Перейти к оплате", 
                    url=f"tg://premium/gift?quantity={payment_data['stars']}"
                )],
                [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_stars_{payment_data['payment_id']}")],
                [InlineKeyboardButton(text="◀️ Назад к тарифам", callback_data="show_stars")]
            ])
            
            # Отправляем сообщение с инструкцией
            await callback_query.message.edit_text(
                f"{description}\n\n"
                "💫 Для оплаты подписки:\n"
                "1. Нажмите кнопку «Перейти к оплате»\n"
                "2. Подтвердите передачу звезд\n"
                "3. После оплаты нажмите «Я оплатил»\n\n"
                "❓ Если возникли проблемы - обратитесь в поддержку",
                reply_markup=payment_keyboard
            )
        else:
            await callback_query.message.edit_text(
                "❌ Этот способ оплаты временно недоступен.\n"
                "Пожалуйста, выберите оплату звездами или обратитесь в поддержку.",
                reply_markup=get_subscription_keyboard()
            )
    
    elif callback_query.data.startswith("check_stars_"):
        try:
            print("\n=== Начало проверки оплаты звездами ===")
            payment_id = callback_query.data.replace("check_stars_", "")
            
            # Подтверждаем оплату
            success = await payment_manager.confirm_star_payment(payment_id, callback_query.from_user)
            
            if success:
                await callback_query.message.edit_text("⏳ Генерируем конфигурацию VPN...")
                
                # Создаем конфигурацию VPN
                success, client_uuid = await v2ray_manager.create_and_send_config(callback_query.from_user.id, bot)
                
                if success:
                    await callback_query.message.edit_text(
                        "✅ Подписка успешно активирована!\n\n"
                        "📱 Как подключиться:\n"
                        "1. Установите приложение V2Ray\n"
                        "2. Импортируйте конфигурацию одним из способов:\n"
                        "   • Отсканируйте QR-код\n"
                        "   • Нажмите на ссылку vmess://\n"
                        "   • Импортируйте файл конфигурации\n"
                        "3. Включите VPN\n\n"
                        "❓ Если нужна помощь - обратитесь в поддержку",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await callback_query.message.edit_text(
                        "❌ Произошла ошибка при создании конфигурации.\n"
                        "Пожалуйста, обратитесь в поддержку.",
                        reply_markup=get_main_keyboard()
                    )
            else:
                await callback_query.answer(
                    "❌ Оплата не найдена или уже была использована.",
                    show_alert=True
                )
        except Exception as e:
            print(f"Ошибка при проверке оплаты: {e}")
            await callback_query.answer(
                "❌ Произошла ошибка. Пожалуйста, попробуйте снова.",
                show_alert=True
            )
        finally:
            print("=== Завершение проверки оплаты звездами ===\n")

    elif callback_query.data.startswith("buy_stars_"):
        try:
            print(f"\n=== Начало обработки платежа звездами ===")
            print(f"callback_data: {callback_query.data}")
            
            _, _, duration = callback_query.data.split("_")
            months = int(duration)
            stars_amount = payment_manager.get_star_price(months)
            
            print(f"Месяцев: {months}")
            print(f"Количество звезд: {stars_amount}")
            
            # Формируем текст в зависимости от периода
            if months == 1:
                title = "VPN на 1 месяц"
                description = f"Доступ к VPN на 1 месяц\nСтоимость: {stars_amount} ⭐️"
            elif months == 3:
                title = "VPN на 3 месяца"
                description = f"Доступ к VPN на 3 месяца\nСтоимость: {stars_amount} ⭐️\nВыгода 30%"
            elif months == 6:
                title = "VPN на 6 месяцев"
                description = f"Доступ к VPN на 6 месяцев\nСтоимость: {stars_amount} ⭐️\nВыгода 45%"
            else:  # 12 месяцев
                title = "VPN на 12 месяцев"
                description = f"Доступ к VPN на 12 месяцев\nСтоимость: {stars_amount} ⭐️\nВыгода 60%"
            
            try:
                print("\nОтправка инвойса...")
                # Создаем инвойс для оплаты звездами
                await bot.send_invoice(
                    chat_id=callback_query.from_user.id,
                    title=title,
                    description=description,
                    payload=f"stars_{callback_query.from_user.id}_{months}",
                    provider_token="284685063:TEST:ZGVtbzpkZW1v",
                    currency="STARS",
                    prices=[
                        types.LabeledPrice(
                            label=title,
                            amount=stars_amount * 100  # Умножаем на 100, так как сумма в копейках
                        )
                    ],
                    start_parameter=f"stars_{months}",
                    need_name=False,
                    need_phone_number=False,
                    need_email=False,
                    need_shipping_address=False,
                    is_flexible=False
                )
                print("Инвойс успешно отправлен")
                
                # Отправляем инструкцию по оплате
                await callback_query.message.edit_text(
                    "💫 Для оплаты подписки:\n\n"
                    "1. Нажмите на сообщение с оплатой выше\n"
                    "2. Подтвердите передачу звезд\n"
                    "3. После успешной оплаты вы получите доступ к VPN\n\n"
                    "❓ Если возникли проблемы - обратитесь в поддержку",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="◀️ Назад к тарифам", callback_data="show_stars")],
                        [InlineKeyboardButton(text="🛟 Техническая поддержка", url=SUPPORT_CHAT_URL)]
                    ])
                )
            except Exception as e:
                print(f"Ошибка при создании инвойса: {e}")
                error_message = str(e)
                if "USER_HAS_NO_PREMIUM" in error_message:
                    await callback_query.answer(
                        "❌ Для оплаты звездами нужен Telegram Premium",
                        show_alert=True
                    )
                elif "NOT_ENOUGH_STARS" in error_message:
                    await callback_query.answer(
                        "❌ У вас недостаточно звезд для оплаты",
                        show_alert=True
                    )
                else:
                    await callback_query.answer(
                        "❌ Ошибка при создании платежа. Попробуйте позже или обратитесь в поддержку.",
                        show_alert=True
                    )
            
        except Exception as e:
            print(f"Ошибка при обработке платежа: {e}")
            await callback_query.answer(
                "❌ Произошла ошибка. Пожалуйста, попробуйте снова.",
                show_alert=True
            )
        finally:
            print("=== Завершение обработки платежа звездами ===\n")

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    """Обработка пре-чекаута"""
    try:
        print("\n=== Начало обработки pre_checkout_query ===")
        print(f"ID запроса: {pre_checkout_query.id}")
        print(f"От пользователя: {pre_checkout_query.from_user.id}")
        print(f"Payload: {pre_checkout_query.invoice_payload}")
        print(f"Валюта: {pre_checkout_query.currency}")
        print(f"Сумма: {pre_checkout_query.total_amount}")
        
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
        print("pre_checkout_query успешно подтвержден")
    except Exception as e:
        print(f"Ошибка при обработке pre_checkout_query: {e}")
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Произошла ошибка при обработке платежа. Попробуйте позже."
        )
    finally:
        print("=== Завершение обработки pre_checkout_query ===\n")

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message) -> None:
    """Обработка успешного платежа"""
    try:
        print("\n=== Начало обработки успешного платежа ===")
        # Получаем информацию о платеже
        payment_info = message.successful_payment
        payload = payment_info.invoice_payload
        
        print(f"Платеж от пользователя: {message.from_user.id}")
        print(f"Payload: {payload}")
        print(f"Валюта: {payment_info.currency}")
        print(f"Сумма: {payment_info.total_amount}")
        print(f"ID транзакции: {payment_info.telegram_payment_charge_id}")
        
        if payload.startswith("stars_"):
            print("\nОбработка оплаты звездами...")
            # Обработка оплаты звездами
            _, user_id, duration = payload.split("_")
            months = int(duration)
            
            print(f"ID пользователя: {user_id}")
            print(f"Длительность подписки: {months} мес.")
            
            # Создаем подписку
            session = Session()
            user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
            
            if user:
                print("\nСоздание подписки...")
                # Деактивируем текущую подписку, если есть
                current_sub = user.get_active_subscription()
                if current_sub:
                    print(f"Деактивация текущей подписки ID: {current_sub.id}")
                    current_sub.is_active = False
                
                # Создаем новую подписку
                subscription = Subscription(
                    user_id=user.telegram_id,
                    start_date=datetime.now(UTC),
                    end_date=datetime.now(UTC) + timedelta(days=30 * months),
                    price=0,  # Цена 0, так как оплата звездами
                    is_trial=False,
                    is_active=True,
                    payment_type="stars",
                    stars_paid=payment_info.total_amount
                )
                session.add(subscription)
                user.is_active = True
                session.commit()
                print("Подписка успешно создана")
                
                print("\nСоздание конфигурации VPN...")
                # Создаем конфигурацию VPN
                success, client_uuid = await v2ray_manager.create_and_send_config(message.from_user.id, bot)
                
                if success:
                    print("Конфигурация успешно создана и отправлена")
                    await message.answer(
                        "✅ Подписка успешно активирована!\n\n"
                        "📱 Как подключиться:\n"
                        "1. Установите приложение V2Ray\n"
                        "2. Импортируйте конфигурацию одним из способов:\n"
                        "   • Отсканируйте QR-код\n"
                        "   • Нажмите на ссылку vmess://\n"
                        "   • Импортируйте файл конфигурации\n"
                        "3. Включите VPN\n\n"
                        "❓ Если нужна помощь - обратитесь в поддержку",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    print("Ошибка при создании конфигурации")
                    await message.answer(
                        "❌ Произошла ошибка при создании конфигурации.\n"
                        "Пожалуйста, обратитесь в поддержку.",
                        reply_markup=get_main_keyboard()
                    )
            
            session.close()
    except Exception as e:
        print(f"Ошибка при обработке успешного платежа: {e}")
        await message.answer(
            "❌ Произошла ошибка при активации подписки.\n"
            "Пожалуйста, обратитесь в поддержку.",
            reply_markup=get_main_keyboard()
        )
    finally:
        print("=== Завершение обработки успешного платежа ===\n")

@dp.message()
async def process_message(message: types.Message):
    """Обработка сообщений"""
    pass  # Здесь можно добавить другую логику обработки сообщений

def get_payment_keyboard():
    """Создание клавиатуры для оплаты"""
    keyboard = []
    
    # Добавляем кнопки для оплаты звездами
    keyboard.extend([
        [InlineKeyboardButton(text="⭐️ 50 звезд - 1 месяц", callback_data="buy_stars_1")],
        [InlineKeyboardButton(text="⭐️ 140 звезд - 3 месяца", callback_data="buy_stars_3")],
        [InlineKeyboardButton(text="⭐️ 260 звезд - 6 месяцев", callback_data="buy_stars_6")],
        [InlineKeyboardButton(text="⭐️ 480 звезд - 12 месяцев", callback_data="buy_stars_12")]
    ])
    
    # Добавляем кнопку назад
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 