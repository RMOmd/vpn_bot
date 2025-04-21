import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    STAR_PRICES,
    SUPPORT_CHAT_URL,
    TELEGAPAY_API_KEY
)
from database import init_db, get_or_create_user, create_trial_subscription, Session, User, Subscription, Country, VPNServer
from admin import register_admin_handlers
from v2ray import V2RayManager
from datetime import datetime, timedelta
from pytz import UTC
from utils import is_admin
import logging
from payments import PaymentManager
from fastapi import Request, FastAPI
import uvicorn
from aiogram.exceptions import TelegramBadRequest
from telegapay import telegapay_api
from states import AdminStates

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем, запускаемся в тестовом режиме или нет
TEST_MODE = BOT_TOKEN == "your_bot_token"
if TEST_MODE:
    logger.info("Запуск в тестовом режиме без реального токена Telegram")
    bot = None
    dp = None
else:
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация обработчиков
    register_admin_handlers(dp, bot)

# Инициализация менеджера V2Ray
v2ray_manager = V2RayManager()

# Создаем экземпляр менеджера платежей
payment_manager = PaymentManager()

# Инициализация FastAPI
app = FastAPI()

def get_main_keyboard():
    """Создание основной клавиатуры"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить пробный период (7 дней)", callback_data="get_trial")],
        [InlineKeyboardButton(text="💎 Купить VPN", callback_data="select_country")],
        [InlineKeyboardButton(text="🛟 Техническая поддержка", url=SUPPORT_CHAT_URL)]
    ])

def get_back_keyboard():
    """Создание клавиатуры с кнопкой назад"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад в главное меню", callback_data="back_to_main")
    ]])

def get_countries_keyboard():
    """Создание клавиатуры со списком стран"""
    session = Session()
    try:
        countries = session.query(Country).filter_by(is_active=True).all()
        keyboard = []
        for country in countries:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{country.flag} {country.name}",
                    callback_data=f"country_{country.id}"
                )
            ])
        keyboard.append([InlineKeyboardButton(text="◀️ Назад в главное меню", callback_data="back_to_main")])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    finally:
        session.close()

