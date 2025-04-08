from datetime import datetime, timedelta, UTC
from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from database import User, Subscription, VPNServer, get_session
from config import logger
from utils import is_admin
from aiogram.exceptions import TelegramBadRequest

class AdminStates(StatesGroup):
    """Состояния для админ-панели"""
    waiting_for_user_id = State()

async def show_vpn_management(callback: types.CallbackQuery, bot: Bot):
    """Показать список пользователей с активными VPN конфигурациями"""
    if not await is_admin(callback.from_user.id):
        return
        
    session = get_session()
    try:
        # Получаем пользователей с активными подписками и их серверами
        active_users = session.query(User).options(
            joinedload(User.subscriptions).joinedload(Subscription.server)
        ).join(Subscription).join(VPNServer).filter(
            Subscription.is_active == True,
            Subscription.end_date >= datetime.now(UTC)
        ).all()
        
        if not active_users:
            text = "🔑 Нет активных VPN пользователей"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
            ])
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
            
        text = "🔑 Активные VPN пользователи:\n\n"
        keyboard = []
        
        for user in active_users:
            subscription = user.get_active_subscription()
            if subscription:
                # Убедимся, что end_date имеет часовой пояс UTC
                end_date = subscription.end_date.replace(tzinfo=UTC) if subscription.end_date.tzinfo is None else subscription.end_date
                days_left = (end_date - datetime.now(UTC)).days
                
                text += (
                    f"👤 {user.first_name or 'Пользователь'} "
                    f"({f'@{user.username}' if user.username else f'ID: {user.telegram_id}'})\n"
                    f"🌍 Сервер: {subscription.server.name}\n"
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
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(text, reply_markup=markup)
    finally:
        session.close()

async def manage_user_vpn(callback: types.CallbackQuery, bot: Bot):
    """Управление VPN конкретного пользователя"""
    if not await is_admin(callback.from_user.id):
        return
        
    user_id = int(callback.data.split('_')[2])
    session = get_session()
    
    try:
        # Получаем пользователя с активной подпиской и сервером
        user = session.query(User).options(
            joinedload(User.subscriptions).joinedload(Subscription.server)
        ).join(Subscription).join(VPNServer).filter(
            User.telegram_id == user_id,
            Subscription.is_active == True,
            Subscription.end_date >= datetime.now(UTC)
        ).first()
        
        if not user:
            await callback.answer("Пользователь не найден или нет активной подписки")
            return
            
        subscription = user.get_active_subscription()
        # Убедимся, что end_date имеет часовой пояс UTC
        end_date = subscription.end_date.replace(tzinfo=UTC) if subscription.end_date.tzinfo is None else subscription.end_date
        days_left = (end_date - datetime.now(UTC)).days
        
        text = (
            f"🔑 Управление VPN для пользователя:\n"
            f"👤 {user.first_name or 'Без имени'} "
            f"({f'@{user.username}' if user.username else f'ID: {user.telegram_id}'})\n\n"
            f"🌍 Сервер: {subscription.server.name}\n"
            f"📅 Дней осталось: {days_left}\n"
            f"💳 Тип подписки: {'Пробный' if subscription.is_trial else 'Платный'}\n"
            f"📆 Дата окончания: {end_date.strftime('%d.%m.%Y %H:%M')}\n"
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
        await callback.message.edit_text(text, reply_markup=markup)
    finally:
        session.close()

async def toggle_user_vpn(callback: types.CallbackQuery, bot: Bot):
    """Включение/отключение VPN для пользователя"""
    if not await is_admin(callback.from_user.id):
        return
        
    user_id = int(callback.data.split('_')[2])
    session = get_session()
    
    try:
        # Получаем текущее время в UTC
        now = datetime.now(UTC)
        subscription = session.query(Subscription).options(
            joinedload(Subscription.server)
        ).filter(
            Subscription.user_id == user_id,
            Subscription.end_date >= now
        ).first()
        
        if subscription:
            subscription.is_active = not subscription.is_active
            session.commit()
            
            status = "включен" if subscription.is_active else "отключен"
            await callback.answer(f"VPN {status} для пользователя {user_id}")
        else:
            await callback.answer("Активная подписка не найдена")
            
        # Возвращаемся к списку VPN
        await show_vpn_management(callback, bot)
    finally:
        session.close()

async def modify_vpn_duration(callback: types.CallbackQuery, bot: Bot):
    """Изменение срока действия VPN"""
    if not await is_admin(callback.from_user.id):
        return
        
    _, action, days, user_id = callback.data.split('_')
    days = int(days)
    user_id = int(user_id)
    
    session = get_session()
    
    try:
        # Получаем текущее время в UTC
        now = datetime.now(UTC)
        subscription = session.query(Subscription).options(
            joinedload(Subscription.server)
        ).filter(
            Subscription.user_id == user_id,
            Subscription.end_date >= now
        ).first()
        
        if subscription:
            # Убедимся, что end_date имеет часовой пояс UTC
            end_date = subscription.end_date.replace(tzinfo=UTC) if subscription.end_date.tzinfo is None else subscription.end_date
            # Обновляем дату окончания подписки
            subscription.end_date = end_date + timedelta(days=days)
            session.commit()
            
            await callback.answer(f"Срок действия VPN продлен на {days} дней")
        else:
            await callback.answer("Активная подписка не найдена")
            
        # Возвращаемся к списку VPN
        await show_vpn_management(callback, bot)
    finally:
        session.close()

async def show_stats(callback: types.CallbackQuery, bot: Bot):
    """Показывает общую статистику"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ У вас нет доступа к админ-панели")
        return

    session = get_session()
    try:
        # Получаем текущее время в UTC
        now = datetime.now(UTC)
        total_users = session.query(func.count(User.telegram_id)).scalar()
        active_subs = session.query(func.count(Subscription.id)).filter(
            Subscription.is_active == True,
            Subscription.end_date > now
        ).scalar()
        trial_users = session.query(func.count(Subscription.id)).filter(
            Subscription.is_trial == True
        ).scalar()
        active_servers = session.query(func.count(VPNServer.id)).filter(
            VPNServer.is_active == True
        ).scalar()

        stats_text = (
            "📊 Статистика:\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"✅ Активных подписок: {active_subs}\n"
            f"🎁 Пробных периодов: {trial_users}\n"
            f"🖥 Активных серверов: {active_servers}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ])

        await callback.message.edit_text(stats_text, reply_markup=keyboard)
    finally:
        session.close()

async def show_users(callback: types.CallbackQuery, bot: Bot, period: str = None):
    """Показывает список пользователей"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ У вас нет доступа к админ-панели")
        return

    session = get_session()
    try:
        query = session.query(User)
        
        # Фильтрация по периоду
        period_text = "за все время"
        if period:
            now = datetime.now(UTC)
            if period == "day":
                start_date = now - timedelta(days=1)
                period_text = "за последние 24 часа"
            elif period == "week":
                start_date = now - timedelta(weeks=1)
                period_text = "за последнюю неделю"
            elif period == "month":
                start_date = now - timedelta(days=30)
                period_text = "за последний месяц"
            query = query.filter(User.created_at >= start_date)
        
        users = query.all()
        total_users = len(users)
        
        text = f"👥 Список пользователей {period_text}\nВсего: {total_users} пользователей\n\n"
        
        for user in users:
            active_sub = user.get_active_subscription()
            status = "✅ Активен" if active_sub else "❌ Неактивен"
            subscription_info = ""
            if active_sub:
                # Убедимся, что end_date имеет часовой пояс UTC
                end_date = active_sub.end_date.replace(tzinfo=UTC) if active_sub.end_date.tzinfo is None else active_sub.end_date
                days_left = (end_date - datetime.now(UTC)).days
                subscription_info = f"\nПодписка: до {end_date.strftime('%d.%m.%Y')}\nОсталось дней: {days_left}"
            
            # Убедимся, что created_at имеет часовой пояс UTC
            created_at = user.created_at.replace(tzinfo=UTC) if user.created_at.tzinfo is None else user.created_at
            
            text += (
                f"👤 {user.first_name or 'Без имени'}\n"
                f"ID: {user.telegram_id}\n"
                f"Username: {'@' + user.username if user.username else 'нет'}\n"
                f"Дата регистрации: {created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"Статус: {status}"
                f"{subscription_info}\n\n"
            )

        # Добавляем индикацию текущего периода в кнопках
        day_text = "📅 Сутки ✓" if period == "day" else "📅 Сутки"
        week_text = "📅 Неделя ✓" if period == "week" else "📅 Неделя"
        month_text = "📅 Месяц ✓" if period == "month" else "📅 Месяц"

        keyboard = [
            [
                InlineKeyboardButton(text=day_text, callback_data="users_period_day"),
                InlineKeyboardButton(text=week_text, callback_data="users_period_week"),
                InlineKeyboardButton(text=month_text, callback_data="users_period_month")
            ],
            [
                InlineKeyboardButton(text="🔍 Поиск", callback_data="users_search"),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="users_refresh")
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ]

        try:
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback.answer("Данные не изменились")
            else:
                raise
    finally:
        session.close()

async def process_users_period(callback: types.CallbackQuery, bot: Bot):
    """Обработчик выбора периода для списка пользователей"""
    try:
        period = callback.data.split('_')[2]  # day, week или month
        await show_users(callback, bot, period)
    except Exception as e:
        logger.error(f"Error in process_users_period: {e}")
        await callback.answer("Произошла ошибка при обработке запроса")

async def refresh_users_list(callback: types.CallbackQuery, bot: Bot):
    """Обновление списка пользователей"""
    await show_users(callback, bot)

async def show_finance(callback: types.CallbackQuery, bot: Bot, period: str = None):
    """Показывает финансовую статистику"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ У вас нет доступа к админ-панели")
        return

    session = get_session()
    try:
        # Определяем период
        now = datetime.now(UTC)
        period_text = "за 30 дней"
        if period == "day":
            start_date = now - timedelta(days=1)
            period_text = "за последние 24 часа"
        elif period == "week":
            start_date = now - timedelta(weeks=1)
            period_text = "за последнюю неделю"
        elif period == "month":
            start_date = now - timedelta(days=30)
            period_text = "за последний месяц"
        else:
            start_date = now - timedelta(days=30)
        
        total_revenue = session.query(func.sum(Subscription.price)).filter(
            Subscription.payment_type == "stars",
            Subscription.start_date > start_date
        ).scalar() or 0

        total_subs = session.query(func.count(Subscription.id)).filter(
            Subscription.payment_type == "stars",
            Subscription.start_date > start_date
        ).scalar() or 0

        stats_text = (
            f"💰 Финансовая статистика {period_text}:\n\n"
            f"💫 Доход в звездах: {total_revenue}\n"
            f"📝 Количество продаж: {total_subs}\n"
            f"📊 Средний чек: {round(total_revenue/total_subs) if total_subs > 0 else 0}"
        )

        # Добавляем индикацию текущего периода в кнопках
        day_text = "📅 Сутки ✓" if period == "day" else "📅 Сутки"
        week_text = "📅 Неделя ✓" if period == "week" else "📅 Неделя"
        month_text = "📅 Месяц ✓" if period == "month" else "📅 Месяц"

        keyboard = [
            [
                InlineKeyboardButton(text=day_text, callback_data="finance_period_day"),
                InlineKeyboardButton(text=week_text, callback_data="finance_period_week"),
                InlineKeyboardButton(text=month_text, callback_data="finance_period_month")
            ],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="finance_refresh")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ]

        try:
            await callback.message.edit_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback.answer("Данные не изменились")
            else:
                raise
    finally:
        session.close()

async def process_finance_period(callback: types.CallbackQuery, bot: Bot):
    """Обработчик выбора периода для финансовой статистики"""
    try:
        period = callback.data.split('_')[2]  # day, week или month
        await show_finance(callback, bot, period)
    except Exception as e:
        logger.error(f"Error in process_finance_period: {e}")
        await callback.answer("Произошла ошибка при обработке запроса")

async def refresh_finance(callback: types.CallbackQuery, bot: Bot):
    """Обновление финансовой статистики"""
    await show_finance(callback, bot)

async def admin_back(callback: types.CallbackQuery, bot: Bot):
    """Возврат в главное меню админки"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ У вас нет доступа к админ-панели")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance")],
        [InlineKeyboardButton(text="🔑 Управление VPN", callback_data="admin_vpn")],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
    ])

    await callback.message.edit_text("🛠 Админ-панель", reply_markup=keyboard)

