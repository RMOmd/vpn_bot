from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import Session, User, Subscription
from config import ADMIN_IDS
from datetime import datetime, timedelta, UTC

async def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def admin_panel(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
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
    
    session = Session()
    users = session.query(User).order_by(User.created_at.desc()).limit(10).all()
    
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
            f"Дней осталось: {days_left}\n\n"
        )
    
    session.close()
    
    # Добавляем кнопку возврата в админ-панель
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback_query.message.edit_text(users_text, reply_markup=keyboard)

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
        [InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance")]
    ])
    
    await callback_query.message.edit_text("Админ-панель:", reply_markup=keyboard)

def register_admin_handlers(dp: Dispatcher):
    dp.message.register(admin_panel, Command("admin"))
    dp.callback_query.register(show_stats, lambda c: c.data == "admin_stats")
    dp.callback_query.register(show_users, lambda c: c.data == "admin_users")
    dp.callback_query.register(show_finance, lambda c: c.data == "admin_finance")
    dp.callback_query.register(admin_back, lambda c: c.data == "admin_panel") 