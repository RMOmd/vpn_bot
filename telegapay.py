import os
import logging
import aiohttp
from datetime import datetime, UTC
from typing import Optional, Dict, Any, List
from config import TELEGAPAY_API_KEY, TELEGAPAY_BASE_URL

logger = logging.getLogger(__name__)

class TelegaPayAPI:
    def __init__(self, api_key: str, base_url: str):
        """
        Инициализация API TelegaPay
        
        Args:
            api_key: API-ключ
            base_url: Базовый URL API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = None
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Выполняет запрос к API TelegaPay
        
        Args:
            method: HTTP метод (POST, GET)
            endpoint: Эндпоинт API
            data: Данные для отправки
            
        Returns:
            Dict: Ответ от API
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/api/v1/{endpoint}"
        
        try:
            if method == "GET":
                async with self.session.get(url, headers=headers) as response:
                    response_data = await response.json()
            else:  # POST
                async with self.session.post(url, json=data, headers=headers) as response:
                    response_data = await response.json()
            
            if not response_data.get("success", False):
                logger.error(f"Ошибка TelegaPay API: {response_data.get('error')}")
                return {"success": False, "error": response_data.get("error", "Неизвестная ошибка")}
            
            return response_data
        except Exception as e:
            logger.error(f"Ошибка при запросе к TelegaPay API: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_payment_methods(self, amount: float, currency: str = "RUB") -> List[str]:
        """
        Получает доступные методы оплаты
        
        Args:
            amount: Сумма платежа
            currency: Код валюты
            
        Returns:
            List[str]: Список доступных методов оплаты
        """
        data = {
            "amount": amount,
            "currency": currency
        }
        
        response = await self._make_request("POST", "get_methods", data)
        
        if response.get("success", False):
            return response.get("methods", [])
        return []
    
    async def get_requisites(self, amount: float, currency: str, method: str, order_id: str = None, user_id: str = None) -> Dict:
        """
        Получает реквизиты для оплаты
        
        Args:
            amount: Сумма платежа
            currency: Код валюты
            method: Метод оплаты
            order_id: Внешний ID заказа
            user_id: ID пользователя
            
        Returns:
            Dict: Реквизиты для оплаты
        """
        data = {
            "amount": amount,
            "currency": currency,
            "method": method
        }
        
        if order_id:
            data["order_id"] = order_id
        
        if user_id:
            data["user_id"] = str(user_id)
        
        return await self._make_request("POST", "get_requisites", data)
    
    async def create_paylink(self, amount: float, currency: str, payment_method: str = None, 
                           description: str = None, return_url: str = None, user_id: str = None) -> Dict:
        """
        Создает платежную ссылку
        
        Args:
            amount: Сумма платежа
            currency: Код валюты
            payment_method: Метод оплаты
            description: Описание платежа
            return_url: URL для перенаправления
            user_id: ID пользователя
            
        Returns:
            Dict: Информация о созданной платежной ссылке
        """
        data = {
            "amount": amount,
            "currency": currency
        }
        
        if payment_method:
            data["payment_method"] = payment_method
        
        if description:
            data["description"] = description
        
        if return_url:
            data["return_url"] = return_url
        
        if user_id:
            data["user_id"] = str(user_id)
        
        return await self._make_request("POST", "create_paylink", data)
    
    async def confirm_payment(self, transaction_id: str) -> Dict:
        """
        Подтверждает оплату
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            Dict: Результат подтверждения
        """
        data = {
            "transaction_id": transaction_id
        }
        
        return await self._make_request("POST", "confirm_payment", data)
    
    async def check_status(self, transaction_id: str) -> Dict:
        """
        Проверяет статус транзакции
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            Dict: Статус транзакции
        """
        data = {
            "transaction_id": transaction_id
        }
        
        return await self._make_request("POST", "check_status", data)
    
    async def cancel_payment(self, transaction_id: str) -> Dict:
        """
        Отменяет платеж
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            Dict: Результат отмены
        """
        data = {
            "transaction_id": transaction_id
        }
        
        return await self._make_request("POST", "cancel_payment", data)
    
    async def close(self):
        """Закрывает сессию"""
        if self.session:
            await self.session.close()
            self.session = None


# Создаем глобальный экземпляр для использования в других модулях
telegapay_api = TelegaPayAPI(
    api_key=TELEGAPAY_API_KEY,
    base_url=TELEGAPAY_BASE_URL
) 