def get_duration_keyboard(country_id: int):
    """Создание клавиатуры с выбором длительности подписки"""
    keyboard = []
    for months, stars in STAR_PRICES.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{months} месяц(ев) - {stars} ⭐️",
                callback_data=f"duration_{country_id}_{months}"
            )
        ])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад к выбору страны", callback_data="select_country")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_payment_methods_keyboard(country_id: int, months: int):
    """Создание клавиатуры с методами оплаты TelegaPay"""
    keyboard = [
        [InlineKeyboardButton(text="💳 Банковская карта", callback_data=f"tpay_method_{country_id}_{months}_BANK_SBER")],
        [InlineKeyboardButton(text="📱 Система быстрых платежей (СБП)", callback_data=f"tpay_method_{country_id}_{months}_SBP")],
        [InlineKeyboardButton(text="📲 QR-код для оплаты", callback_data=f"tpay_method_{country_id}_{months}_QR_CODE")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"pay_telegapay_{country_id}_{months}")]
    ]
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
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик callback-запросов"""
    try:
        # Отвечаем на callback
        await callback_query.answer()
        
        if callback_query.data == "start":
            await show_main_menu(callback_query.message)
            
        if callback_query.data == "back_to_main":
            await callback_query.message.delete()
            await callback_query.message.answer(
                "Выберите нужный пункт меню:",
                reply_markup=get_main_keyboard()
            )
        elif callback_query.data == "admin_servers":
            # Обработчик для кнопки управления серверами
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить сервер", callback_data="add_server")],
                [InlineKeyboardButton(text="📋 Список серверов", callback_data="list_servers")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
            ])
            
            await callback_query.message.edit_text(
                "Управление VPN серверами\n\n"
                "Выберите действие:",
                reply_markup=keyboard
            )
        elif callback_query.data == "add_server":
            # Обработчик для добавления сервера
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_servers")]
            ])
            
            await callback_query.message.edit_text(
                "Добавление нового VPN сервера\n\n"
                "Введите название сервера:",
                reply_markup=keyboard
            )
            await state.set_state(AdminStates.waiting_for_server_name)
        elif callback_query.data == "cancel_server":
            # Обработчик для отмены добавления сервера
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить сервер", callback_data="add_server")],
                [InlineKeyboardButton(text="📋 Список серверов", callback_data="list_servers")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
            ])
            
            await callback_query.message.edit_text(
                "Управление VPN серверами\n\n"
                "Действие отменено. Выберите другое действие:",
                reply_markup=keyboard
            )
        elif callback_query.data == "select_country":
            await callback_query.message.delete()
            await callback_query.message.answer(
                "Выберите страну для VPN:",
                reply_markup=get_countries_keyboard()
            )
        elif callback_query.data.startswith("country_"):
            country_id = int(callback_query.data.split("_")[1])
            await callback_query.message.delete()
            await callback_query.message.answer(
                "Выберите период подписки:",
                reply_markup=get_duration_keyboard(country_id)
            )
        elif callback_query.data.startswith("duration_"):
            _, country_id, months = callback_query.data.split("_")
            country_id = int(country_id)
            months = int(months)
            
            # Создаем клавиатуру для выбора метода оплаты
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить звездами Telegram", callback_data=f"pay_stars_{country_id}_{months}")],
                [InlineKeyboardButton(text="Оплатить картой или СБП", callback_data=f"pay_telegapay_{country_id}_{months}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"country_{country_id}")]
            ])
            
            await callback_query.message.edit_text(
                f"Выберите способ оплаты для подписки на {months} месяц(ев):\n\n"
                f"Стоимость в звездах: {payment_manager.get_star_price(months)} ⭐️\n"
                f"Стоимость в рублях: {payment_manager.get_rub_price(months)} ₽",
                reply_markup=keyboard
            )
        
        elif callback_query.data.startswith("pay_stars_"):
            _, country_id, months = callback_query.data.split("_")[1:]
            country_id = int(country_id)
            months = int(months)
            stars = payment_manager.get_star_price(months)
            
            # Создаем счет для оплаты звездами
            prices = [LabeledPrice(label=f"VPN на {months} мес.", amount=stars)]
            
            await callback_query.message.delete()
            
            # Отправляем инвойс
            await bot.send_invoice(
                callback_query.from_user.id,
                title=f"VPN подписка на {months} мес.",
                description=f"Подписка на VPN сервис на {months} месяц(ев)",
                payload=f"sub_{country_id}_{months}_{callback_query.from_user.id}",
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
            
            # Отправляем сообщение с кнопкой назад
            await callback_query.message.answer(
                f"Счет на оплату создан!\n\n"
                f"Период: {months} месяц(ев)\n"
                f"Стоимость: {stars} ⭐️\n\n"
                f"Для оплаты нажмите кнопку выше.",
                reply_markup=get_back_keyboard()
            )
        
        elif callback_query.data.startswith("pay_telegapay_"):
            _, country_id, months = callback_query.data.split("_")[1:]
            country_id = int(country_id)
            months = int(months)
            amount = payment_manager.get_rub_price(months)
            
            # Показываем выбор методов оплаты
            keyboard = get_payment_methods_keyboard(country_id, months)
            
            await callback_query.message.edit_text(
                f"💳 Выберите способ оплаты:\n\n"
                f"Период: {months} месяц(ев)\n"
                f"Стоимость: {amount} ₽\n\n",
                reply_markup=keyboard
            )
        
        elif callback_query.data.startswith("tpay_method_"):
            parts = callback_query.data.split("_")
            country_id = int(parts[2])
            months = int(parts[3])
            payment_method = "_".join(parts[4:])  # В случае если метод содержит нижнее подчеркивание
            amount = payment_manager.get_rub_price(months)
            
            # Создаем платеж через TelegaPay с указанным методом
            payment_url = await payment_manager.create_telegapay_payment(
                user_id=callback_query.from_user.id,
                duration_months=months,
                payment_method=payment_method
            )
            
            if not payment_url:
                await callback_query.message.edit_text(
                    "❌ Произошла ошибка при создании платежа. Пожалуйста, попробуйте позже или обратитесь в техподдержку.",
                    reply_markup=get_back_keyboard()
                )
                return
            
            # Создаем клавиатуру с кнопкой для оплаты
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
                [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data=f"check_payment_{country_id}_{months}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"pay_telegapay_{country_id}_{months}")]
            ])
            
            method_names = {
                "BANK_SBER": "Банковская карта Сбербанк",
                "BANK_TINKOFF": "Банковская карта Тинькофф",
                "SBP": "Система быстрых платежей (СБП)",
                "QR_CODE": "QR-код для оплаты",
                "STATIC_QR_CODE": "Статический QR-код"
            }
            
            method_name = method_names.get(payment_method, payment_method)
            
            await callback_query.message.edit_text(
                f"💳 Оплата через {method_name}\n\n"
                f"Период: {months} месяц(ев)\n"
                f"Стоимость: {amount} ₽\n\n"
                f"Для оплаты нажмите кнопку ниже и следуйте инструкциям на странице оплаты.\n"
                f"После оплаты нажмите кнопку 'Я оплатил(а)'.",
                reply_markup=keyboard
            )
        
        elif callback_query.data.startswith("check_payment_"):
            _, country_id, months = callback_query.data.split("_")[1:]
            country_id = int(country_id)
            months = int(months)
            
            # Найдем последний платеж пользователя
            found_payment_id = None
            for payment_id, payment_info in payment_manager.payments.items():
                if (payment_info.get("user_id") == callback_query.from_user.id and 
                    payment_info.get("type") == "telegapay" and 
                    payment_info.get("status") == "pending" and
                    payment_info.get("duration") == int(months)):
                    found_payment_id = payment_id
                    break
            
            if not found_payment_id:
                await callback_query.message.edit_text(
                    "❌ Платеж не найден. Возможно, вы еще не создали платеж или создали его слишком давно.",
                    reply_markup=get_back_keyboard()
                )
                return
            
            # Проверяем статус платежа
            payment_status = await payment_manager.check_telegapay_status(found_payment_id)
            
            if payment_status:
                # Платеж успешен, создаем подписку
                session = Session()
                try:
                    user = session.query(User).filter_by(telegram_id=callback_query.from_user.id).first()
                    if not user:
                        user = get_or_create_user(callback_query.from_user, session)
                    
                    # Выбираем активный сервер для выбранной страны
                    server = session.query(VPNServer).filter_by(
                        country_id=int(country_id),
                        is_active=True
                    ).first()
                    
                    if not server:
                        await callback_query.message.edit_text(
                            "❌ Нет доступных серверов для выбранной страны. Пожалуйста, обратитесь в техподдержку.",
                            reply_markup=get_back_keyboard()
                        )
                        return
                    
                    # Деактивируем текущую подписку, если есть
                    current_sub = user.get_active_subscription()
                    if current_sub:
                        current_sub.is_active = False
                    
                    # Создаем новую подписку
                    subscription = Subscription(
                        user_id=user.telegram_id,
                        country_id=int(country_id),
                        server_id=server.id,
                        start_date=datetime.now(UTC),
                        end_date=datetime.now(UTC) + timedelta(days=30*int(months)),
                        price=payment_manager.get_rub_price(int(months)),
                        is_active=True,
                        payment_type="telegapay"
                    )
                    session.add(subscription)
                    user.is_active = True
                    session.commit()
                    
                    # Создаем и отправляем конфигурацию
                    success, client_uuid = await v2ray_manager.create_and_send_config(callback_query.from_user.id, bot)
                    
                    if success:
                        await callback_query.message.edit_text(
                            f"✅ Оплата успешно получена!\n\n"
                            f"Ваша подписка активирована на {months} месяц(ев).\n"
                            f"Срок действия: до {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                            f"Конфигурация V2Ray отправлена отдельным сообщением.",
                            reply_markup=get_back_keyboard()
                        )
                    else:
                        await callback_query.message.edit_text(
                            f"✅ Оплата успешно получена, но возникла ошибка при создании конфигурации.\n"
                            f"Пожалуйста, обратитесь в техподдержку.",
                            reply_markup=get_back_keyboard()
                        )
                finally:
                    session.close()
            else:
                # Платеж не найден или не оплачен
                await callback_query.message.edit_text(
                    "❌ Платеж еще не оплачен или находится в обработке. Пожалуйста, подождите несколько минут и попробуйте снова.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Проверить еще раз", callback_data=callback_query.data)],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"duration_{country_id}_{months}")]
                    ])
                )
        elif callback_query.data == "get_trial":
            session = Session()
            try:
                user = session.query(User).filter_by(telegram_id=callback_query.from_user.id).first()
                if not user:
                    user = get_or_create_user(callback_query.from_user, session)
                
                await callback_query.message.delete()
                
                if user.has_used_trial(session):
                    await callback_query.message.answer(
                        "Вы уже использовали пробный период. Выберите тариф для покупки подписки:",
                        reply_markup=get_countries_keyboard()
                    )
                else:
                    subscription = await create_trial_subscription(user, session)
                    if subscription:
                        success_message = await callback_query.message.answer(
                            "🎉 Поздравляем!\n\n"
                            "Вам предоставлен бесплатный пробный период на 7 дней.\n"
                            "Наслаждайтесь безопасным и быстрым VPN!",
                            reply_markup=get_back_keyboard()
                        )
                        
                        success, client_uuid = await v2ray_manager.create_and_send_config(callback_query.from_user.id, bot)
                        if not success:
                            await callback_query.message.answer(
                                "❌ Возникла ошибка при создании конфигурации.\n"
                                "Пожалуйста, обратитесь в техподдержку.",
                                reply_markup=get_back_keyboard()
                            )
                    else:
                        await callback_query.message.answer(
                            "Вы уже использовали пробный период. Выберите тариф для покупки подписки:",
                            reply_markup=get_countries_keyboard()
                        )
            finally:
                session.close()
            
    except TelegramBadRequest as e:
        if "query is too old" in str(e):
            # Игнорируем устаревшие запросы
            logger.warning(f"Получен устаревший запрос: {e}")
            try:
                await callback_query.message.answer(
                    "Этот запрос устарел. Пожалуйста, повторите действие или отправьте /start для начала.",
                )
            except Exception as inner_e:
                logger.error(f"Ошибка при отправке сообщения об устаревшем запросе: {inner_e}")
        else:
            # Логируем другие ошибки TelegramBadRequest
            logger.error(f"Ошибка TelegramBadRequest: {e}")
    except Exception as e:
        logger.exception(f"Ошибка при обработке callback: {e}")
        await callback_query.message.answer(
            "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз или отправьте /start."
        )

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    """Обработчик предварительной проверки платежа"""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    """Обработчик успешного платежа"""
    try:
        # Получаем информацию о подписке из payload
        _, country_id, months, user_id = message.successful_payment.invoice_payload.split("_")
        country_id = int(country_id)
        months = int(months)
        user_id = int(user_id)
        
        # Создаем подписку
        session = Session()
        try:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                user = get_or_create_user(message.from_user, session)
            
            # Выбираем активный сервер для выбранной страны
            server = session.query(VPNServer).filter_by(
                country_id=country_id,
                is_active=True
            ).first()
            
            if not server:
                await message.answer(
                    "❌ Нет доступных серверов для выбранной страны. "
                    "Пожалуйста, обратитесь в техподдержку.",
                    reply_markup=get_back_keyboard()
                )
                return
                
            subscription = Subscription(
                user_id=user.telegram_id,
                country_id=country_id,
                server_id=server.id,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30*months),
                price=STAR_PRICES[months],
                is_active=True,
                payment_type="stars"
            )
            session.add(subscription)
            session.commit()
            
            success, client_uuid = await v2ray_manager.create_and_send_config(user_id, bot)
            if success:
                await message.answer(
                    f"✅ Оплата успешно получена!\n\n"
                    f"Ваша подписка активирована на {months} месяц(ев).\n"
                    f"Срок действия: до {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                    f"Конфигурация V2Ray отправлена отдельным сообщением.",
                    reply_markup=get_back_keyboard()
                )
            else:
                await message.answer(
                    f"✅ Оплата успешно получена, но возникла ошибка при создании конфигурации.\n"
                    f"Пожалуйста, обратитесь в техподдержку.",
                    reply_markup=get_back_keyboard()
                )
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Ошибка при обработке платежа: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке платежа. "
            "Пожалуйста, обратитесь в техподдержку.",
            reply_markup=get_back_keyboard()
        )

async def create_trial_subscription(user, session):
    """Создание пробной подписки"""
    from utils import is_admin  # Импортируем здесь, чтобы избежать циклической зависимости


    if await is_admin(user.telegram_id):  # Проверка на админа

        # Выбираем случайную страну с активными серверами
        country = session.query(Country).filter_by(is_active=True).first()
        if not country:
            return None

        # Выбираем активный сервер для выбранной страны
        server = session.query(VPNServer).filter_by(
            country_id=country.id,
            is_active=True
        ).first()

        if not server:
            return None

        # Создаем пробную подписку для админа без проверок
        subscription = Subscription(
            user_id=user.telegram_id,
            country_id=country.id,
            server_id=server.id,
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC) + timedelta(days=7),
            price=0,
            is_trial=True,
            is_active=True,
            payment_type="trial"
        )
        session.add(subscription)
        session.commit()
        return subscription
    else:
        # Проверяем, есть ли у пользователя активная подписка
        active_sub = user.get_active_subscription()
        if active_sub:
            return None

        # Выбираем случайную страну с активными серверами
        country = session.query(Country).filter_by(is_active=True).first()
        if not country:
            return None

        # Выбираем активный сервер для выбранной страны
        server = session.query(VPNServer).filter_by(
            country_id=country.id,
            is_active=True
        ).first()

        if not server:
            return None

    # Проверяем, есть ли у пользователя активная подписка
    active_sub = user.get_active_subscription()
    if active_sub:
        return None
        
    # Выбираем случайную страну с активными серверами
    country = session.query(Country).filter_by(is_active=True).first()
    if not country:
        return None
        
    # Выбираем активный сервер для выбранной страны
    server = session.query(VPNServer).filter_by(
        country_id=country.id,
        is_active=True
    ).first()
    
    if not server:
        return None
        
    # Создаем пробную подписку
    subscription = Subscription(
        user_id=user.telegram_id,
        country_id=country.id,
        server_id=server.id,
        start_date=datetime.now(UTC),
        end_date=datetime.now(UTC) + timedelta(days=7),
        price=0,
        is_trial=True,
        is_active=True,
        payment_type="trial"
    )
    session.add(subscription)
    session.commit()
    return subscription



@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Обработчик команды /admin"""
    if not await is_admin(message.from_user.id):
        await message.answer("⛔️ У вас нет доступа к админ-панели")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance")],
        [InlineKeyboardButton(text="🔑 Управление VPN", callback_data="admin_vpn")],
        [InlineKeyboardButton(text="🌍 Управление странами", callback_data="admin_countries")], 
        [InlineKeyboardButton(text="🖥️ Управление серверами", callback_data="admin_servers")],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
    ])

    await message.answer("🛠 Админ-панель", reply_markup=keyboard)

