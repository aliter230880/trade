# Grid Trading Bot

Простой grid-бот для криптобирж (Bybit, OKX, Binance и др. через ccxt).

## Стек

- **Python 3.12+** (работает и на 3.14)
- **FastAPI** — REST API + статика
- **ccxt** — унифицированный клиент бирж
- **SQLite** — хранение состояния
- **WebSocket** — стрим цен и ордеров
- Простая HTML/JS морда без сборщиков

## Структура

```
grid-bot/
├── backend/
│   ├── main.py           # FastAPI app
│   ├── grid_engine.py    # логика сетки
│   ├── exchange.py       # обёртка ccxt
│   ├── storage.py        # SQLite
│   └── models.py         # Pydantic модели
├── frontend/
│   ├── index.html        # одностраничная морда
│   ├── app.js
│   └── style.css
├── data/                 # SQLite + логи (gitignore)
├── .env.example
├── requirements.txt
└── run.cmd               # запуск локально
```

## Быстрый старт (локально)

```cmd
cd e:\AI\AI_folder\grid-bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
run.cmd
```

Открыть `http://localhost:8000`.

## Безопасность API-ключей

- Используй Bybit **Demo Trading** для тестов.
- Permissions: **Read + Trade**, БЕЗ Withdraw.
- Ключи хранятся локально в `data/keys.db` (SQLite, не уходит в git).
- Никогда не комить `.env`.

## Этапы

- [x] Каркас проекта
- [ ] Подключение к бирже через ccxt
- [ ] Логика grid (расстановка ордеров)
- [ ] Веб-морда с настройками и P&L
- [ ] Telegram уведомления
- [ ] Бэктест на исторических свечах
- [ ] Docker для деплоя на VPS
