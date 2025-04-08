from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import Session, User, Subscription, delete_user, Country, VPNServer
from config import ADMIN_IDS
from datetime import datetime, timedelta, UTC
from v2ray import V2RayManager
import os
from aiogram.fsm.context import FSMContext
from sqlalchemy import cast, String
from aiogram import Router
from aiogram.fsm.state import State, StatesGroup
import logging

logger = logging.getLogger(__name__)
router = Router()

# Состояния для FSM
class AdminStates(StatesGroup):
    waiting_for_country_name = State()
    waiting_for_country_flag = State()
    waiting_for_server_name = State()
    waiting_for_server_host = State()
    waiting_for_server_port = State()
    waiting_for_server_password = State()

async def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def admin_panel(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🔑 Управление VPN", callback_data="admin_vpn")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance")]
    ])
    
    await message.answer("Админ-панель:", reply_markup=keyboard)

async def show_stats(callback_query: types.CallbackQuery):
    if not await is_admin(callback_query.from_user.id):
        return
    
    session = Session()
    now = datetime.now(UTC)
    
    total_users = session.query(User).count()
    active_users = session.query(User).filter_by(is_active=True).count()
    
    # Статистика по пробным периодам
    trial_active = session.query(Subscription).filter(
        Subscription.is_trial == True,
        Subscription.start_date <= now,
        Subscription.end_date >= now
    ).count()
    
    trial_total = session.query(Subscription).filter(
        Subscription.is_trial == True
    ).count()
    
    # Статистика по платным подпискам
    paid_active = session.query(Subscription).filter(
        Subscription.is_trial == False,
        Subscription.price > 0,
        Subscription.start_date <= now,
        Subscription.end_date >= now
    ).count()
    
    paid_total = session.query(Subscription).filter(
        Subscription.is_trial == False,
        Subscription.price > 0
    ).count()
    
    session.close()
    
    stats_text = (
        f"📊 Статистика:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Активных пользователей: {active_users}\n\n"
        f"🎁 Пробный период:\n"
        f"• Активных пробных: {trial_active}\n"
        f"• Всего выдано: {trial_total}\n\n"
        f"💰 Платные подписки:\n"
        f"• Активных платных: {paid_active}\n"
        f"• Всего продано: {paid_total}"
    )
    
    # Добавляем кнопку возврата
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback_query.message.edit_text(stats_text, reply_markup=keyboard)

async def show_users(callback_query: types.CallbackQuery):
    if not await is_admin(callback_query.from_user.id):
        return
    
    # Получаем параметры из callback_data если они есть
    parts = callback_query.data.split('_')
    if len(parts) > 1:
        period = parts[2] if len(parts) > 2 else None
        search = parts[3] if len(parts) > 3 else None
    else:
        period = None
        search = None
    
    session = Session()
    query = session.query(User)
    
    # Применяем фильтр по периоду
    if period:
        now = datetime.now(UTC)
        if period == 'day':
            query = query.filter(User.created_at >= now - timedelta(days=1))
        elif period == 'week':
            query = query.filter(User.created_at >= now - timedelta(weeks=1))
        elif period == 'month':
            query = query.filter(User.created_at >= now - timedelta(days=30))
    
    # Применяем поиск
    if search and search != 'none':
        search = search.lower()
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.telegram_id.cast(String).like(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%"))
        )
    
    # Получаем пользователей
    users = query.order_by(User.created_at.desc()).limit(10).all()
    
    # Формируем текст с результатами
    if period or (search and search != 'none'):
        users_text = "🔍 Результаты поиска:\n\n"
    else:
        users_text = "👥 Последние 10 пользователей:\n\n"
    
    for user in users:
        days_left = user.get_days_left()
        active_sub = user.get_active_subscription()
        sub_type = "Пробный" if (active_sub and active_sub.is_trial) else "Платный" if active_sub else "Нет"
        
        users_text += (
            f"ID: {user.telegram_id}\n"
            f"Username: {f'@{user.username}' if user.username else 'Не указан'}\n"
            f"Имя: {user.first_name or 'Не указано'}\n"
            f"Фамилия: {user.last_name or 'Не указана'}\n"
            f"Дата регистрации: {user.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Статус: {'Активен' if user.is_active else 'Неактивен'}\n"
            f"Тип подписки: {sub_type}\n"
            f"Дней осталось: {days_left}\n"
            f"[<a href='tg://user?id={user.telegram_id}'>Написать</a>] [/delete_{user.telegram_id}]\n\n"
        )
    
    if not users:
        users_text = "😕 Пользователи не найдены"
    
    # Создаем клавиатуру с фильтрами и поиском
    keyboard = [
        [
            InlineKeyboardButton(text="🕐 День", callback_data=f"users_filter_day_{search or 'none'}"),
            InlineKeyboardButton(text="📅 Неделя", callback_data=f"users_filter_week_{search or 'none'}"),
            InlineKeyboardButton(text="📆 Месяц", callback_data=f"users_filter_month_{search or 'none'}")
        ],
        [InlineKeyboardButton(text="🔍 Поиск", callback_data="users_search")],
        [InlineKeyboardButton(text="🔄 Сбросить фильтры", callback_data="admin_users")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ]
    
    await callback_query.message.edit_text(users_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

async def search_users(callback_query: types.CallbackQuery, state: FSMContext):
    """Запрос поискового запроса у пользователя"""
    if not await is_admin(callback_query.from_user.id):
        return
        
    await callback_query.message.edit_text(
        "🔍 Введите username, ID или имя пользователя для поиска:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_users")
        ]])
    )
    await state.set_state("waiting_for_search")

