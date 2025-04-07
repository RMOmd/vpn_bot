import os
import uuid
from datetime import datetime, timedelta, UTC
from aiogram import types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import Session, User, Subscription
from config import PAYMENT_PROVIDER_TOKEN

class PaymentManager:
    def __init__(self):
        self.payments = {}
        
        # Стоимость в звездах для разных периодов
        self.star_prices = {
            1: 50,    # 1 месяц - 50 звезд
            3: 140,   # 3 месяца - 140 звезд
            6: 260,   # 6 месяцев - 260 звезд
            12: 480,  # 12 месяцев - 480 звезд
        }

    def get_star_price(self, duration_months: int) -> int:
        """Получить стоимость подписки в звездах"""
        return self.star_prices.get(duration_months, 0)

    async def create_payment(self, user_id: int, amount: float, duration_months: int) -> dict:
        """Создает обычный платеж через Telegram Payments
        
        Args:
            user_id: ID пользователя
            amount: Сумма платежа
            duration_months: Длительность подписки в месяцах
            
        Returns:
            dict: Данные для создания инвойса
        """
        if not PAYMENT_PROVIDER_TOKEN:
            raise ValueError("Не задан токен платежного провайдера")
            
        payment_id = f"money_{user_id}_{datetime.now(UTC).timestamp()}"
        
        # Сохраняем информацию о платеже
        self.payments[payment_id] = {
            "user_id": user_id,
            "amount": amount,
            "duration": duration_months,
            "created_at": datetime.now(UTC),
            "status": "pending",
            "type": "money"
        }
        
        # Формируем данные для инвойса
        return {
            "title": "Подписка на VPN",
            "description": f"Подписка на {duration_months} {'месяц' if duration_months == 1 else 'месяцев'}",
            "payload": payment_id,
            "provider_token": PAYMENT_PROVIDER_TOKEN,
            "currency": "RUB",
            "prices": [{"label": "Подписка", "amount": int(amount * 100)}],  # Сумма в копейках
            "start_parameter": payment_id
        }

    async def create_star_payment(self, user_id: int, duration_months: int) -> dict:
        """Создает платеж звездами
        
        Returns:
            dict: Информация о платеже
        """
        stars_amount = self.get_star_price(duration_months)
        payment_id = f"stars_{user_id}_{datetime.now(UTC).timestamp()}"
        
        # Сохраняем информацию о платеже
        self.payments[payment_id] = {
            "user_id": user_id,
            "stars": stars_amount,
            "duration": duration_months,
            "created_at": datetime.now(UTC),
            "status": "pending",
            "type": "stars"
        }
        
        return {
            "payment_id": payment_id,
            "stars": stars_amount,
            "duration": duration_months
        }

    async def process_star_payment(self, payment_id: str, from_user: types.User, bot: Bot) -> bool:
        """Обработка оплаты звездами"""
        payment_info = self.payments.get(payment_id)
        if not payment_info or payment_info["status"] != "pending":
            return False
            
        # Проверяем, что платеж от того же пользователя
        if payment_info["user_id"] != from_user.id:
            return False

        try:
            # Генерируем ссылку для оплаты звездами
            payment_info["payment_link"] = f"tg://premium/gift?quantity={payment_info['stars']}"
            return True
            
        except Exception as e:
            print(f"Ошибка при создании ссылки на оплату звездами: {e}")
            return False

    async def confirm_star_payment(self, payment_id: str, from_user: types.User) -> bool:
        """Подтверждение оплаты звездами"""
        payment_info = self.payments.get(payment_id)
        if not payment_info or payment_info["status"] != "pending":
            return False

        # Обновляем статус платежа
        payment_info["status"] = "paid"
        
        # Создаем подписку
        session = Session()
        user = session.query(User).filter_by(telegram_id=from_user.id).first()
        
        if user:
            # Деактивируем текущую подписку, если есть
            current_sub = user.get_active_subscription()
            if current_sub:
                current_sub.is_active = False
            
            # Создаем новую подписку
            subscription = Subscription(
                user_id=user.telegram_id,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30 * payment_info["duration"]),
                price=0,  # Цена 0, так как оплата звездами
                is_trial=False,
                is_active=True,
                payment_type="stars",
                stars_paid=payment_info["stars"]
            )
            session.add(subscription)
            user.is_active = True
            session.commit()
        
        session.close()
        return True

    def get_payment_info(self, payment_id: str) -> dict:
        """Получает информацию о платеже"""
        return self.payments.get(payment_id) 