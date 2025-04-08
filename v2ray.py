import os
import json
import uuid
from aiogram.types import FSInputFile
import base64
from datetime import datetime, UTC, timedelta
from typing import Optional

class V2RayManager:
    def __init__(self, server_host: str, server_port: int = 443):
        self.server_host = server_host
        self.server_port = server_port
        self.config_dir = "v2ray_configs"
        
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

    def generate_client_config(self, user_id: int) -> dict:
        """Генерация конфигурации для клиента"""
        client_uuid = str(uuid.uuid4())
        
        config = {
            "v": "2",
            "ps": f"VPN Bot Client {user_id}",
            "add": self.server_host,
            "port": self.server_port,
            "id": client_uuid,
            "aid": 0,
            "net": "ws",
            "type": "none",
            "host": "",
            "path": "/v2ray",
            "tls": ""
        }
        
        return config, client_uuid

    def generate_temporary_config(self, user_id: int, duration_days: int) -> tuple[dict, str, datetime]:
        """Генерация временной конфигурации с ограниченным сроком действия
        
        Args:
            user_id: ID пользователя
            duration_days: Длительность действия конфига в днях
            
        Returns:
            tuple: (config, client_uuid, expiry_date)
        """
        config, client_uuid = self.generate_client_config(user_id)
        expiry_date = datetime.now(UTC) + timedelta(days=duration_days)
        
        # Добавляем информацию о сроке действия в конфиг
        config["expiry"] = expiry_date.isoformat()
        
        return config, client_uuid, expiry_date

    def save_client_config(self, user_id: int, config: dict) -> str:
        """Сохранение конфигурации в файл"""
        config_dir = os.path.join("v2ray_configs", str(user_id))
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = os.path.join(config_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            
        return config_path

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

    def generate_vmess_link(self, config: dict) -> str:
        """Генерация ссылки vmess:// для быстрого импорта"""
        config_str = json.dumps(config)
        encoded = base64.b64encode(config_str.encode()).decode()
        return f"vmess://{encoded}"

    async def create_and_send_config(self, user_id: int, bot):
        """Создание и отправка конфигурации пользователю"""
        try:
            # Генерируем конфигурацию
            config, client_uuid = self.generate_client_config(user_id)
            
            # Сохраняем полную конфигурацию
            config_path = self.save_client_config(user_id, config)
            
            # Генерируем vmess ссылку
            vmess_link = self.generate_vmess_link(config)
            
            # Отправляем конфигурацию и ссылку пользователю
            await bot.send_document(
                chat_id=user_id,
                document=FSInputFile(config_path),
                caption=f"Ваша конфигурация V2Ray.\n\nДля быстрого импорта используйте эту ссылку:\n`{vmess_link}`",
                parse_mode="Markdown"
            )
            
            return True, client_uuid
        except Exception as e:
            print(f"Ошибка при создании конфигурации: {e}")
            return False, None 