async def show_users_search(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    """Показывает форму поиска пользователей"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ У вас нет доступа к админ-панели")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users")]
    ])

    await callback.message.edit_text(
        "🔍 Введите ID пользователя для поиска:",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.waiting_for_user_id)

async def process_user_search(message: types.Message, bot: Bot, state: FSMContext):
    """Обработка поиска пользователя по ID"""
    if not await is_admin(message.from_user.id):
        return

    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ Некорректный ID пользователя. Введите число.")
        return

    session = get_session()
    try:
        user = session.query(User).options(
            joinedload(User.subscriptions).joinedload(Subscription.server)
        ).filter(User.telegram_id == user_id).first()
        
        if not user:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users")]
            ])
            await message.answer("❌ Пользователь не найден", reply_markup=keyboard)
            await state.clear()
            return

        active_sub = user.get_active_subscription()
        status = "✅ Активен" if active_sub else "❌ Неактивен"
        subscription_info = ""
        if active_sub:
            end_date = active_sub.end_date.replace(tzinfo=UTC) if active_sub.end_date.tzinfo is None else active_sub.end_date
            days_left = (end_date - datetime.now(UTC)).days
            subscription_info = f"\nПодписка: до {end_date.strftime('%d.%m.%Y')}\nОсталось дней: {days_left}"
        
        created_at = user.created_at.replace(tzinfo=UTC) if user.created_at.tzinfo is None else user.created_at
        
        text = (
            f"👤 Информация о пользователе:\n\n"
            f"Имя: {user.first_name or 'Без имени'}\n"
            f"ID: {user.telegram_id}\n"
            f"Username: {'@' + user.username if user.username else 'нет'}\n"
            f"Дата регистрации: {created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"Статус: {status}"
            f"{subscription_info}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Искать другого", callback_data="users_search")],
            [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="admin_users")]
        ])

        await message.answer(text, reply_markup=keyboard)
        await state.clear()
        
        # Удаляем сообщение с ID пользователя
        await message.delete()
    finally:
        session.close()

def register_admin_handlers(dp):
    """Регистрация обработчиков админ-панели"""
    dp.callback_query.register(show_stats, lambda c: c.data == "admin_stats")
    dp.callback_query.register(show_users, lambda c: c.data == "admin_users")
    dp.callback_query.register(show_finance, lambda c: c.data == "admin_finance")
    dp.callback_query.register(show_vpn_management, lambda c: c.data == "admin_vpn")
    dp.callback_query.register(admin_back, lambda c: c.data == "admin_back")
    dp.callback_query.register(manage_user_vpn, lambda c: c.data.startswith("manage_vpn_"))
    dp.callback_query.register(toggle_user_vpn, lambda c: c.data.startswith("vpn_toggle_"))
    dp.callback_query.register(modify_vpn_duration, lambda c: c.data.startswith("vpn_add_"))
    # Обработчики для списка пользователей
    dp.callback_query.register(process_users_period, lambda c: c.data.startswith("users_period_"))
    dp.callback_query.register(refresh_users_list, lambda c: c.data == "users_refresh")
    dp.callback_query.register(show_users_search, lambda c: c.data == "users_search")
    dp.message.register(process_user_search, AdminStates.waiting_for_user_id)
    # Обработчики для финансовой статистики
    dp.callback_query.register(process_finance_period, lambda c: c.data.startswith("finance_period_"))
    dp.callback_query.register(refresh_finance, lambda c: c.data == "finance_refresh") 