import os
import json
import uuid
from aiogram.types import FSInputFile
import base64

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

    def save_client_config(self, user_id: int, config: dict) -> str:
        """Сохранение конфигурации в файл"""
        filename = f"{self.config_dir}/client_{user_id}.json"
        
        # Создаем полную конфигурацию v2ray
        full_config = {
            "inbounds": [{
                "port": 1080,
                "protocol": "socks",
                "settings": {
                    "auth": "noauth",
                    "udp": True
                }
            }],
            "outbounds": [{
                "protocol": "vmess",
                "settings": {
                    "vnext": [{
                        "address": config["add"],
                        "port": config["port"],
                        "users": [{
                            "id": config["id"],
                            "alterId": config["aid"]
                        }]
                    }]
                },
                "streamSettings": {
                    "network": config["net"],
                    "wsSettings": {
                        "path": config["path"]
                    }
                }
            }]
        }
        
        with open(filename, 'w') as f:
            json.dump(full_config, f, indent=2)
        
        return filename

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