async def process_search_query(message: types.Message, state: FSMContext):
    """Обработка поискового запроса"""
    if not await is_admin(message.from_user.id):
        return
        
    search_query = message.text.strip()
    await state.clear()
    
    # Удаляем сообщение с поисковым запросом
    await message.delete()
    
    # Показываем результаты поиска
    callback_query = types.CallbackQuery(
        id="search_results",
        from_user=message.from_user,
        chat_instance="search",
        message=message,
        data=f"users_filter_none_{search_query}"
    )
    await show_users(callback_query)

async def show_finance(callback_query: types.CallbackQuery):
    if not await is_admin(callback_query.from_user.id):
        return
    
    session = Session()
    now = datetime.now(UTC)
    
    # Общая статистика
    all_subs = session.query(Subscription).filter(Subscription.price > 0).all()
    total_income = sum(sub.price for sub in all_subs)
    
    # Статистика за последний месяц
    month_ago = now - timedelta(days=30)
    monthly_subs = [sub for sub in all_subs if sub.start_date >= month_ago]
    monthly_income = sum(sub.price for sub in monthly_subs)
    
    # Статистика по активным подпискам
    active_subs = [sub for sub in all_subs if sub.start_date <= now <= sub.end_date]
    active_income = sum(sub.price for sub in active_subs)
    
    finance_text = (
        f"💰 Финансовая статистика:\n\n"
        f"Общий доход: {total_income}₽\n"
        f"Доход за последний месяц: {monthly_income}₽\n"
        f"Активных платных подписок: {len(active_subs)}\n"
        f"Сумма активных подписок: {active_income}₽"
    )
    
    # Добавляем кнопку возврата в админ-панель
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    session.close()
    await callback_query.message.edit_text(finance_text, reply_markup=keyboard)

async def admin_back(callback_query: types.CallbackQuery):
    if not await is_admin(callback_query.from_user.id):
        return
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🔑 Управление VPN", callback_data="admin_vpn")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance")]
    ])
    
    await callback_query.message.edit_text("Админ-панель:", reply_markup=keyboard)

