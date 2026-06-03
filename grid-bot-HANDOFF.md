# Grid Trading Bot — HANDOFF

Стартовая точка для нового чата. Всё что нужно для продолжения работы по проекту.
Полная летопись разработки — в этом же файле ниже, разделом "История".

**Дата последнего обновления**: 24 мая 2026, 13:15 МСК. После полного деплоя на VPS.

---

## TL;DR

Grid-trading бот на Python + FastAPI с веб-мордой. Развёрнут на VPS cloud.reg.ru,
доступен по `https://trade.aliterra.space`. Работает на Bybit Mainnet с реальным
капиталом **$52.76 USDT**. Первый бот **запущен 24.05.2026 13:12 МСК** на
**DOGE/USDT** с 8 уровнями grid и размером ордера $5.

**Текущее состояние**: ✅ полностью в продакшене.
- Bot #1 DOGE/USDT, 8 уровней, диапазон $0.09–$0.12
- Все 8 ордеров стоят на Bybit (open_orders: 8)
- Telegram-уведомления работают через IP-fallback (обход блокировки РКН)
- HTTPS-сертификат от Let's Encrypt
- Auto-restart контейнера

**Следующий шаг**: ждём первые сделки (DOGE должен пересечь уровни).
Параллельно по roadmap'у: смена Telegram-токена → funding farmer → ML-фильтр.

---

## Доступы

### Сервер
- **IP**: `168.222.143.103`
- **Hostname**: `cv7358071.novalocal`
- **OS**: Ubuntu 24.04.3 LTS (kernel 6.8)
- **Тариф**: HP C1-M1-D10 (1 vCPU / 1 GB RAM / 10 GB SSD)
- **Регион**: Москва-2
- **Резервные копии**: включены
- **Цена**: ~300₽/мес (~$3.5)
- **SSH**: `root@168.222.143.103`, пароль `ShAVSu2ZM57U7jFB`
  - ⚠️ **Заменить на SSH-ключ**, отключить парольный вход (TODO)
  - SSH host key fingerprint: `SHA256:kTPrb01XLPu73Wwm45TIweNoMja2WroQnMRDblRi4e8`

### URL
- **Production**: https://trade.aliterra.space (HTTPS, Let's Encrypt)
- **Бэкап по IP**: http://168.222.143.103 (без HTTPS, но тоже под basic auth)
- **Локально на VPS**: http://localhost:8000 (без auth, только с самого VPS)
- **🔒 Basic Auth**:
  - Логин: `dim230880`
  - Пароль: `Dim_230880` (засветился в чате — рекомендуется сменить)
  - Реализация: Caddy `basic_auth` директива в `/etc/caddy/Caddyfile`

### ⚠️ ВПС НЕ МОЙ — там есть ДРУГИЕ ПРОЕКТЫ ПОЛЬЗОВАТЕЛЯ

VPS используется не только под grid-bot. Перед любыми системными
действиями (apt-get, остановка сервисов, чистка диска, перезагрузка)
**обязательно проверять что не задеваем эти соседние проекты**.

#### Соседние сервисы

| Что | Где | Порт |
|---|---|---|
| **grid-bot** (наш) | docker `/opt/grid-bot/` | :8000 |
| **web3gram-relay** | docker `/opt/web3gram-relay/` | 127.0.0.1:8765 |
| **cp-qdrant** (Qdrant для character-platform) | docker | 127.0.0.1:6333 |
| **character-platform** API (uvicorn) | прямо на хосте | 127.0.0.1:8001 |
| **character-platform** SPA (статика) | `/opt/character-platform/web` | через Caddy |
| **autoposter** (Node, через PM2) | `/root/autoposter` | :3000 |
| **PHP 8.3 FPM** для web3.aliterra.space | системный | unix socket |
| **piper** (вероятно TTS) | `/opt/piper/` | — |

#### Caddy обслуживает 3 домена

`/etc/caddy/Caddyfile` содержит блоки для:
- **trade.aliterra.space** → grid-bot:8000 (наш, с basic_auth)
- **web3.aliterra.space** → web3gram-relay:8765 + PHP-FPM + статика
- **ai.aliterra.space** → uvicorn:8001 + SPA character-platform

⚠️ **Никогда не перезаписывать Caddyfile целиком** — там 3 проекта.
Только править блок trade.aliterra.space или добавлять новые.

#### Что я сделал и почему это безопасно

- `systemctl disable nginx` + `systemctl stop nginx` — nginx не использовался
  (sites-enabled пустой, кроме дефолта от установки), Caddy полностью замещает
  его для всех 3 доменов. Если nginx понадобится — `systemctl enable nginx`
  обратно.
