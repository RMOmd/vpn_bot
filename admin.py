from datetime import datetime, timedelta, UTC
from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from database import User, Subscription, VPNServer, Country, get_session
from config import logger
from utils import is_admin
from aiogram.exceptions import TelegramBadRequest
from states import AdminStates

async def show_vpn_management(callback: types.CallbackQuery, bot: Bot, **kwargs):
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

async def manage_user_vpn(callback: types.CallbackQuery, bot: Bot, **kwargs):
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

async def toggle_user_vpn(callback: types.CallbackQuery, bot: Bot, **kwargs):
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

async def modify_vpn_duration(callback: types.CallbackQuery, bot: Bot, **kwargs):
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

async def show_stats(callback: types.CallbackQuery, bot: Bot, **kwargs):
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

async def show_users(callback: types.CallbackQuery, bot: Bot, period: str = None, **kwargs):
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

async def process_users_period(callback: types.CallbackQuery, bot: Bot, **kwargs):
    """Обработчик выбора периода для списка пользователей"""
    try:
        period = callback.data.split('_')[2]  # day, week или month
        await show_users(callback, bot, period)
    except Exception as e:
        logger.error(f"Error in process_users_period: {e}")
        await callback.answer("Произошла ошибка при обработке запроса")

async def refresh_users_list(callback: types.CallbackQuery, bot: Bot, **kwargs):
    """Обновление списка пользователей"""
    await show_users(callback, bot)

async def show_finance(callback: types.CallbackQuery, bot: Bot, period: str = None, **kwargs):
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

async def process_finance_period(callback: types.CallbackQuery, bot: Bot, **kwargs):
    """Обработчик выбора периода для финансовой статистики"""
    try:
        period = callback.data.split('_')[2]  # day, week или month
        await show_finance(callback, bot, period)
    except Exception as e:
        logger.error(f"Error in process_finance_period: {e}")
        await callback.answer("Произошла ошибка при обработке запроса")

async def refresh_finance(callback: types.CallbackQuery, bot: Bot, **kwargs):
    """Обновление финансовой статистики"""
    await show_finance(callback, bot)