async def show_vpn_management(callback_query: types.CallbackQuery):
    """Показать список пользователей с активными VPN конфигурациями"""
    if not await is_admin(callback_query.from_user.id):
        return
    
    session = Session()
    v2ray = V2RayManager(
        server_host=os.getenv('V2RAY_SERVER_HOST'),
        server_port=int(os.getenv('V2RAY_SERVER_PORT', 443))
    )
    
    try:
        # Получаем пользователей с активными подписками
        active_users = session.query(User).join(Subscription).filter(
            Subscription.is_active == True,
            Subscription.end_date >= datetime.now(UTC)
        ).all()
        
        if not active_users:
            text = "🔑 Нет активных VPN пользователей"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
            ])
            await callback_query.message.edit_text(text, reply_markup=keyboard)
            return
            
        text = "🔑 Активные VPN пользователи:\n\n"
        keyboard = []
        
        for user in active_users:
            config = v2ray.load_client_config(user.telegram_id)
            subscription = user.get_active_subscription()
            
            if config and subscription:
                expiry_date = datetime.fromisoformat(config["expiry"])
                days_left = (expiry_date - datetime.now(UTC)).days
                
                text += (
                    f"👤 {user.first_name or 'Пользователь'} "
                    f"({f'@{user.username}' if user.username else f'ID: {user.telegram_id}'})\n"
                    f"📅 Дней осталось: {days_left}\n"
                    f"💳 Тип: {'Пробный' if subscription.is_trial else 'Платный'}\n\n"
                )
                
                # Добавляем кнопки управления для каждого пользователя
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"⚙️ Управлять {user.first_name or f'ID: {user.telegram_id}'}",
                        callback_data=f"manage_vpn_{user.telegram_id}"
                    )
                ])
        
        # Добавляем кнопку возврата
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")])
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback_query.message.edit_text(text, reply_markup=markup)
    finally:
        session.close()

async def manage_user_vpn(callback_query: types.CallbackQuery):
    """Управление VPN конкретного пользователя"""
    if not await is_admin(callback_query.from_user.id):
        return
        
    user_id = int(callback_query.data.split('_')[2])
    session = Session()
    
    try:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            await callback_query.answer("Пользователь не найден")
            return
            
        subscription = user.get_active_subscription()
        if not subscription:
            await callback_query.answer("У пользователя нет активной подписки")
            return
            
        v2ray = V2RayManager(
            server_host=os.getenv('V2RAY_SERVER_HOST'),
            server_port=int(os.getenv('V2RAY_SERVER_PORT', 443))
        )
        config = v2ray.load_client_config(user.telegram_id)
        
        if not config:
            await callback_query.answer("Конфигурация VPN не найдена")
            return
            
        expiry_date = datetime.fromisoformat(config["expiry"])
        days_left = (expiry_date - datetime.now(UTC)).days
        
        text = (
            f"🔑 Управление VPN для пользователя:\n"
            f"👤 {user.first_name or 'Без имени'} "
            f"({f'@{user.username}' if user.username else f'ID: {user.telegram_id}'})\n\n"
            f"📅 Дней осталось: {days_left}\n"
            f"💳 Тип подписки: {'Пробный' if subscription.is_trial else 'Платный'}\n"
            f"📆 Дата окончания: {expiry_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"✅ Статус: {'Активен' if subscription.is_active else 'Неактивен'}"
        )
        
        # Кнопки управления
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🚫 Отключить" if subscription.is_active else "✅ Включить",
                    callback_data=f"vpn_toggle_{user_id}"
                )
            ],
            [
                InlineKeyboardButton(text="➕ 1 день", callback_data=f"vpn_add_1_{user_id}"),
                InlineKeyboardButton(text="➕ 7 дней", callback_data=f"vpn_add_7_{user_id}"),
                InlineKeyboardButton(text="➕ 30 дней", callback_data=f"vpn_add_30_{user_id}")
            ],
            [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="admin_vpn")]
        ]
        
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback_query.message.edit_text(text, reply_markup=markup)
    finally:
        session.close()

