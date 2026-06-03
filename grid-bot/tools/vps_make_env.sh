#!/bin/bash
# Генерирует .env на сервере со свежим ENCRYPTION_KEY
ENC_KEY=$(openssl rand -base64 32 | tr -d '/+=' | head -c 40)
cat > /opt/grid-bot/.env <<ENVEOF
APP_HOST=0.0.0.0
APP_PORT=8000
DEFAULT_EXCHANGE=bybit
DEFAULT_TESTNET=false
TELEGRAM_BOT_TOKEN=8595643771:AAFFVxyzReQO5-LLO5m9ZA23sbFTJouU5io
TELEGRAM_CHAT_ID=789368186
ENCRYPTION_KEY=${ENC_KEY}
ENVEOF
chmod 600 /opt/grid-bot/.env
echo "OK, ENCRYPTION_KEY=${ENC_KEY}"
