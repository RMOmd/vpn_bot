#!/bin/bash

# Установка WireGuard
apt update
apt install -y wireguard

# Создание директории для конфигураций
mkdir -p /etc/wireguard

# Генерация ключей
wg genkey | tee /etc/wireguard/private.key | wg pubkey > /etc/wireguard/public.key
chmod 600 /etc/wireguard/private.key

# Создание конфигурации сервера
cat > /etc/wireguard/wg0.conf << EOF
[Interface]
PrivateKey = $(cat /etc/wireguard/private.key)
Address = 10.0.0.1/24
ListenPort = 51820
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
EOF

# Включение IP forwarding
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Запуск WireGuard
systemctl enable wg-quick@wg0
systemctl start wg-quick@wg0

# Вывод публичного ключа
echo "Публичный ключ сервера:"
cat /etc/wireguard/public.key 