- При ребутах VPS nginx раньше Caddy занимал порт 80, Caddy не стартовал.
  Disable nginx это исправило.

#### Что важно НЕ делать

- ❌ `apt-get autoremove` без проверки списка
- ❌ `docker system prune -a` (удалит образы web3gram, qdrant)
- ❌ `rm -rf /opt/*` — снесёт чужие проекты
- ❌ Перезаписывать `/etc/caddy/Caddyfile` целиком
- ❌ Менять системные настройки PHP-FPM, fail2ban, Docker-демона
- ❌ Чистить `/root/autoposter`, `/root/.pm2`, `/root/.npm`

### Bybit Mainnet
- **API-ключ #3** (текущий): начинается с `QVUK*...quqN`
- Старые ключи отозваны (#1 demo, #2 mainnet после засветки в HTTP)
- Permissions: Read-Write, Spot Trading, Unified Trading. **Без Withdraw**.
- IP-restriction: **TODO добавить 168.222.143.103**
- **Баланс**: $52.76 USDT в Unified Trading Account

### Telegram
- Bot token: засвечен в чате — **TODO ротировать через @BotFather**
- chat_id: `789368186`
- Проверено: уведомления работают через IP-fallback

### Локальные файлы
- **Workspace**: `e:\AI\AI_folder\grid-bot\`
- **Контекст**: `e:\AI\AI_folder\context\grid-bot-HANDOFF.md` (этот файл)
- **Roadmap**: `e:\AI\AI_folder\context\trading-bots-roadmap.md`

---

## Расположение на VPS

```
/opt/grid-bot/
├── backend/
├── frontend/
├── data/
│   └── bot.db          ← SQLite, в Docker volume
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                ← права 600, секреты
```

Конфиги системы:
```
/etc/caddy/Caddyfile     ← reverse-proxy на 127.0.0.1:8000 + автоHTTPS
/var/lib/caddy/.local/share/caddy/  ← acme storage (сертификаты)
```

---

## Запуск/перезапуск

```bash
# На VPS (через SSH):
cd /opt/grid-bot
docker compose up -d         # запуск
docker compose down          # остановка
docker compose logs -f       # логи
docker compose restart       # рестарт
docker compose build && docker compose up -d  # пересборка после изменений
```

С локальной машины проще через утилиты в `tools/`:
```cmd
cmd /c 'e:\AI\AI_folder\grid-bot\tools\vps_run.cmd "docker compose ps -a" '
cmd /c 'e:\AI\AI_folder\grid-bot\tools\vps_run.cmd "docker logs grid-bot --tail 50"'
```

Эти .cmd-обёртки используют `plink` (PuTTY) с захардкоженным паролем и
host key. После смены пароля — обновить файлы.

---

## Расположение проекта (локально)

```
e:\AI\AI_folder\grid-bot\
├── backend/
│   ├── main.py           ← FastAPI app, REST API, autostart_running_bots
│   ├── grid_engine.py    ← async grid engine (per-bot Task)
│   ├── exchange.py       ← ccxt + прямые v5-вызовы Bybit
│   ├── backtest.py       ← симуляция grid на свечах
│   ├── notifier.py       ← Telegram (с IP-fallback для обхода РКН)
│   ├── storage.py        ← SQLite + Fernet-шифрование
│   ├── config.py         ← .env loader
│   ├── models.py         ← Pydantic-схемы
│   └── __init__.py
├── frontend/
│   ├── index.html        ← одна страница, 5 секций
│   ├── app.js
│   └── style.css
├── tools/                ← диагностика + утилиты деплоя
│   ├── vps_run.cmd       ← plink-обёртка для команд на VPS
│   ├── vps_scp.cmd       ← pscp-обёртка для копирования файлов
│   ├── vps_init.cmd      ← принять host key (использовалось один раз)
│   ├── vps_make_env.sh   ← скрипт создания .env на сервере
│   ├── Caddyfile         ← конфиг Caddy (текущий на VPS)
│   └── diag_*.py         ← диагностика, оставлены для истории
├── .venv/                ← локальное Python 3.14 окружение
├── .env                  ← локальные секреты, не в git
├── .env.example
├── .dockerignore
├── .gitignore
├── Dockerfile            ← Python 3.12-slim
├── docker-compose.yml
├── DEPLOY.md             ← пошаговая инструкция деплоя
├── README.md
├── requirements.txt
└── run.cmd               ← локальный запуск
```

---

## Текущее состояние бота #6 (на AVAX, узкая сетка)

- **ID**: 6
- **Биржа**: bybit (mainnet)
- **Пара**: AVAX/USDT (после миграции с DOGE из-за низкой волатильности)
- **Цена AVAX при старте**: $8.986
- **Диапазон**: 8.71 – 9.24 (~±3% от цены, **узкая сетка**)
- **Уровней**: 10 (5 buy + 5 sell, фактически разместилось 9 — не хватило AVAX на L9)
- **Шаг между уровнями**: ~$0.059 (~0.66%)
- **Прибыль на пару сделок**: ~$0.020 после комиссий
- **Размер ордера**: $4.5 USDT
- **Stop-Loss**: 15%
- **Капитал**: $30.45 USDT + 2.4466 AVAX (~$21.93) = $52.35
- **Статус**: `running`
- **Открытых ордеров на Bybit**: 9
- **Старт**: 31.05.2026 13:56 МСК

### Расположение уровней
```
SELL  L9 = 9.240   (не размещён, не хватило AVAX)
SELL  L8 = 9.181
SELL  L7 = 9.122
SELL  L6 = 9.063
SELL  L5 = 9.004
─── РЫНОК = $8.986 ───
BUY   L4 = 8.945   (ближайший buy, -0.5%)
BUY   L3 = 8.886
BUY   L2 = 8.827
BUY   L1 = 8.768
BUY   L0 = 8.710
```

### История ботов

- **Bot #1** (24.05) — удалён, баг с дублированием
- **Bot #2** (24-29.05) — удалён, FIFO давал минусы. PnL = -$0.18 на 12 сделках
- **Bot #3** (29-31.05) — DOGE, level-to-level matching, **0 сделок за сутки** из-за слишком широкого диапазона ($0.08-0.12, ±20%) и низкой волатильности DOGE
- **Bot #4** (31.05) — кратковременный AVAX с size=$20, удалён
- **Bot #5** (31.05) — кратковременный, удалён в гонке
- **Bot #6** (31.05 - сейчас) — AVAX узкая сетка, **в работе**

### Прогноз
- 5-15 fills в день, ~$0.10-0.30/день
- Месяц: $3-9 (≈ 6-17% годовых на $52)
- Главная цель — подтвердить что level-to-level matching работает
  и P&L положительный

---

## Главные грабли деплоя (которые поймали и победили)

### 1. SSH-доступ к VPS из Windows
Стандартного `sshpass` на Windows нет. Решение — установить **PuTTY**
через winget, использовать `plink` с флагами `-batch -pw -hostkey`.
Утилиты в `tools/vps_run.cmd` и `tools/vps_scp.cmd`.

### 2. Архив Compress-Archive ломает пути
PowerShell делает .zip с **backslash** в путях, Linux unzip их не понимает.
Решение: использовать Python `tarfile` для tar.gz.

### 3. PowerShell перехватывает первый символ команды как `с` (кириллица)
Время от времени при старте команды в начало приклеивается кириллический
«с» — типичное наблюдение в этой PowerShell-сессии. Обход:
запускать через `cmd /c '...'`.

### 4. PowerShell не понимает `&&`
Заменили на `;` или `cmd /c '...'`.

### 5. reg.ru добавляет AAAA-записи автоматически
При создании A-записи `trade.aliterra.space → 168.222.143.103` система
reg.ru **автоматически добавила AAAA-запись** на их собственный IPv6
`2a00:f940:2:2:1:1:0:268`. Это сломало ACME challenge — Let's Encrypt
ходил по IPv6 на чужой сервер reg.ru, получал 404.

**Решение**: вручную удалить AAAA-записи через панель DNS reg.ru
(удалили `trade` и `www.trade`).

### 6. DNS-кеш Let's Encrypt
После удаления AAAA, у валидаторов LE остался кеш ~30-60 минут.
Помогло: подождать + чистка ACME storage Caddy + рестарт.

### 7. systemd-resolved кеширует AAAA
На самом VPS `127.0.0.53` (systemd-resolved) держал AAAA дольше
public DNS. С самого VPS curl на `trade.aliterra.space` шёл через
старый IPv6 на чужой сервер. **Не критично** — Caddy получил
сертификат через challenges от внешних серверов LE, которые видели
правильный IPv4. Браузеры пользователей резолвят через свои DNS
(нормально).

### 8. Telegram заблокирован на reg.ru cloud по SNI
Прямые HTTPS-запросы к `api.telegram.org` блокируются провайдером по
SNI/DPI. ICMP-ping проходит, но TLS handshake режется.

**Решение**: в `notifier.py` добавлен `_PinnedIPTransport` который
делает запрос на конкретный IP `149.154.167.220` (этот IP проходит
блокировку) с правильным SNI и Host-заголовком — TLS-серт валиден,
запрос доходит до Telegram. Fallback из 4 IP на случай если основной
тоже заблокируют.

Проверено: уведомления приходят.

### 9. Caddy logger и права на файлы
Первая версия `Caddyfile` логировала в `/var/log/caddy/`, но папка
принадлежит `root`, а Caddy от пользователя `caddy` — permission denied.
Решение: убрали явное логирование в файл, всё идёт в systemd journal
(`journalctl -u caddy`).

### 10. ENCRYPTION_KEY менять нельзя после первого ключа
Сохранили урок. На VPS свежий рандомный ключ генерируется один раз
скриптом `vps_make_env.sh`.

---

## Архитектура полная (к деплою добавилось)

### Что было ранее (см. trading-bots-roadmap)
- FastAPI + ccxt + SQLite, 7 бирж, тёмная веб-морда
- Шифрование ключей через Fernet
- 5 секций UI: ключи, тикер, бот, telegram, бэктест
- Grid-движок с FIFO P&L
- Auto-recovery running ботов при рестарте сервера

### Что добавилось при деплое
- **Docker**: Python 3.12-slim образ, ~150MB
- **docker-compose**: volume `./data:/app/data` для SQLite, restart unless-stopped
- **Caddy** v2.11.3 как reverse-proxy с авто-HTTPS
- **UFW firewall**: только 22/80/443 наружу, IPv6 закрыт
- **systemd autostart**: Caddy и Docker стартуют при boot

### Сетевая схема

```
Browser
   ↓ HTTPS
trade.aliterra.space
   ↓ DNS A
168.222.143.103 (VPS)
   ↓ port 443
Caddy (Let's Encrypt cert)
   ↓ reverse_proxy
127.0.0.1:8000 (Docker port mapping)
   ↓
grid-bot container
  ↓
  uvicorn → backend.main:app
  ↓
  SQLite (volume) + ccxt → Bybit API
  ↓
  notifier → Telegram (через IP-pinning)
```

---

## Что обязательно сделать в ближайшее время

### Безопасность (TODO)
- [ ] **Сменить Telegram-токен** в @BotFather → /mybots → Revoke. Скинуть мне новый, обновлю `.env` и перезапущу.
- [ ] **Сменить пароль root** на SSH-ключ. Шаги:
  1. Сгенерировать SSH-ключ (если у пользователя ещё нет)
  2. Положить публичный в `/root/.ssh/authorized_keys` на VPS
  3. В `/etc/ssh/sshd_config` поставить `PasswordAuthentication no`
  4. `systemctl restart ssh`
  5. Обновить `vps_run.cmd` и `vps_scp.cmd` с использованием `-i ключ.ppk`
- [ ] **IP-restriction в Bybit** на API-ключе #3 — указать `168.222.143.103`. Это значит ключ будет работать только с нашего VPS, утечка перестанет быть страшной.
- [ ] **Регулярные бэкапы** SQLite — script + cron на VPS, и отдельный бэкап на локальный ПК.

### Наблюдение
- [ ] Через 1 час глянуть UI — сколько fills прошло
- [ ] Через сутки — посмотреть P&L и историю по кнопке 📊
- [ ] Через неделю — оценить реальную доходность

---

## Команды для нового чата (если попадёшь сюда заново)

### Проверить что всё живо
```cmd
cmd /c 'e:\AI\AI_folder\grid-bot\tools\vps_run.cmd "docker compose -f /opt/grid-bot/docker-compose.yml ps && curl -s https://trade.aliterra.space/api/health"'
```

### Глянуть статус ботов
```cmd
cmd /c 'e:\AI\AI_folder\grid-bot\tools\vps_run.cmd "curl -s https://trade.aliterra.space/api/bots"'
```

### Логи контейнера
```cmd
cmd /c 'e:\AI\AI_folder\grid-bot\tools\vps_run.cmd "docker logs grid-bot --tail 100"'
```

### Перезапустить бота
Через UI: Stop → Start. Или API:
```
POST https://trade.aliterra.space/api/bots/1/stop
POST https://trade.aliterra.space/api/bots/1/start
```

### Обновить код на VPS
```cmd
:: 1. Локально внести правки
:: 2. Залить нужные файлы (например backend/notifier.py):
cmd /c 'e:\AI\AI_folder\grid-bot\tools\vps_scp.cmd e:\AI\AI_folder\grid-bot\backend\notifier.py root@168.222.143.103:/opt/grid-bot/backend/notifier.py'
:: 3. Пересобрать и рестарт:
cmd /c 'e:\AI\AI_folder\grid-bot\tools\vps_run.cmd "cd /opt/grid-bot && docker compose build && docker compose up -d"'
```

### Полная переустановка проекта
1. Локально: создать `tar.gz` через Python tarfile
2. `pscp` на VPS в `/opt/grid-bot/`
3. `tar -xzf ... && docker compose up -d --build`

---

## История разработки

### День 1 — 23.05.2026: MVP
Один длинный день. Создали grid-бота от нуля. Прошли 8 значимых граблей с Bybit
Demo API. Финал: рабочий бэктест на исторических данных, ASCII equity-chart.

### День 2 — 24.05.2026: Деплой на VPS

**Утро (10:00–11:30)**:
- Пользователь заказал VPS на cloud.reg.ru (HP C1-M1-D10, 300₽/мес)
- Установлен plink (PuTTY) на локальной Windows для SSH-автоматизации
- VPS: обновление системы, установка Docker 29.5.2 + Compose v5.1.4
- Tar.gz архив проекта (80KB), залит через pscp
- Сгенерирован свежий ENCRYPTION_KEY (40 символов рандом)
- Контейнер собран и запущен, локально по `:8000` отвечает

**День (11:30–13:00)**:
- DNS A-запись `trade.aliterra.space` через панель reg.ru
- Borьба с auto-добавляемыми AAAA-записями reg.ru
- Установка Caddy v2.11.3 для HTTPS
- Долгое получение сертификата (DNS-кеш у Let's Encrypt + AAAA на чужой сервер)
- Удалили AAAA-записи (trade и www.trade), почистили ACME-storage
- HTTPS сертификат от Let's Encrypt получен
- UI доступен по `https://trade.aliterra.space`

**Полдень (13:00–13:15)**:
- Старый API-ключ Bybit (засветился в HTTP) удалён, выпущен новый #3
- Bybit пополнен ~$50 USDT, в боте видно $52.76
- Создан Bot #1 DOGE/USDT, 8 уровней, диапазон 0.09-0.12
- Telegram не отправлял сообщения — заблокировано РКН на reg.ru cloud
- Найдено: api.telegram.org IP `149.154.167.220` проходит блокировку
- Написан `_PinnedIPTransport` в notifier для IP-pinning с правильным SNI
- Контейнер пересобран, **уведомления заработали**
- Bot #1 запущен повторно, сообщение «▶️ запущен» пришло в Telegram
- Все 8 ордеров стоят на Bybit Mainnet

**Финал дня**: бот в работе, ждём первые сделки.

---

## Зависимости (полный список)

```
# requirements.txt
fastapi>=0.115
uvicorn[standard]>=0.32
ccxt>=4.4
pydantic>=2.9
pydantic-settings>=2.6
python-dotenv>=1.0
cryptography>=43
httpx>=0.27
aiosqlite>=0.20
```

Системные пакеты VPS:
- `docker-ce`, `docker-compose-plugin` (через get.docker.com)
- `caddy` v2.11.3 (cloudsmith repo)
- `unzip` (для распаковки архива при деплое)
- `ufw` (firewall, пришёл в Ubuntu 24.04)

Размер итоговый:
- Docker image grid-bot:latest = ~280 MB
- Использование диска /opt/grid-bot/ + Docker = ~500 MB
- RAM: контейнер ~150 MB + Caddy ~30 MB + системы = ~250 MB занято из 1 GB

---

## Карта чата для нового бота-ассистента

Если попадёшь в новый чат и нужно продолжить работу:

1. **Прочитай оба файла**: этот + `trading-bots-roadmap.md`
2. **Текущее состояние** (на 24.05.2026 13:15):
   - VPS работает, https://trade.aliterra.space доступен
   - Bot #1 DOGE/USDT в `running`, ждёт fills
   - Капитал $52.76, в работе $40
3. **Спроси пользователя**:
   - Сколько P&L набежало с момента запуска
   - Хочет ли смену токена / IP-restriction
   - Какой следующий шаг по roadmap (funding farmer? ML-фильтр?)
4. **Не забудь** про возможные грабли в этой сессии:
   - PowerShell иногда приклеивает кириллический «с» в начало команд
   - cmd-обёртки через `cmd /c '...'` обходят это
   - SSH через `tools\vps_run.cmd` (plink + хардкод пароля)

### Важные правила для будущих изменений
- API-ключи никогда не печатать в логах/ответах
- ENCRYPTION_KEY никогда не менять на работающей системе
- Перед тем как трогать `.env` — проверить что есть бэкап БД
- Перед перезапуском контейнера — отметить открытые позиции в Bybit
- При обновлении Caddyfile — `caddy validate` перед `systemctl reload`
