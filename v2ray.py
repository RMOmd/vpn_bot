import os
import json
import uuid
import base64
from datetime import datetime, UTC, timedelta
from typing import Optional, Tuple
import qrcode
from io import BytesIO
from aiogram.types import FSInputFile

class V2RayManager:
    def __init__(self, server_host: str, server_port: int):
        self.server_host = server_host
        self.server_port = server_port
        
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
        
    async def create_and_send_config(self, user_id: int, bot, expiry_days: int = 7) -> Tuple[bool, Optional[str]]:
        """Создание и отправка конфигурации пользователю
        
        Args:
            user_id: ID пользователя
            bot: Объект бота для отправки сообщений
            expiry_days: Срок действия в днях
            
        Returns:
            Tuple[bool, Optional[str]]: Успех операции и UUID клиента
        """
        try:
            # Генерируем конфигурацию
            config, client_uuid = self.generate_client_config(user_id, expiry_days)
            
            # Сохраняем конфигурацию
            config_path = self.save_client_config(user_id, config)
            
            # Генерируем vmess ссылку и QR код
            vmess_link = self.generate_vmess_link(config)
            qr_path = self.generate_qr_code(vmess_link)
            
            # Отправляем информацию пользователю
            await bot.send_message(
                user_id,
                "📱 Для подключения VPN выполните следующие шаги:\n\n"
                "1. Установите приложение V2RayNG:\n"
                "• Android: https://play.google.com/store/apps/details?id=com.v2ray.ang\n"
                "• iOS: https://apps.apple.com/us/app/v2box-v2ray-client/id6446814690\n\n"
                "2. Отсканируйте QR код ниже или импортируйте конфигурацию из файла\n\n"
                "3. Нажмите кнопку подключения в приложении\n\n"
                "🔗 Ссылка для импорта:\n"
                f"`{vmess_link}`",
                parse_mode="Markdown"
            )
            
            # Отправляем QR код
            qr_file = FSInputFile(qr_path)
            await bot.send_photo(user_id, qr_file, caption="QR код для быстрого импорта")
            
            # Отправляем файл конфигурации
            config_file = FSInputFile(config_path)
            await bot.send_document(
                user_id,
                config_file,
                caption="Файл конфигурации V2Ray"
            )
            
            # Удаляем временный файл QR кода
            os.remove(qr_path)
            
            return True, client_uuid
        except Exception as e:
            print(f"Ошибка при создании конфигурации: {e}")
            return False, None
            
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