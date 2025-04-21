import asyncio
import logging
from datetime import datetime, timedelta, UTC
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import Session, Subscription, User
from aiogram import Bot
from config import BOT_TOKEN, ADMIN_IDS

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем планировщик задач
scheduler = AsyncIOScheduler()

# Вспомогательный класс для эмуляции работы с VPN
class VPNManager:
    """Класс для управления VPN-конфигурациями"""
    
    def remove_client_config(self, config_name):
        """Удаляет конфигурацию клиента с сервера"""
        logger.info(f"Имитация удаления конфигурации {config_name}")
        # В реальной реализации здесь должен быть код для удаления конфигурации
        return True
        
    def check_interface_status(self):
        """Проверяет статус VPN-интерфейса"""
        # В реальной реализации здесь должен быть код для проверки статуса
        return {"is_active": True, "status": "running"}

# Получение экземпляра бота
def get_bot():
    """Возвращает экземпляр бота"""
    return Bot(token=BOT_TOKEN)

async def check_upcoming_expirations():
    """
    Проверяет подписки, срок действия которых истекает в ближайшие 3 дня,
    и отправляет уведомления пользователям, если они еще не были уведомлены
    """
    logger.info("Проверка истекающих подписок...")
    bot = get_bot()
    current_time = datetime.now(UTC)
    notification_threshold = current_time + timedelta(days=3)
    
    with Session() as session:
        # Получаем активные подписки, которые истекают в ближайшие 3 дня
        expiring_subscriptions = session.query(Subscription).join(User)\
            .filter(
                Subscription.is_active == True,
                Subscription.end_date <= notification_threshold,
                Subscription.end_date > current_time,
                Subscription.expiry_notified == False
            ).all()
        
        logger.info(f"Найдено {len(expiring_subscriptions)} истекающих подписок")
        
        for subscription in expiring_subscriptions:
            user = subscription.user
            days_left = (subscription.end_date - current_time).days
            
            # Отправляем уведомление пользователю
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"⚠️ Внимание! Ваша подписка истекает через {days_left} дней. "
                    f"Пожалуйста, продлите её, чтобы продолжить пользоваться сервисом."
                )
                
                # Отмечаем, что уведомление отправлено
                subscription.expiry_notified = True
                session.commit()
                logger.info(f"Отправлено уведомление пользователю {user.telegram_id} об истечении подписки")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user.telegram_id}: {e}")

