import os
import hashlib
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    SUBSCRIPTION_PRICES,
    CRYPTO_PAY_TOKEN,
    CRYPTO_PAY_TESTNET,
    SUPPORT_CHAT_URL
)
from database import init_db, get_or_create_user, create_trial_subscription, Session, User, Subscription
from admin import register_admin_handlers
from v2ray import V2RayManager
from datetime import datetime, timedelta, UTC
from crypto_pay import CryptoPay
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

# Инициализация Crypto Pay
print(f"CRYPTO_PAY_TOKEN: {CRYPTO_PAY_TOKEN}")  # Отладочный вывод
print(f"CRYPTO_PAY_TESTNET: {CRYPTO_PAY_TESTNET}")  # Отладочный вывод
crypto_pay = CryptoPay(CRYPTO_PAY_TOKEN, CRYPTO_PAY_TESTNET)

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
    for months, price in SUBSCRIPTION_PRICES.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{months} месяц(ев) - {price} USDT",
                callback_data=f"buy_{months}"
            )
        ])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    # Проверяем, есть ли параметр в команде start
    if len(message.text.split()) > 1:
        start_param = message.text.split()[1]
        if start_param.startswith("pay_"):
            # Обрабатываем платеж
            _, months, user_id = start_param.split("_")
            months = int(months)
            user_id = int(user_id)
            
            if message.from_user.id != user_id:
                await message.answer("Этот платеж предназначен для другого пользователя.")
                return
                
            # Создаем подписку
            session = Session()
            try:
                user = session.query(User).filter_by(telegram_id=user_id).first()
                if user:
                    subscription = Subscription(
                        user_id=user.telegram_id,
                        start_date=datetime.now(UTC),
                        end_date=datetime.now(UTC) + timedelta(days=30*months),
                        price=SUBSCRIPTION_PRICES[months],
                        is_active=True,
                        payment_type="crypto"
                    )
                    session.add(subscription)
                    session.commit()
                    
                    await message.answer(
                        f"✅ Оплата успешно получена!\n\n"
                        f"Ваша подписка активирована на {months} месяц(ев).\n"
                        f"Срок действия: до {subscription.end_date.strftime('%d.%m.%Y')}"
                    )
                else:
                    await message.answer("Ошибка: пользователь не найден")
            finally:
                session.close()
            return
    
    # Обычный старт бота
    user = get_or_create_user(message.from_user)
    welcome_text = (
        "👋 Добро пожаловать в VPN бот!\n\n"
        "Выберите нужный пункт меню:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

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
        price = SUBSCRIPTION_PRICES[months]
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        
        # Создаем счет в Crypto Pay
        invoice = await crypto_pay.create_invoice(
            amount=price,
            description=f"VPN подписка на {months} месяц(ев)",
            payload=f"vpn_sub_{months}_{callback_query.from_user.id}",
            paid_btn_name="start",
            paid_btn_url=f"https://t.me/{bot_info.username}?start=pay_{months}_{callback_query.from_user.id}"
        )
        
        if not invoice:
            await callback_query.message.answer(
                "Произошла ошибка при создании счета. Попробуйте позже."
            )
            return
            
        # Создаем клавиатуру с кнопкой оплаты
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💳 Оплатить",
                url=invoice["bot_invoice_url"]
            )],
            [InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="show_prices"
            )]
        ])
        
        await callback_query.message.edit_text(
            f"Счет на оплату создан!\n\n"
            f"Период: {months} месяц(ев)\n"
            f"Сумма: {price} USDT\n\n"
            f"Нажмите кнопку 'Оплатить' для перехода к оплате.\n"
            f"После оплаты нажмите кнопку 'Start' в боте.",
            reply_markup=keyboard
        )
    elif callback_query.data.startswith("check_payment_"):
        invoice_id = int(callback_query.data.split("_")[2])
        invoice = await crypto_pay.get_invoice(invoice_id)
        
        if not invoice:
            await callback_query.message.answer(
                "Произошла ошибка при проверке оплаты. Попробуйте позже."
            )
            return
            
        if invoice["status"] == "paid":
            # Получаем информацию о подписке из payload
            _, months, user_id = invoice["payload"].split("_")
            months = int(months)
            user_id = int(user_id)
            
            # Создаем подписку
            session = Session()
            try:
                user = session.query(User).filter_by(telegram_id=user_id).first()
                if user:
                    subscription = Subscription(
                        user_id=user.telegram_id,
                        start_date=datetime.now(UTC),
                        end_date=datetime.now(UTC) + timedelta(days=30*months),
                        price=SUBSCRIPTION_PRICES[months],
                        is_active=True,
                        payment_type="crypto"
                    )
                    session.add(subscription)
                    session.commit()
                    
                    await callback_query.message.edit_text(
                        f"✅ Оплата успешно получена!\n\n"
                        f"Ваша подписка активирована на {months} месяц(ев).\n"
                        f"Срок действия: до {subscription.end_date.strftime('%d.%m.%Y')}"
                    )
                else:
                    await callback_query.message.answer(
                        "Ошибка: пользователь не найден"
                    )
            finally:
                session.close()
        else:
            await callback_query.message.answer(
                "Оплата еще не получена. Попробуйте проверить позже."
            )
    elif callback_query.data == "get_trial":
        user = get_or_create_user(callback_query.from_user)
        if user.has_used_trial():
            await callback_query.message.answer(
                "Вы уже использовали пробный период. Выберите тариф для покупки подписки:",
                reply_markup=get_subscription_keyboard()
            )
        else:
            create_trial_subscription(user)
            await callback_query.message.answer(
                "🎉 Поздравляем!\n\n"
                "Вам предоставлен бесплатный пробный период на 7 дней.\n"
                "Наслаждайтесь безопасным и быстрым VPN!"
            )

async def main():
    # Инициализация базы данных
    init_db()
    
    try:
        # Запуск бота в режиме long polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await crypto_pay.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
