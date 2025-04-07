import os
import logging
import aiohttp
from datetime import datetime, UTC
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class CryptoPay:
    def __init__(self, token: str, testnet: bool = False):
        self.token = token
        self.base_url = "https://testnet-pay.crypt.bot" if testnet else "https://pay.crypt.bot"
        self.session = None

    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Выполняет запрос к API Crypto Pay"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "Crypto-Pay-API-Token": self.token
        }

        url = f"{self.base_url}/api/{endpoint}"
        
        try:
            if method == "GET":
                async with self.session.get(url, params=params, headers=headers) as response:
                    data = await response.json()
            else:  # POST
                async with self.session.post(url, json=params, headers=headers) as response:
                    data = await response.json()
                    
            if not data.get("ok"):
                logger.error(f"Ошибка Crypto Pay API: {data.get('error')}")
                return None
            return data.get("result")
        except Exception as e:
            logger.error(f"Ошибка при запросе к Crypto Pay API: {e}")
            return None

    async def create_invoice(
        self,
        amount: float,
        asset: str = "USDT",
        description: Optional[str] = None,
        paid_btn_name: Optional[str] = None,
        paid_btn_url: Optional[str] = None,
        payload: Optional[str] = None,
        allow_comments: bool = True,
        allow_anonymous: bool = True,
        expires_in: Optional[int] = None
    ) -> Optional[Dict]:
        """Создает новый счет для оплаты"""
        params = {
            "asset": asset,
            "amount": str(amount),
            "allow_comments": "true" if allow_comments else "false",
            "allow_anonymous": "true" if allow_anonymous else "false"
        }

        if description:
            params["description"] = description
        if paid_btn_name:
            params["paid_btn_name"] = paid_btn_name
        if paid_btn_url:
            params["paid_btn_url"] = paid_btn_url
        if payload:
            params["payload"] = payload
        if expires_in:
            params["expires_in"] = str(expires_in)

        return await self._make_request("POST", "createInvoice", params)

    async def get_invoice(self, invoice_id: int) -> Optional[Dict]:
        """Получает информацию о счете"""
        return await self._make_request("GET", "getInvoices", {"invoice_ids": str(invoice_id)})

    async def get_balance(self) -> Optional[Dict]:
        """Получает баланс аккаунта"""
        return await self._make_request("GET", "getBalance")

    async def get_exchange_rates(self) -> Optional[Dict]:
        """Получает текущие курсы обмена"""
        return await self._make_request("GET", "getExchangeRates")

    async def close(self):
        """Закрывает сессию"""
        if self.session:
            await self.session.close()
            self.session = None 