import os
import uuid
from datetime import datetime, timedelta, UTC
from aiogram import types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import Session, User, Subscription
from config import PAYMENT_PROVIDER_TOKEN
from telegapay import telegapay_api
import hashlib
import aiohttp
import logging

logger = logging.getLogger(__name__)

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

        # Стоимость в рублях для разных периодов
        self.rub_prices = {
            1: 149,    # 1 месяц - 149 рублей
            3: 399,    # 3 месяца - 399 рублей
            6: 699,    # 6 месяцев - 699 рублей
            12: 1299,  # 12 месяцев - 1299 рублей
        }

    def get_star_price(self, duration_months: int) -> int:
        """Получить стоимость подписки в звездах"""
        return self.star_prices.get(duration_months, 0)

    def get_rub_price(self, duration_months: int) -> int:
        """Получить стоимость подписки в рублях"""
        return self.rub_prices.get(duration_months, 0)

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
        """Создает платеж звездами"""
        stars_amount = self.get_star_price(duration_months)
        if not stars_amount:
            logger.error(f"Не найдена цена для периода {duration_months} месяцев")
            return None
            
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
        
        logger.info(f"Создан платеж звездами: {payment_id} для пользователя {user_id}")
        return {
            "payment_id": payment_id,
            "stars": stars_amount,
            "duration": duration_months
        }

    async def create_telegapay_payment(self, user_id: int, duration_months: int, payment_method: str = None) -> str:
        """Создает платеж через TelegaPay
        
        Args:
            user_id: ID пользователя
            duration_months: Длительность подписки в месяцах
            payment_method: Метод оплаты (BANK_SBER, SBP, QR_CODE и т.д.)
            
        Returns:
            str: URL для оплаты
        """
        amount = self.get_rub_price(duration_months)
        order_id = str(uuid.uuid4())[:8]  # Уникальный идентификатор заказа
        
        # Описание платежа
        description = f"Подписка VPN на {duration_months} мес."

        # ВРЕМЕННОЕ РЕШЕНИЕ для тестирования без реального TelegaPay API
        transaction_id = f"test_{uuid.uuid4()}"
        payment_url = "https://example.com/test_payment"  # Тестовая ссылка
        
        # Сохраняем информацию о платеже
        payment_id = f"tpay_{user_id}_{transaction_id}"
        self.payments[payment_id] = {
            "user_id": user_id,
            "amount": amount,
            "duration": duration_months,
            "created_at": datetime.now(UTC),
            "status": "pending",
            "type": "telegapay",
            "payment_method": payment_method,
            "transaction_id": transaction_id
        }
        
        logger.info(f"Создан тестовый платеж TelegaPay: {payment_id} для пользователя {user_id}, метод: {payment_method}")
        return payment_url

    async def process_star_payment(self, payment_id: str, from_user: types.User, bot: Bot) -> bool:
        """Обработка оплаты звездами"""
        payment_info = self.payments.get(payment_id)
        if not payment_info or payment_info["status"] != "pending":
            logger.error(f"Платеж {payment_id} не найден или не в статусе pending")
            return False
            
        # Проверяем, что платеж от того же пользователя
        if payment_info["user_id"] != from_user.id:
            logger.error(f"Платеж {payment_id} принадлежит другому пользователю")
            return False

        try:
            # Проверяем наличие необходимых данных
            if "stars" not in payment_info:
                logger.error(f"Отсутствует количество звезд в платеже {payment_id}")
                return False
                
            # Создаем ссылку для оплаты звездами
            payment_info["payment_link"] = f"tg://premium/gift?quantity={payment_info['stars']}"
            logger.info(f"Создана ссылка для оплаты звездами: {payment_info['payment_link']}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при создании ссылки на оплату звездами: {e}")
            return False
            
    async def check_telegapay_status(self, payment_id: str) -> bool:
        """Проверка статуса платежа TelegaPay"""
        payment_info = self.payments.get(payment_id)
        if not payment_info or payment_info["type"] != "telegapay":
            logger.error(f"Платеж {payment_id} не найден или не является платежом TelegaPay")
            return False
            
        transaction_id = payment_info.get("transaction_id")
        if not transaction_id:
            logger.error(f"Отсутствует ID транзакции для платежа {payment_id}")
            return False
            
        # ВРЕМЕННОЕ РЕШЕНИЕ для тестирования
        # Всегда возвращаем успешный статус
        payment_info["status"] = "paid"
        logger.info(f"Тестовый платеж TelegaPay {payment_id} успешно оплачен")
        return True

    async def confirm_payment(self, payment_id: str, from_user: types.User) -> bool:
        """Подтверждение любого типа оплаты"""
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
                price=payment_info.get("amount", 0),
                is_trial=False,
                is_active=True,
                payment_type=payment_info["type"],
                stars_paid=payment_info.get("stars", 0)
            )
            session.add(subscription)
            user.is_active = True
            session.commit()
        
        session.close()
        return True

    def get_payment_info(self, payment_id: str) -> dict:
        """Получает информацию о платеже"""
        return self.payments.get(payment_id) 