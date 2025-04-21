from config import ADMIN_IDS, BOT_TOKEN
from aiogram import Bot

async def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def get_bot():
    """Возвращает экземпляр бота"""
    return Bot(token=BOT_TOKEN) 