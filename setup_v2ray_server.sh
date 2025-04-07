#!/bin/bash

# Установка необходимых пакетов
apt update
apt install -y curl unzip

# Установка V2Ray
bash <(curl -L https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh)

# Генерация UUID
UUID=$(cat /proc/sys/kernel/random/uuid)

# Создание конфигурации сервера
cat > /usr/local/etc/v2ray/config.json << EOF
{
  "inbounds": [{
    "port": 443,
    "protocol": "vmess",
    "settings": {
      "clients": [
        {
          "id": "${UUID}",
          "alterId": 0
        }
      ]
    },
    "streamSettings": {
      "network": "ws",
      "wsSettings": {
        "path": "/v2ray"
      },
      "security": "none"
    }
  }],
  "outbounds": [{
    "protocol": "freedom",
    "settings": {}
  }]
}
EOF

# Запуск V2Ray
systemctl enable v2ray
systemctl restart v2ray

# Вывод информации для подключения
echo "V2Ray установлен и настроен!"
echo "UUID: ${UUID}"
echo "Порт: 443"
echo "Путь WebSocket: /v2ray"
echo "Протокол: vmess" 