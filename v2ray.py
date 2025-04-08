import os
import json
import uuid
import base64
from datetime import datetime, UTC, timedelta
from typing import Optional, Tuple
import qrcode
from io import BytesIO
from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy.orm import Session
from database import Subscription, Session as DBSession
from log import logger

class V2RayManager:
    """Менеджер для работы с V2Ray"""
    
    def __init__(self):
        self.config_dir = "configs"
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
    
    async def create_and_send_config(self, user_id: int, bot: Bot) -> Tuple[bool, Optional[str]]:
        """Создать и отправить конфигурацию пользователю"""
        session = DBSession()
        try:
            # Получаем активную подписку пользователя
            subscription = session.query(Subscription).filter_by(
                user_id=user_id,
                is_active=True
            ).first()
            
            if not subscription:
                logger.error(f"Нет активной подписки для пользователя {user_id}")
                return False, None
                
            if not subscription.server:
                logger.error(f"Нет сервера для подписки {subscription.id}")
                return False, None
            
            # Генерируем UUID для пользователя
            client_uuid = str(uuid.uuid4())
            
            # Создаем конфигурацию
            config = {
                "v": "2",
                "ps": f"{subscription.server.name} - {subscription.country.name}",
                "add": subscription.server.host,
                "port": subscription.server.port,
                "id": client_uuid,
                "aid": subscription.server.alter_id,
                "net": subscription.server.network,
                "type": subscription.server.type,
                "host": subscription.server.hostname or subscription.server.host,
                "path": subscription.server.path,
                "tls": "tls" if subscription.server.tls else "none",
                "sni": subscription.server.hostname or subscription.server.host if subscription.server.tls else ""
            }
            
            # Кодируем конфигурацию в base64
            config_str = json.dumps(config)
            config_b64 = base64.b64encode(config_str.encode()).decode()
            vmess_url = f"vmess://{config_b64}"
            
            # Создаем QR-код
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(vmess_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Сохраняем QR-код
            qr_path = os.path.join(self.config_dir, f"{user_id}_qr.png")
            qr_img.save(qr_path)
            
            # Формируем текст сообщения с подробной информацией
            config_text = (
                f"✅ Ваша конфигурация V2Ray:\n\n"
                f"🌍 Сервер: {subscription.server.name}\n"
                f"🏳️ Страна: {subscription.country.name}\n"
                f"🔌 Протокол: {subscription.server.network}\n"
                f"🔒 TLS: {'Включен' if subscription.server.tls else 'Отключен'}\n\n"
                f"Для подключения используйте:\n"
                f"1️⃣ QR-код (отправлен следующим сообщением)\n"
                f"2️⃣ Ссылку для импорта:\n"
                f"```\n{vmess_url}\n```"
            )
            
            # Отправляем сообщение пользователю
            await bot.send_message(
                user_id,
                config_text,
                parse_mode="Markdown"
            )
            
            # Отправляем QR-код
            await bot.send_photo(
                user_id,
                photo=FSInputFile(qr_path),
                caption="QR-код для быстрого импорта конфигурации"
            )
            
            # Удаляем временный файл QR-кода
            try:
                os.remove(qr_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл QR-кода: {e}")
            
            return True, client_uuid
            
        except Exception as e:
            logger.error(f"Ошибка при создании конфигурации: {e}")
            return False, None
        finally:
            session.close()

    def generate_client_config(self, user_id: int, expiry_days: int = 7) -> Tuple[dict, str]:
        """Генерация конфигурации клиента
        
        Args:
            user_id: ID пользователя
            expiry_days: Срок действия в днях
            
        Returns:
            Tuple[dict, str]: Конфигурация и UUID клиента
        """
        client_uuid = str(uuid.uuid4())
        expiry_date = datetime.now(UTC) + timedelta(days=expiry_days)
        
        config = {
            "v": "2",
            "ps": f"VPN Bot - {expiry_date.strftime('%d.%m.%Y')}",
            "add": self.server_host,
            "port": str(self.server_port),
            "id": client_uuid,
            "aid": "0",
            "net": "ws",
            "type": "none",
            "host": self.server_host,
            "path": "/ws",
            "tls": "tls",
            "sni": self.server_host,
            "expiry": expiry_date.isoformat()
        }
        
        return config, client_uuid
        
    def save_client_config(self, user_id: int, config: dict) -> str:
        """Сохранение конфигурации клиента
        
        Args:
            user_id: ID пользователя
            config: Конфигурация для сохранения
            
        Returns:
            str: Путь к сохраненному файлу
        """
        # Создаем директорию для пользователя
        user_dir = os.path.join("v2ray_configs", str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        # Сохраняем конфигурацию
        config_path = os.path.join(user_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
            
        return config_path
        
    def generate_vmess_link(self, config: dict) -> str:
        """Генерация ссылки vmess:// для быстрого импорта"""
        # Кодируем конфигурацию в base64
        config_str = json.dumps(config)
        config_bytes = config_str.encode('utf-8')
        config_b64 = base64.b64encode(config_bytes).decode('utf-8')
        
        return f"vmess://{config_b64}"
        
    def generate_qr_code(self, vmess_link: str) -> str:
        """Генерация QR кода для быстрого импорта
        
        Args:
            vmess_link: Ссылка vmess://
            
        Returns:
            str: Путь к файлу с QR кодом
        """
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(vmess_link)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Создаем директорию для временных файлов
        os.makedirs("temp", exist_ok=True)
        qr_path = os.path.join("temp", f"qr_{uuid.uuid4()}.png")
        img.save(qr_path)
        
        return qr_path
        
    def check_config_expiry(self, config: dict) -> bool:
        """Проверка срока действия конфигурации
        
        Args:
            config: Конфигурация для проверки
            
        Returns:
            bool: True если конфиг действующий, False если истек срок
        """
        if "expiry" not in config:
            return True  # Если нет срока действия, считаем конфиг бессрочным
            
        expiry_date = datetime.fromisoformat(config["expiry"])
        return datetime.now(UTC) < expiry_date

    def load_client_config(self, user_id: int) -> Optional[dict]:
        """Загрузка конфигурации пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Optional[dict]: Конфигурация пользователя или None, если конфиг не найден
        """
        config_path = os.path.join("v2ray_configs", str(user_id), "config.json")
        if not os.path.exists(config_path):
            return None
            
        with open(config_path, "r") as f:
            config = json.load(f)
            
        # Проверяем срок действия
        if not self.check_config_expiry(config):
            return None
            
        return config 