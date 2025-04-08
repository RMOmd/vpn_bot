import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    SUBSCRIPTION_PRICES,
    SUPPORT_CHAT_URL
)
from database import init_db, get_or_create_user, create_trial_subscription, Session, User, Subscription
from admin import register_admin_handlers
from v2ray import V2RayManager
from datetime import datetime, timedelta, UTC
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Регистрация хендлеров админки
register_admin_handlers(dp)

# Инициализация V2Ray менеджера
v2ray_manager = V2RayManager(
    server_host=os.getenv('V2RAY_SERVER_HOST'),
    server_port=int(os.getenv('V2RAY_SERVER_PORT', 443))
)

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
    for months, stars in SUBSCRIPTION_PRICES.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{months} месяц(ев) - {stars} ⭐️",
                callback_data=f"buy_{months}"
            )
        ])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    session = Session()
    try:
        user = get_or_create_user(message.from_user, session)
        welcome_text = (
            "👋 Добро пожаловать в VPN бот!\n\n"
            "Выберите нужный пункт меню:"
        )
        await message.answer(welcome_text, reply_markup=get_main_keyboard())
    finally:
        session.close()

@dp.callback_query()
async def process_callback(callback_query: types.CallbackQuery):
    """Обработчик callback-запросов"""
    if callback_query.data == "back_to_main":
        await callback_query.message.edit_text(
            "Выберите нужный пункт меню:",
            reply_markup=get_main_keyboard()
        )
    elif callback_query.data == "show_prices":
        await callback_query.message.edit_text(
            "Выберите период подписки:",
            reply_markup=get_subscription_keyboard()
        )
    elif callback_query.data.startswith("buy_"):
        months = int(callback_query.data.split("_")[1])
        stars = SUBSCRIPTION_PRICES[months]
        
        # Создаем счет для оплаты звездами
        prices = [LabeledPrice(label=f"VPN на {months} мес.", amount=stars)]
        
        await bot.send_invoice(
            callback_query.from_user.id,
            title=f"VPN подписка на {months} мес.",
            description=f"Подписка на VPN сервис на {months} месяц(ев)",
            payload=f"sub_{months}_{callback_query.from_user.id}",
            provider_token="",  # Не нужен для звезд
            currency="XTR",
            prices=prices,
            start_parameter=f"sub_{months}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        
        await callback_query.message.edit_text(
            f"Счет на оплату создан!\n\n"
            f"Период: {months} месяц(ев)\n"
            f"Стоимость: {stars} ⭐️\n\n"
            f"Для оплаты нажмите кнопку выше.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data="show_prices")
            ]])
        )
    elif callback_query.data == "get_trial":
        session = Session()
        try:
            # Получаем пользователя в текущей сессии
            user = session.query(User).filter_by(telegram_id=callback_query.from_user.id).first()
            if not user:
                # Если пользователя нет, создаем его
                user = get_or_create_user(callback_query.from_user, session)
            
            # Проверяем использование пробного периода
            if user.has_used_trial(session):
                await callback_query.message.answer(
                    "Вы уже использовали пробный период. Выберите тариф для покупки подписки:",
                    reply_markup=get_subscription_keyboard()
                )
            else:
                subscription = create_trial_subscription(user, session)
                if subscription:
                    await callback_query.message.answer(
                        "🎉 Поздравляем!\n\n"
                        "Вам предоставлен бесплатный пробный период на 7 дней.\n"
                        "Наслаждайтесь безопасным и быстрым VPN!"
                    )
                    
                    # Создаем и отправляем конфигурацию V2Ray
                    success, client_uuid = await v2ray_manager.create_and_send_config(callback_query.from_user.id, bot)
                    if not success:
                        await callback_query.message.answer(
                            "❌ Возникла ошибка при создании конфигурации.\n"
                            "Пожалуйста, обратитесь в техподдержку."
                        )
                else:
                    await callback_query.message.answer(
                        "Вы уже использовали пробный период. Выберите тариф для покупки подписки:",
                        reply_markup=get_subscription_keyboard()
                    )
        finally:
            session.close()

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    """Обработчик предварительной проверки платежа"""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    """Обработчик успешного платежа"""
    try:
        # Получаем информацию о подписке из payload
        _, months, user_id = message.successful_payment.invoice_payload.split("_")
        months = int(months)
        user_id = int(user_id)
        
        # Создаем подписку
        session = Session()
        try:
            # Получаем пользователя в текущей сессии
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                # Если пользователя нет, создаем его
                user = get_or_create_user(message.from_user, session)
                
            subscription = Subscription(
                user_id=user.telegram_id,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30*months),
                price=SUBSCRIPTION_PRICES[months],
                is_active=True,
                payment_type="stars"
            )
            session.add(subscription)
            session.commit()
            
            # Создаем и отправляем конфигурацию V2Ray
            success, client_uuid = await v2ray_manager.create_and_send_config(user_id, bot)
            if success:
                await message.answer(
                    f"✅ Оплата успешно получена!\n\n"
                    f"Ваша подписка активирована на {months} месяц(ев).\n"
                    f"Срок действия: до {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                    f"Конфигурация V2Ray отправлена отдельным сообщением."
                )
            else:
                await message.answer(
                    f"✅ Оплата успешно получена, но возникла ошибка при создании конфигурации.\n"
                    f"Пожалуйста, обратитесь в техподдержку."
                )
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Ошибка при обработке платежа: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке платежа. "
            "Пожалуйста, обратитесь в техподдержку.",
            reply_markup=get_main_keyboard()
        )

async def main():
    # Инициализация базы данных
    init_db()
    
    try:
        # Запуск бота в режиме long polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
