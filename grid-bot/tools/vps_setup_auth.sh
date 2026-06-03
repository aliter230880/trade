#!/bin/bash
# Настройка Basic Auth для Caddy
set -e

USER="dim230880"
PASS="Dim_230880"

# Найти caddy
CADDY=$(command -v caddy || echo /usr/bin/caddy)
echo "caddy: $CADDY"
ls -la "$CADDY" 2>/dev/null || { echo "caddy не найден"; exit 1; }

# Сгенерировать bcrypt хэш
HASH=$($CADDY hash-password --plaintext "$PASS")
echo "hash: $HASH"

# Записать новый Caddyfile
cat > /etc/caddy/Caddyfile <<CADDYEOF
trade.aliterra.space {
	encode gzip
	basicauth * {
		${USER} ${HASH}
	}
	reverse_proxy 127.0.0.1:8000
}

http://168.222.143.103 {
	basicauth * {
		${USER} ${HASH}
	}
	reverse_proxy 127.0.0.1:8000
}
CADDYEOF

# Валидация и reload
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
echo "OK, basicauth включён для пользователя $USER"
