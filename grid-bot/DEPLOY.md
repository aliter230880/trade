# Деплой на VPS (cloud.reg.ru, Aeza, Timeweb или любой Linux)

## 1. Что нужно

- VPS с Ubuntu 22.04 или 24.04 (1 vCPU / 1 GB RAM минимум)
- SSH-доступ
- Свободный 80/443 или любой другой порт (по умолчанию 8000)

## 2. Подключиться по SSH

С твоего ПК (cmd):

```cmd
ssh root@<IP_сервера>
```

## 3. Установить Docker (один раз)

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
```

## 4. Загрузить код на сервер

Вариант A — git (если положишь проект на GitHub):

```bash
git clone https://github.com/TWOJ-USER/grid-bot.git
cd grid-bot
```

Вариант B — scp с локального ПК (без git):

С локального компа:

```cmd
scp -r e:\AI\AI_folder\grid-bot root@<IP>:/opt/
```

На сервере:

```bash
cd /opt/grid-bot
```

## 5. Настроить .env

```bash
cp .env.example .env
nano .env
```

Заполнить:

```
ENCRYPTION_KEY=<сгенерируй: openssl rand -base64 32>
TELEGRAM_BOT_TOKEN=<если нужен>
TELEGRAM_CHAT_ID=<если нужен>
```

## 6. Запустить

```bash
docker compose up -d --build
```

Проверить:

```bash
curl http://localhost:8000/api/health
docker compose logs -f
```

## 7. Открыть наружу

### Вариант A: по IP

`http://<IP_сервера>:8000` — работает сразу. Минус: HTTP без шифрования, ключи API уйдут в открытом виде.

### Вариант B: поддомен с HTTPS через Caddy (рекомендую)

На сервере:

```bash
apt install -y caddy
cat > /etc/caddy/Caddyfile <<'EOF'
bot.aliterra.space {
    reverse_proxy localhost:8000
}
EOF
systemctl reload caddy
```

В панели reg.ru DNS добавь A-запись `bot.aliterra.space → <IP_сервера>`. Через 5 минут HTTPS-сертификат от Let's Encrypt получится автоматом.

### Вариант C: Cloudflare tunnel

Если не хочешь открывать порт наружу — `cloudflared tunnel` через твой Cloudflare-аккаунт. Аналогично текущей схеме `start_unity_bridge.cmd`.

## 8. Обновления

```bash
cd /opt/grid-bot
git pull        # или новый scp
docker compose up -d --build
```

## 9. Бэкап

Главное — папка `data/` с SQLite. На сервере:

```bash
tar czf grid-bot-backup-$(date +%F).tar.gz /opt/grid-bot/data /opt/grid-bot/.env
```

## 10. Безопасность

- Никогда не клади `.env` в git (есть в `.gitignore`).
- На VPS сделай firewall:
  ```bash
  ufw allow 22
  ufw allow 80
  ufw allow 443
  ufw enable
  ```
  Порт 8000 наружу не открывай если используешь Caddy/Cloudflare.
- В Bybit API IP-restriction: после деплоя укажи в Bybit IP сервера, чтобы ключи работали только с него.