async def cleanup_expired_subscriptions():
    """
    Деактивирует истекшие подписки и удаляет соответствующие конфигурации с сервера
    """
    logger.info("Деактивация истекших подписок...")
    bot = get_bot()
    current_time = datetime.now(UTC)
    
    with Session() as session:
        # Получаем все активные подписки, срок действия которых истек
        expired_subscriptions = session.query(Subscription).join(User)\
            .filter(
                Subscription.is_active == True,
                Subscription.end_date < current_time
            ).all()
        
        logger.info(f"Найдено {len(expired_subscriptions)} истекших подписок")
        
        # Создаем экземпляр VPNManager для управления конфигурациями
        vpn_manager = VPNManager()
        
        for subscription in expired_subscriptions:
            user = subscription.user
            
            # Деактивируем подписку
            subscription.is_active = False
            session.commit()
            
            # Удаляем конфигурацию с сервера
            try:
                config_name = f"client_{user.telegram_id}"
                vpn_manager.remove_client_config(config_name)
                logger.info(f"Удалена конфигурация {config_name} для пользователя {user.telegram_id}")
            except Exception as e:
                logger.error(f"Ошибка при удалении конфигурации для пользователя {user.telegram_id}: {e}")
            
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    user.telegram_id,
                    "❌ Ваша подписка истекла. Доступ к VPN отключен. "
                    "Для возобновления доступа, пожалуйста, оплатите новую подписку."
                )
                logger.info(f"Отправлено уведомление пользователю {user.telegram_id} об истечении подписки")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user.telegram_id}: {e}")
        
        # Отправляем статистику администратору
        if expired_subscriptions and len(ADMIN_IDS) > 0:
            try:
                admin_id = ADMIN_IDS[0]
                await bot.send_message(
                    admin_id,
                    f"📊 Статистика: деактивировано {len(expired_subscriptions)} истекших подписок."
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке статистики администратору: {e}")

async def check_server_status():
    """
    Проверяет статус серверов и отправляет уведомление администратору в случае проблем
    """
    logger.info("Проверка статуса серверов...")
    bot = get_bot()
    
    # Создаем экземпляр VPNManager для проверки серверов
    vpn_manager = VPNManager()
    
    # Проверяем статус интерфейса VPN
    try:
        status = vpn_manager.check_interface_status()
        if not status['is_active']:
            if len(ADMIN_IDS) > 0:
                admin_id = ADMIN_IDS[0]
                await bot.send_message(
                    admin_id,
                    f"⚠️ Внимание! VPN-интерфейс не активен. Пожалуйста, проверьте сервер."
                )
            logger.warning("VPN-интерфейс не активен")
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса интерфейса VPN: {e}")
        if len(ADMIN_IDS) > 0:
            admin_id = ADMIN_IDS[0]
            await bot.send_message(
                admin_id,
                f"⚠️ Ошибка при проверке статуса сервера: {e}"
            )

async def generate_statistics():
    """
    Генерирует и отправляет статистику администратору
    """
    logger.info("Генерация статистики...")
    bot = get_bot()
    
    with Session() as session:
        # Получаем общее количество пользователей
        total_users = session.query(User).count()
        
        # Получаем количество активных подписок
        active_subscriptions = session.query(Subscription).filter(Subscription.is_active == True).count()
        
        # Получаем количество истекших подписок за последние 7 дней
        week_ago = datetime.now(UTC) - timedelta(days=7)
        recent_expired = session.query(Subscription).filter(
            Subscription.is_active == False,
            Subscription.end_date >= week_ago
        ).count()
        
        # Отправляем статистику администратору
        if len(ADMIN_IDS) > 0:
            try:
                admin_id = ADMIN_IDS[0]
                await bot.send_message(
                    admin_id,
                    f"📊 Статистика сервиса:\n"
                    f"👥 Всего пользователей: {total_users}\n"
                    f"✅ Активных подписок: {active_subscriptions}\n"
                    f"❌ Истекло за 7 дней: {recent_expired}"
                )
                logger.info("Статистика отправлена администратору")
            except Exception as e:
                logger.error(f"Ошибка при отправке статистики администратору: {e}")

async def start_scheduler():
    """
    Запускает планировщик задач с заданными интервалами
    """
    logger.info("Запуск планировщика задач...")
    
    # Проверка истекающих подписок каждые 6 часов
    scheduler.add_job(
        check_upcoming_expirations,
        trigger=IntervalTrigger(hours=6),
        id='check_upcoming_expirations',
        replace_existing=True
    )
    
    # Деактивация истекших подписок каждые 6 часов
    scheduler.add_job(
        cleanup_expired_subscriptions,
        trigger=IntervalTrigger(hours=6),
        id='cleanup_expired_subscriptions',
        replace_existing=True
    )
    
    # Проверка статуса серверов каждые 12 часов
    scheduler.add_job(
        check_server_status,
        trigger=IntervalTrigger(hours=12),
        id='check_server_status',
        replace_existing=True
    )
    
    # Генерация и отправка статистики каждые 24 часа (раз в день)
    scheduler.add_job(
        generate_statistics,
        trigger=IntervalTrigger(hours=24),
        id='generate_statistics',
        replace_existing=True
    )
    
    # Запускаем планировщик
    scheduler.start()
    
    # Бесконечный цикл, чтобы функция не завершалась
    while True:
        await asyncio.sleep(3600)  # Проверка каждый час
        
        # Проверяем, запущен ли планировщик
        if not scheduler.running:
            logger.error("Планировщик остановлен, перезапускаем...")
            scheduler.start()

if __name__ == "__main__":
    # Запускаем планировщик, если файл запущен напрямую
    asyncio.run(start_scheduler()) 