async def show_subscription_info(message: types.Message, subscription: Subscription) -> None:
    if subscription.end_date.tzinfo is None:
        end_date = subscription.end_date.replace(tzinfo=UTC)
    else:
        end_date = subscription.end_date
        
    days_left = (end_date - datetime.now(UTC)).days
    text = (
        f"🔑 Ваша подписка:\n\n"
        f"Статус: {'Активна ✅' if subscription.is_active else 'Неактивна ❌'}\n"
        f"Срок действия: до {end_date.strftime('%d.%m.%Y')}\n\n"
        f"Осталось дней: {days_left}\n"
    )

@dp.message(AdminStates.waiting_for_server_name)
async def process_server_name_input(message: types.Message, state: FSMContext):
    """Обработчик ввода имени сервера"""
    await state.update_data(server_name=message.text)
    
    # Получаем список стран
    session = Session()
    try:
        countries = session.query(Country).filter_by(is_active=True).all()
        if not countries:
            await message.answer(
                "❌ Нет доступных стран. Сначала добавьте хотя бы одну страну.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_servers")]
                ])
            )
            await state.clear()
            return
        
        # Создаем клавиатуру с выбором страны
        keyboard = []
        for country in countries:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{country.flag} {country.name}",
                    callback_data=f"server_country_{country.id}"
                )
            ])
        keyboard.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_servers")])
        
        await message.answer(
            "Выберите страну для сервера:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    finally:
        session.close()
    
    # Удаляем сообщение с названием сервера
    await message.delete()

@dp.callback_query(lambda c: c.data.startswith("server_country_"))
async def process_server_country_select(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора страны для сервера"""
    # Извлекаем ID страны из callback_data
    parts = callback_query.data.split('_')
    if len(parts) >= 3:
        try:
            country_id = int(parts[2])  # Формат server_country_ID
        except ValueError:
            await callback_query.answer("Ошибка в формате ID страны")
            return
    else:
        await callback_query.answer("Некорректный формат callback_data")
        return
        
    session = Session()
    
    try:
        # Получаем страну
        country = session.query(Country).filter_by(id=country_id).first()
        if not country:
            await callback_query.answer("Страна не найдена")
            return
            
        # Обновляем состояние
        await state.update_data(country_id=country_id)
        
        # Запрашиваем хост сервера
        await callback_query.message.edit_text(
            f"Выбрана страна: {country.flag} {country.name}\n\n"
            "Введите хост сервера (IP или домен):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_server")
            ]])
        )
        
        # Устанавливаем состояние ожидания хоста
        await state.set_state(AdminStates.waiting_for_server_host)
    finally:
        session.close()

@dp.message(AdminStates.waiting_for_server_host)
async def process_server_host_input(message: types.Message, state: FSMContext):
    """Обработчик ввода хоста сервера"""
    await state.update_data(server_host=message.text)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_servers")]
    ])
    
    await message.answer(
        "Введите порт сервера:",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.waiting_for_server_port)

@dp.message(AdminStates.waiting_for_server_port)
async def process_server_port_input(message: types.Message, state: FSMContext):
    """Обработчик ввода порта сервера"""
    try:
        port = int(message.text)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректный порт (1-65535):")
        return
    
    # Создаем новый сервер
    session = Session()
    try:
        data = await state.get_data()
        server = VPNServer(
            name=data['server_name'],
            host=data['server_host'],
            port=port,
            country_id=data['country_id'],
            is_active=True
        )
        session.add(server)
        session.commit()
        
        # Получаем страну для отображения в сообщении
        country = session.query(Country).filter_by(id=data['country_id']).first()
        
        await message.answer(
            f"✅ Сервер успешно добавлен!\n\n"
            f"Название: {server.name}\n"
            f"Страна: {country.flag} {country.name}\n"
            f"Хост: {server.host}\n"
            f"Порт: {server.port}"
        )
        
        # Показываем админ-панель
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance")],
            [InlineKeyboardButton(text="🔑 Управление VPN", callback_data="admin_vpn")],
            [InlineKeyboardButton(text="🌍 Управление странами", callback_data="admin_countries")], 
            [InlineKeyboardButton(text="🖥️ Управление серверами", callback_data="admin_servers")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
        ])
        
        await message.answer("🛠 Админ-панель", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении сервера: {e}")
        await message.answer("❌ Произошла ошибка при добавлении сервера.")
    finally:
        session.close()
    
    await state.clear()

async def main():
    # Инициализация базы данных
    init_db()
    
    if TEST_MODE:
        logger.info("Бот не запущен, так как используется тестовый режим")
        return
    
    # Запуск бота
    await dp.start_polling(bot)

# Добавляем обработчик вебхуков от TelegaPay
@app.post('/telegapay/webhook')
async def telegapay_webhook(request: Request):
    """Обработчик вебхуков от TelegaPay"""
    try:
        # Проверяем API ключ
        api_key = request.headers.get('X-API-Key')
        if api_key != TELEGAPAY_API_KEY:
            logger.warning(f"Получен вебхук с неверным API ключом: {api_key}")
            return {"success": False, "error": "Invalid API key"}
        
        # Получаем данные
        data = await request.json()
        logger.info(f"Получен вебхук от TelegaPay: {data}")
        
        transaction_id = data.get('transaction_id')
        status = data.get('status')
        type_tx = data.get('type')
        
        # Проверяем тип транзакции
        if type_tx != 'payin':
            logger.info(f"Получен вебхук для типа {type_tx}, игнорируем")
            return {"success": True}
        
        # Находим платеж по transaction_id
        found_payment_id = None
        for payment_id, payment_info in payment_manager.payments.items():
            if (payment_info.get("type") == "telegapay" and 
                payment_info.get("transaction_id") == transaction_id):
                found_payment_id = payment_id
                break
        
        if not found_payment_id:
            logger.warning(f"Платеж с transaction_id {transaction_id} не найден")
            return {"success": True}  # Всегда возвращаем успех для вебхуков
        
        payment_info = payment_manager.payments[found_payment_id]
        user_id = payment_info.get("user_id")
        duration = payment_info.get("duration")
        
        # Если статус completed, обновляем статус и создаем подписку
        if status == 'completed' and payment_info.get("status") != "paid":
            payment_info["status"] = "paid"
            
            # Получаем информацию о пользователе
            session = Session()
            try:
                user = session.query(User).filter_by(telegram_id=user_id).first()
                
                if not user:
                    logger.error(f"Пользователь с ID {user_id} не найден")
                    return {"success": True}
                
                # Деактивируем текущую подписку, если есть
                current_sub = user.get_active_subscription()
                if current_sub:
                    current_sub.is_active = False
                
                # Находим страну и сервер
                # По умолчанию берем первый активный сервер
                server = session.query(VPNServer).filter_by(is_active=True).first()
                
                if not server:
                    logger.error("Нет доступных серверов")
                    return {"success": True}
                
                # Создаем новую подписку
                subscription = Subscription(
                    user_id=user_id,
                    country_id=server.country_id,
                    server_id=server.id,
                    start_date=datetime.now(UTC),
                    end_date=datetime.now(UTC) + timedelta(days=30 * duration),
                    price=payment_manager.get_rub_price(duration),
                    is_active=True,
                    payment_type="telegapay"
                )
                session.add(subscription)
                user.is_active = True
                session.commit()
                
                # Отправляем уведомление пользователю
                try:
                    await bot.send_message(
                        user_id,
                        f"✅ Оплата успешно получена!\n\n"
                        f"Ваша подписка активирована на {duration} месяц(ев).\n"
                        f"Срок действия: до {subscription.end_date.strftime('%d.%m.%Y')}"
                    )
                    
                    # Создаем и отправляем конфигурацию
                    await v2ray_manager.create_and_send_config(user_id, bot)
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
                
            except Exception as e:
                logger.error(f"Ошибка при обработке вебхука: {e}")
            finally:
                session.close()
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука TelegaPay: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import asyncio
    import nest_asyncio
    
    # Применяем nest_asyncio для запуска нескольких циклов событий
    nest_asyncio.apply()
    
    # Запускаем бота и FastAPI одновременно
    async def start_services():
        # Инициализация базы данных
        init_db()
        
        # Импортируем планировщик для запуска задач по расписанию
        try:
            from scheduler import start_scheduler
            # Создаем и запускаем планировщик в отдельном потоке
            scheduler_task = asyncio.create_task(start_scheduler())
            logger.info("Планировщик задач запущен")
        except Exception as e:
            logger.error(f"Ошибка при запуске планировщика задач: {e}")
        
        # Запускаем бота
        bot_task = asyncio.create_task(main())
        
        # Запускаем веб-сервер
        web_task = asyncio.create_task(
            uvicorn.run(
                app, 
                host="0.0.0.0", 
                port=8000,
                log_level="info"
            )
        )
        
        # Собираем все задачи
        tasks = [bot_task, web_task]
        if 'scheduler_task' in locals():
            tasks.append(scheduler_task)
            
        await asyncio.gather(*tasks)
    
    asyncio.run(start_services())