async def admin_back(callback: types.CallbackQuery, bot: Bot, **kwargs):
    """Возврат в главное меню админки"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ У вас нет доступа к админ-панели")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance")],
        [InlineKeyboardButton(text="🔑 Управление VPN", callback_data="admin_vpn")],
        [InlineKeyboardButton(text="🌍 Управление странами", callback_data="admin_countries")],
        [InlineKeyboardButton(text="🛠️ Управление серверами", callback_data="admin_servers")],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
    ])

    await callback.message.edit_text("🛠 Админ-панель", reply_markup=keyboard)

async def show_users_search(callback: types.CallbackQuery, bot: Bot, state: FSMContext, **kwargs):
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

async def process_user_search(message: types.Message, bot: Bot, state: FSMContext, **kwargs):
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

async def show_countries_management(callback: types.CallbackQuery, bot: Bot, **kwargs):
    """Показать список стран и управление ими"""
    if not await is_admin(callback.from_user.id):
        return
        
    session = get_session()
    try:
        # Получаем все страны
        countries = session.query(Country).all()
        
        text = "🌍 Управление странами:\n\n"
        keyboard = []
        
        for country in countries:
            status = "✅" if country.is_active else "❌"
            text += f"{status} {country.flag} {country.name}\n"
            
            # Добавляем кнопки управления для каждой страны
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{'🔴 Отключить' if country.is_active else '🟢 Включить'} {country.flag}",
                    callback_data=f"country_toggle_{country.id}"
                ),
                InlineKeyboardButton(
                    text=f"🗑 Удалить {country.flag}",
                    callback_data=f"country_delete_{country.id}"
                )
            ])
        
        # Добавляем кнопку добавления новой страны и возврата
        keyboard.extend([
            [InlineKeyboardButton(text="➕ Добавить страну", callback_data="country_add")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ])
        
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=markup)
    finally:
        session.close()

async def toggle_country(callback: types.CallbackQuery, bot: Bot, **kwargs):
    """Включение/отключение страны"""
    if not await is_admin(callback.from_user.id):
        return
        
    country_id = int(callback.data.split('_')[2])
    session = get_session()
    
    try:
        country = session.query(Country).filter_by(id=country_id).first()
        if country:
            country.is_active = not country.is_active
            session.commit()
            status = "включена" if country.is_active else "отключена"
            await callback.answer(f"Страна {country.flag} {country.name} {status}")
        else:
            await callback.answer("Страна не найдена")
        
        # Обновляем список стран
        await show_countries_management(callback, bot)
    finally:
        session.close()

async def delete_country(callback: types.CallbackQuery, bot: Bot, **kwargs):
    """Удаление страны"""
    if not await is_admin(callback.from_user.id):
        return
        
    country_id = int(callback.data.split('_')[2])
    session = get_session()
    
    try:
        country = session.query(Country).filter_by(id=country_id).first()
        if country:
            # Проверяем, есть ли активные подписки для этой страны
            active_subs = session.query(Subscription).filter(
                Subscription.country_id == country_id,
                Subscription.is_active == True,
                Subscription.end_date >= datetime.now(UTC)
            ).count()
            
            if active_subs > 0:
                await callback.answer(
                    f"Невозможно удалить страну {country.flag} {country.name}: "
                    f"есть {active_subs} активных подписок",
                    show_alert=True
                )
            else:
                # Удаляем страну
                session.delete(country)
                session.commit()
                await callback.answer(f"Страна {country.flag} {country.name} удалена")
        else:
            await callback.answer("Страна не найдена")
        
        # Обновляем список стран
        await show_countries_management(callback, bot)
    finally:
        session.close()

async def start_add_country(callback: types.CallbackQuery, bot: Bot, state: FSMContext, **kwargs):
    """Начало процесса добавления страны"""
    if not await is_admin(callback.from_user.id):
        return
        
    await callback.message.edit_text(
        "🌍 Добавление новой страны\n\n"
        "Введите название страны (например: Россия):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="countries_cancel")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_country_name)

async def process_country_name(message: types.Message, bot: Bot, state: FSMContext, **kwargs):
    """Обработка ввода названия страны"""
    if not await is_admin(message.from_user.id):
        return
        
    # Сохраняем название страны
    await state.update_data(country_name=message.text)
    
    # Просим ввести эмодзи флага
    await message.answer(
        "Отправьте эмодзи флага страны (например: 🇷🇺):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="countries_cancel")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_country_code)
    
    # Удаляем сообщение с названием страны
    await message.delete()

async def process_country_flag(message: types.Message, bot: Bot, state: FSMContext, **kwargs):
    """Обработка ввода флага страны"""
    if not await is_admin(message.from_user.id):
        return
        
    # Проверяем, что отправлен эмодзи флага
    if not message.text or len(message.text) > 4:
        await message.answer(
            "❌ Пожалуйста, отправьте только эмодзи флага страны.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="countries_cancel")]
            ])
        )
        return
        
    # Получаем сохраненное название страны
    data = await state.get_data()
    country_name = data.get('country_name')
    
    session = get_session()
    try:
        # Создаем новую страну
        country = Country(
            name=country_name,
            flag=message.text,
            is_active=True
        )
        session.add(country)
        session.commit()
        
        # Очищаем состояние
        await state.clear()
        
        # Отправляем сообщение об успехе
        callback_message = await message.answer(
            f"✅ Страна {country.flag} {country.name} успешно добавлена!"
        )
        
        # Показываем обновленный список стран
        callback = types.CallbackQuery(
            id="0",
            from_user=message.from_user,
            chat_instance="0",
            message=callback_message,
            data="admin_countries"
        )
        await show_countries_management(callback, bot)
        
        # Удаляем сообщение с флагом
        await message.delete()
    finally:
        session.close()

async def cancel_country_add(callback: types.CallbackQuery, bot: Bot, state: FSMContext, **kwargs):
    """Отмена добавления страны"""
    await state.clear()
    await show_countries_management(callback, bot)

async def process_admin_servers(callback_query: types.CallbackQuery, bot: Bot, **kwargs):
    """Обработчик кнопки управления серверами"""
    if not await is_admin(callback_query.from_user.id):
        await callback_query.answer("У вас нет доступа к этой функции.")
        return

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

async def process_add_server(callback_query: types.CallbackQuery, state: FSMContext, **kwargs):
    """Обработчик кнопки добавления сервера"""
    if not await is_admin(callback_query.from_user.id):
        await callback_query.answer("У вас нет доступа к этой функции.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_servers")]
    ])
    
    await callback_query.message.edit_text(
        "Добавление нового VPN сервера\n\n"
        "Введите название сервера:",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.waiting_for_server_name)

async def process_server_name(message: types.Message, state: FSMContext, **kwargs):
    """Обработчик ввода названия сервера"""
    await state.update_data(server_name=message.text)
    
    # Получаем список стран
    session = get_session()
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

async def process_server_country(callback: types.CallbackQuery, state: FSMContext, bot: Bot, **kwargs):
    """Обработка выбора страны для сервера"""
    if not await is_admin(callback.from_user.id):
        return
        
    country_id = int(callback.data.split('_')[1])
    session = get_session()
    
    try:
        # Получаем страну
        country = session.query(Country).filter_by(id=country_id).first()
        if not country:
            await callback.answer("Страна не найдена")
            return
            
        # Обновляем состояние
        await state.update_data(country_id=country_id)
        
        # Запрашиваем хост сервера
        await callback.message.edit_text(
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

async def process_server_host(message: types.Message, state: FSMContext, **kwargs):
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

async def process_server_port(message: types.Message, state: FSMContext, **kwargs):
    """Обработчик ввода порта сервера"""
    try:
        port = int(message.text)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректный порт (1-65535):")
        return
    
    # Создаем новый сервер
    session = get_session()
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
    except Exception as e:
        logger.error(f"Ошибка при добавлении сервера: {e}")
        await message.answer("❌ Произошла ошибка при добавлении сервера.")
    finally:
        session.close()
    
    await state.clear()
    # Создаем callback_query для возврата в админ-панель
    callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        chat_instance="0",
        message=message,
        data="admin_back"
    )
    await admin_back(callback, bot)

async def process_list_servers(callback_query: types.CallbackQuery, bot: Bot, **kwargs):
    """Обработчик кнопки просмотра списка серверов"""
    if not await is_admin(callback_query.from_user.id):
        await callback_query.answer("У вас нет доступа к этой функции.")
        return

    session = get_session()
    try:
        servers = session.query(VPNServer).options(joinedload(VPNServer.country)).all()
        
        if not servers:
            await callback_query.message.edit_text(
                "Список серверов пуст.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_servers")]
                ])
            )
            return
        
        text = "📋 Список VPN серверов:\n\n"
        keyboard_buttons = []
        
        for server in servers:
            status = "🟢" if server.is_active else "🔴"
            text += f"{status} {server.name}\n"
            text += f"🌍 Страна: {server.country.flag} {server.country.name}\n"
            text += f"📍 Хост: {server.host}\n"
            text += f"🔌 Порт: {server.port}\n"
            text += f"👥 Подключений: {len(server.subscriptions)}\n\n"
            
            # Добавляем кнопки управления для каждого сервера
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{'🔴 Деактивировать' if server.is_active else '🟢 Активировать'} {server.name}",
                    callback_data=f"server_toggle_{server.id}"
                )
            ])
            if len(server.subscriptions) == 0:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"❌ Удалить {server.name}",
                        callback_data=f"server_delete_{server.id}"
                    )
                ])
        
        keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_servers")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    finally:
        session.close()

async def process_server_action(callback_query: types.CallbackQuery, bot: Bot, **kwargs):
    """Обработчик действий с сервером"""
    if not await is_admin(callback_query.from_user.id):
        await callback_query.answer("У вас нет доступа к этой функции.")
        return

    action, server_id = callback_query.data.split("_")[1:]
    server_id = int(server_id)
    
    session = get_session()
    try:
        server = session.query(VPNServer).filter_by(id=server_id).first()
        if not server:
            await callback_query.answer("Сервер не найден.")
            return
        
        if action == "toggle":
            server.is_active = not server.is_active
            session.commit()
            status = "активирован" if server.is_active else "деактивирован"
            await callback_query.answer(f"Сервер {status}")
        elif action == "delete":
            if len(server.subscriptions) > 0:
                await callback_query.answer("Нельзя удалить сервер с активными подписками.")
                return
            session.delete(server)
            session.commit()
            await callback_query.answer("Сервер удален")
        
        # Обновляем список серверов
        await process_list_servers(callback_query, bot)
    except Exception as e:
        logger.error(f"Ошибка при обработке действия с сервером: {e}")
        await callback_query.answer("Произошла ошибка")
    finally:
        session.close()

def register_admin_handlers(dp, bot: Bot):
    """Регистрация обработчиков админ-панели"""
    # Создаем функцию-обертку для передачи bot в обработчики
    def wrap_handler(handler):
        async def wrapper(event, *args, **kwargs):
            return await handler(event, *args, **kwargs)
        return wrapper

    # Регистрируем обработчики с оберткой
    dp.callback_query.register(wrap_handler(show_stats), lambda c: c.data == "admin_stats")
    dp.callback_query.register(wrap_handler(show_users), lambda c: c.data == "admin_users")
    dp.callback_query.register(wrap_handler(show_finance), lambda c: c.data == "admin_finance")
    dp.callback_query.register(wrap_handler(show_vpn_management), lambda c: c.data == "admin_vpn")
    dp.callback_query.register(wrap_handler(admin_back), lambda c: c.data == "admin_back")
    dp.callback_query.register(wrap_handler(manage_user_vpn), lambda c: c.data.startswith("manage_vpn_"))
    dp.callback_query.register(wrap_handler(toggle_user_vpn), lambda c: c.data.startswith("vpn_toggle_"))
    dp.callback_query.register(wrap_handler(modify_vpn_duration), lambda c: c.data.startswith("vpn_add_"))
    # Обработчики для списка пользователей
    dp.callback_query.register(wrap_handler(process_users_period), lambda c: c.data.startswith("users_period_"))
    dp.callback_query.register(wrap_handler(refresh_users_list), lambda c: c.data == "users_refresh")
    dp.callback_query.register(wrap_handler(show_users_search), lambda c: c.data == "users_search")
    dp.message.register(process_user_search, AdminStates.waiting_for_user_id)
    # Обработчики для финансовой статистики
    dp.callback_query.register(wrap_handler(process_finance_period), lambda c: c.data.startswith("finance_period_"))
    dp.callback_query.register(wrap_handler(refresh_finance), lambda c: c.data == "finance_refresh")
    # Обработчики для управления странами
    dp.callback_query.register(wrap_handler(show_countries_management), lambda c: c.data == "admin_countries")
    dp.callback_query.register(wrap_handler(toggle_country), lambda c: c.data.startswith("country_toggle_"))
    dp.callback_query.register(wrap_handler(delete_country), lambda c: c.data.startswith("country_delete_"))
    dp.callback_query.register(wrap_handler(start_add_country), lambda c: c.data == "country_add")
    dp.callback_query.register(wrap_handler(cancel_country_add), lambda c: c.data == "countries_cancel")
    dp.message.register(process_country_name, AdminStates.waiting_for_country_name)
    dp.message.register(process_country_flag, AdminStates.waiting_for_country_code)
    # Обработчики для управления серверами
    dp.callback_query.register(wrap_handler(process_admin_servers), lambda c: c.data == "admin_servers")
    dp.callback_query.register(wrap_handler(process_add_server), lambda c: c.data == "add_server")
    dp.callback_query.register(wrap_handler(process_list_servers), lambda c: c.data == "list_servers")
    dp.callback_query.register(wrap_handler(process_server_action), lambda c: c.data.startswith("server_"))
    dp.callback_query.register(wrap_handler(process_server_country), lambda c: c.data.startswith("server_country_"))
    dp.message.register(process_server_name, AdminStates.waiting_for_server_name)
    dp.message.register(process_server_host, AdminStates.waiting_for_server_host)
    dp.message.register(process_server_port, AdminStates.waiting_for_server_port) 