async def toggle_user_vpn(callback_query: types.CallbackQuery):
    """Включение/отключение VPN для пользователя"""
    if not await is_admin(callback_query.from_user.id):
        return
        
    user_id = int(callback_query.data.split('_')[2])
    session = Session()
    
    try:
        subscription = session.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.end_date >= datetime.now(UTC)
        ).first()
        
        if subscription:
            subscription.is_active = not subscription.is_active
            session.commit()
            
            status = "включен" if subscription.is_active else "отключен"
            await callback_query.answer(f"VPN {status} для пользователя {user_id}")
        else:
            await callback_query.answer("Активная подписка не найдена")
            
        # Возвращаемся к управлению пользователем
        await manage_user_vpn(callback_query)
    finally:
        session.close()

async def modify_vpn_duration(callback_query: types.CallbackQuery):
    """Изменение срока действия VPN"""
    if not await is_admin(callback_query.from_user.id):
        return
        
    _, action, days, user_id = callback_query.data.split('_')
    days = int(days)
    user_id = int(user_id)
    
    session = Session()
    v2ray = V2RayManager(
        server_host=os.getenv('V2RAY_SERVER_HOST'),
        server_port=int(os.getenv('V2RAY_SERVER_PORT', 443))
    )
    
    try:
        subscription = session.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.end_date >= datetime.now(UTC)
        ).first()
        
        if subscription:
            # Обновляем дату окончания подписки
            subscription.end_date += timedelta(days=days)
            
            # Создаем новую конфигурацию с обновленным сроком
            config, client_uuid = v2ray.generate_client_config(
                user_id,
                expiry_days=(subscription.end_date - datetime.now(UTC)).days
            )
            v2ray.save_client_config(user_id, config)
            
            session.commit()
            await callback_query.answer(f"Срок действия VPN продлен на {days} дней")
        else:
            await callback_query.answer("Активная подписка не найдена")
            
        # Возвращаемся к управлению пользователем
        await manage_user_vpn(callback_query)
    finally:
        session.close()

async def delete_user_command(message: types.Message):
    """Обработчик команды удаления пользователя"""
    if not await is_admin(message.from_user.id):
        return
        
    try:
        # Извлекаем ID пользователя из команды /delete_123456789
        user_id = int(message.text.split('_')[1])
        
        # Удаляем пользователя
        if delete_user(user_id):
            await message.reply(f"✅ Пользователь {user_id} успешно удален")
        else:
            await message.reply(f"❌ Пользователь {user_id} не найден")
    except (IndexError, ValueError):
        await message.reply("❌ Неверный формат команды. Используйте: /delete_ID")

def get_admin_keyboard():
    """Создание клавиатуры админ-панели"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users")],
        [InlineKeyboardButton(text="🌍 Управление странами", callback_data="admin_countries")],
        [InlineKeyboardButton(text="🖥 Управление серверами", callback_data="admin_servers")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance")]
    ])

def get_users_keyboard():
    """Создание клавиатуры управления пользователями"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="users_stats")],
        [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="users_search")],
        [InlineKeyboardButton(text="📅 Фильтр по времени", callback_data="users_filter")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

def get_countries_keyboard():
    """Создание клавиатуры управления странами"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить страну", callback_data="country_add")],
        [InlineKeyboardButton(text="🗑 Удалить страну", callback_data="country_delete")],
        [InlineKeyboardButton(text="⚡️ Включить/выключить", callback_data="country_toggle")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

def get_servers_keyboard():
    """Создание клавиатуры управления серверами"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить сервер", callback_data="server_add")],
        [InlineKeyboardButton(text="🗑 Удалить сервер", callback_data="server_delete")],
        [InlineKeyboardButton(text="⚡️ Включить/выключить", callback_data="server_toggle")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

def get_finance_keyboard():
    """Создание клавиатуры финансов"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="finance_stats")],
        [InlineKeyboardButton(text="📅 Фильтр по времени", callback_data="finance_filter")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Обработчик команды /admin"""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.")
        return
        
    await message.answer(
        "Админ-панель\nВыберите раздел:",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data == "admin_back")
async def process_admin_back(callback: types.CallbackQuery):
    """Обработчик кнопки назад в админ-панели"""
    await callback.message.edit_text(
        "Админ-панель\nВыберите раздел:",
        reply_markup=get_admin_keyboard()
    )

# Обработчики для управления пользователями
@router.callback_query(F.data == "admin_users")
async def process_admin_users(callback: types.CallbackQuery):
    """Обработчик раздела управления пользователями"""
    await callback.message.edit_text(
        "Управление пользователями\nВыберите действие:",
        reply_markup=get_users_keyboard()
    )

@router.callback_query(F.data == "users_stats")
async def process_users_stats(callback: types.CallbackQuery):
    """Обработчик статистики пользователей"""
    session = Session()
    try:
        total_users = session.query(User).count()
        active_users = session.query(User).filter_by(is_active=True).count()
        total_subscriptions = session.query(Subscription).count()
        active_subscriptions = session.query(Subscription).filter_by(is_active=True).count()
        
        stats_text = (
            f"📊 Статистика пользователей:\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"✅ Активных пользователей: {active_users}\n"
            f"💎 Всего подписок: {total_subscriptions}\n"
            f"✅ Активных подписок: {active_subscriptions}"
        )
        
        await callback.message.edit_text(
            stats_text,
            reply_markup=get_users_keyboard()
        )
    finally:
        session.close()

@router.callback_query(F.data == "users_filter")
async def process_users_filter(callback: types.CallbackQuery):
    """Обработчик фильтра пользователей по времени"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 За день", callback_data="users_filter_day")],
        [InlineKeyboardButton(text="📅 За неделю", callback_data="users_filter_week")],
        [InlineKeyboardButton(text="📅 За месяц", callback_data="users_filter_month")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users")]
    ])
    
    await callback.message.edit_text(
        "Выберите период для фильтрации:",
        reply_markup=keyboard
    )

# Обработчики для управления странами
@router.callback_query(F.data == "admin_countries")
async def process_admin_countries(callback: types.CallbackQuery):
    """Обработчик раздела управления странами"""
    await callback.message.edit_text(
        "Управление странами\nВыберите действие:",
        reply_markup=get_countries_keyboard()
    )

@router.callback_query(F.data == "country_add")
async def process_country_add(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик добавления страны"""
    await state.set_state(AdminStates.waiting_for_country_name)
    await callback.message.edit_text(
        "Введите название страны:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_countries")
        ]])
    )

@router.message(AdminStates.waiting_for_country_name)
async def process_country_name(message: types.Message, state: FSMContext):
    """Обработчик названия страны"""
    await state.update_data(country_name=message.text)
    await state.set_state(AdminStates.waiting_for_country_flag)
    await message.answer(
        "Введите эмодзи флага страны:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_countries")
        ]])
    )

@router.message(AdminStates.waiting_for_country_flag)
async def process_country_flag(message: types.Message, state: FSMContext):
    """Обработчик флага страны"""
    data = await state.get_data()
    session = Session()
    try:
        country = Country(
            name=data['country_name'],
            flag=message.text
        )
        session.add(country)
        session.commit()
        await message.answer(
            f"✅ Страна {data['country_name']} {message.text} успешно добавлена!",
            reply_markup=get_countries_keyboard()
        )
    finally:
        session.close()
        await state.clear()

# Обработчики для управления серверами
@router.callback_query(F.data == "admin_servers")
async def process_admin_servers(callback: types.CallbackQuery):
    """Обработчик раздела управления серверами"""
    await callback.message.edit_text(
        "Управление серверами\nВыберите действие:",
        reply_markup=get_servers_keyboard()
    )

@router.callback_query(F.data == "server_add")
async def process_server_add(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик добавления сервера"""
    await state.set_state(AdminStates.waiting_for_server_name)
    await callback.message.edit_text(
        "Введите название сервера:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_servers")
        ]])
    )

@router.message(AdminStates.waiting_for_server_name)
async def process_server_name(message: types.Message, state: FSMContext):
    """Обработчик названия сервера"""
    await state.update_data(server_name=message.text)
    await state.set_state(AdminStates.waiting_for_server_host)
    await message.answer(
        "Введите хост сервера (IP или домен):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_servers")
        ]])
    )

@router.message(AdminStates.waiting_for_server_host)
async def process_server_host(message: types.Message, state: FSMContext):
    """Обработчик хоста сервера"""
    await state.update_data(server_host=message.text)
    await state.set_state(AdminStates.waiting_for_server_port)
    await message.answer(
        "Введите порт сервера:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_servers")
        ]])
    )

@router.message(AdminStates.waiting_for_server_port)
async def process_server_port(message: types.Message, state: FSMContext):
    """Обработчик порта сервера"""
    await state.update_data(server_port=message.text)
    await state.set_state(AdminStates.waiting_for_server_password)
    await message.answer(
        "Введите пароль сервера:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_servers")
        ]])
    )

@router.message(AdminStates.waiting_for_server_password)
async def process_server_password(message: types.Message, state: FSMContext):
    """Обработчик пароля сервера"""
    data = await state.get_data()
    session = Session()
    try:
        server = VPNServer(
            name=data['server_name'],
            host=data['server_host'],
            port=int(data['server_port']),
            password=message.text
        )
        session.add(server)
        session.commit()
        await message.answer(
            f"✅ Сервер {data['server_name']} успешно добавлен!",
            reply_markup=get_servers_keyboard()
        )
    finally:
        session.close()
        await state.clear()

# Обработчики для финансов
@router.callback_query(F.data == "admin_finance")
async def process_admin_finance(callback: types.CallbackQuery):
    """Обработчик раздела финансов"""
    await callback.message.edit_text(
        "Финансы\nВыберите действие:",
        reply_markup=get_finance_keyboard()
    )

@router.callback_query(F.data == "finance_stats")
async def process_finance_stats(callback: types.CallbackQuery):
    """Обработчик статистики финансов"""
    session = Session()
    try:
        # Получаем статистику за разные периоды
        now = datetime.now(UTC)
        
        # За день
        day_start = now - timedelta(days=1)
        day_stats = session.query(Subscription).filter(
            Subscription.created_at >= day_start
        ).all()
        day_total = sum(sub.price for sub in day_stats)
        
        # За неделю
        week_start = now - timedelta(weeks=1)
        week_stats = session.query(Subscription).filter(
            Subscription.created_at >= week_start
        ).all()
        week_total = sum(sub.price for sub in week_stats)
        
        # За месяц
        month_start = now - timedelta(days=30)
        month_stats = session.query(Subscription).filter(
            Subscription.created_at >= month_start
        ).all()
        month_total = sum(sub.price for sub in month_stats)
        
        stats_text = (
            f"💰 Финансовая статистика:\n\n"
            f"📅 За день: {day_total} ⭐️\n"
            f"📅 За неделю: {week_total} ⭐️\n"
            f"📅 За месяц: {month_total} ⭐️"
        )
        
        await callback.message.edit_text(
            stats_text,
            reply_markup=get_finance_keyboard()
        )
    finally:
        session.close()

def register_admin_handlers(dp: Dispatcher):
    dp.message.register(admin_panel, Command("admin"))
    dp.callback_query.register(show_stats, lambda c: c.data == "admin_stats")
    dp.callback_query.register(show_users, lambda c: c.data == "admin_users" or c.data.startswith("users_filter_"))
    dp.callback_query.register(show_finance, lambda c: c.data == "admin_finance")
    dp.callback_query.register(admin_back, lambda c: c.data == "admin_panel")
    dp.callback_query.register(show_vpn_management, lambda c: c.data == "admin_vpn")
    dp.callback_query.register(manage_user_vpn, lambda c: c.data and c.data.startswith("manage_vpn_"))
    dp.callback_query.register(toggle_user_vpn, lambda c: c.data and c.data.startswith("vpn_toggle_"))
    dp.callback_query.register(modify_vpn_duration, lambda c: c.data and c.data.startswith("vpn_add_"))
    dp.callback_query.register(search_users, lambda c: c.data == "users_search")
    dp.message.register(process_search_query, F.text, StateFilter("waiting_for_search"))
    dp.message.register(delete_user_command, lambda m: m.text and m.text.startswith("/delete_"))
    dp.include_router(router) 