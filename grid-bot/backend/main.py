"""FastAPI-приложение grid-бота."""

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import storage
from .config import settings
from .exchange import fetch_balance_usdt, fetch_ticker, make_client
from .grid_engine import get_bot, stop_all
from .models import (
    ApiKeyIn,
    ApiKeyOut,
    ApiResponse,
    ExchangeStatus,
    GridBotOut,
    GridConfigIn,
    SUPPORTED_EXCHANGES,
    TickerOut,
)

log = logging.getLogger("main")

app = FastAPI(title="Grid Trading Bot", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    storage.init_db()


@app.on_event("startup")
async def autostart_running_bots() -> None:
    """Если в БД остались боты со статусом 'running' — перезапустим их.

    Полезно если сервер перезапустился (рестарт VPS, обновление, краш).

    ИСПРАВЛЕНО v2:
    - Ошибки теперь логируются (раньше `except: pass` их глотал).
    - Бот сам делает _sync_fills_from_exchange() при resume-старте,
      поэтому ордера, исполненные за время простоя, не теряются.
    """
    bots = storage.list_grid_bots()
    running = [b for b in bots if b["status"] == "running"]

    if not running:
        log.info("autostart: no running bots to resume")
        return

    log.info("autostart: found %d bot(s) to resume after restart", len(running))

    for b in running:
        try:
            bot = get_bot(b["id"])
            asyncio.create_task(bot.start())
            log.info(
                "autostart: scheduled resume for bot %d (%s %s)",
                b["id"], b["exchange"], b["symbol"],
            )
        except Exception as exc:
            # Раньше здесь был `pass` — ошибка при рестарте оставалась невидимой.
            log.error(
                "autostart: failed to resume bot %d (%s %s): %s",
                b["id"], b["exchange"], b["symbol"], exc,
            )
            # Помечаем как error чтобы пользователь видел проблему в UI
            storage.set_bot_status(b["id"], "error")


# -------- API: ключи --------

@app.get("/api/exchanges")
def list_exchanges() -> dict:
    return {"exchanges": list(SUPPORTED_EXCHANGES)}


@app.post("/api/keys", response_model=ApiKeyOut)
def add_api_key(payload: ApiKeyIn) -> dict:
    key_id = storage.save_api_key(
        exchange=payload.exchange,
        api_key=payload.api_key,
        api_secret=payload.api_secret,
        passphrase=payload.passphrase,
        testnet=payload.testnet,
        label=payload.label,
    )
    keys = [k for k in storage.list_api_keys() if k["id"] == key_id]
    if not keys:
        raise HTTPException(500, "Не удалось сохранить ключ")
    return keys[0]


@app.get("/api/keys", response_model=list[ApiKeyOut])
def list_keys() -> list[dict]:
    return storage.list_api_keys()


@app.delete("/api/keys/{key_id}", response_model=ApiResponse)
def remove_key(key_id: int) -> dict:
    storage.delete_api_key(key_id)
    return {"ok": True, "message": "Ключ удалён"}


@app.get("/api/keys/{key_id}/status", response_model=ExchangeStatus)
def key_status(key_id: int) -> dict:
    rec = storage.get_api_key(key_id)
    if not rec:
        raise HTTPException(404, "Ключ не найден")
    try:
        client = make_client(
            rec["exchange"], rec["api_key"], rec["api_secret"],
            rec["passphrase"], rec["testnet"],
        )
        balance = fetch_balance_usdt(client)
        return {
            "exchange": rec["exchange"],
            "testnet": rec["testnet"],
            "connected": True,
            "balance_usdt": balance,
        }
    except Exception as exc:
        return {
            "exchange": rec["exchange"],
            "testnet": rec["testnet"],
            "connected": False,
            "error": str(exc),
        }


# -------- API: цены --------

@app.get("/api/ticker", response_model=TickerOut)
def get_ticker(key_id: int, symbol: str) -> dict:
    rec = storage.get_api_key(key_id)
    if not rec:
        raise HTTPException(404, "Ключ не найден")
    client = make_client(
        rec["exchange"], rec["api_key"], rec["api_secret"],
        rec["passphrase"], rec["testnet"],
    )
    try:
        return fetch_ticker(client, symbol)
    except Exception as exc:
        raise HTTPException(400, f"Не удалось получить тикер: {exc}") from exc


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": app.version}


@app.get("/api/notifier/status")
def notifier_status() -> dict:
    return {
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }


@app.post("/api/notifier/test")
def notifier_test() -> dict:
    from .notifier import send_telegram
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise HTTPException(400, "Telegram не настроен в .env "
                                  "(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
    send_telegram("✅ Тест связи с Grid Trading Bot")
    return {"ok": True, "message": "Сообщение отправлено"}


# -------- API: grid bots --------

@app.post("/api/bots", response_model=GridBotOut)
def create_bot(payload: GridConfigIn) -> dict:
    bot_id = storage.create_grid_bot(payload.model_dump())
    return storage.get_grid_bot(bot_id)


@app.get("/api/bots", response_model=list[GridBotOut])
def list_bots() -> list[dict]:
    return storage.list_grid_bots()


@app.get("/api/bots/{bot_id}", response_model=GridBotOut)
def read_bot(bot_id: int) -> dict:
    rec = storage.get_grid_bot(bot_id)
    if not rec:
        raise HTTPException(404, "Бот не найден")
    return rec


@app.post("/api/bots/{bot_id}/start", response_model=ApiResponse)
async def start_bot(bot_id: int) -> dict:
    if not storage.get_grid_bot(bot_id):
        raise HTTPException(404, "Бот не найден")
    bot = get_bot(bot_id)
    await bot.start()
    return {"ok": True, "message": "Бот запущен"}


@app.post("/api/bots/{bot_id}/stop", response_model=ApiResponse)
async def stop_bot(bot_id: int, cancel: bool = True) -> dict:
    bot = get_bot(bot_id)
    await bot.stop(cancel_orders=cancel)
    return {"ok": True, "message": "Бот остановлен"}


@app.delete("/api/bots/{bot_id}", response_model=ApiResponse)
async def delete_bot(bot_id: int) -> dict:
    bot = get_bot(bot_id)
    await bot.stop(cancel_orders=True)
    storage.delete_grid_bot(bot_id)
    return {"ok": True, "message": "Бот удалён"}


@app.get("/api/bots/{bot_id}/orders")
def bot_orders(bot_id: int, limit: int = 50) -> dict:
    return {"orders": storage.list_bot_orders(bot_id, limit)}


@app.get("/api/bots/{bot_id}/trades")
def bot_trades(bot_id: int, limit: int = 100) -> dict:
    """История исполненных ордеров с P&L."""
    return {"trades": storage.list_filled_trades(bot_id, limit)}


@app.get("/api/auto-range")
def auto_range(key_id: int, symbol: str, days: int = 7, mult: float = 1.5,
               levels_target: int = 12) -> dict:
    """Авто-подбор диапазона grid-бота по волатильности (ATR за N дней)."""
    rec = storage.get_api_key(key_id)
    if not rec:
        raise HTTPException(404, "Ключ не найден")
    client = make_client(
        rec["exchange"], rec["api_key"], rec["api_secret"],
        rec["passphrase"], rec["testnet"],
    )
    try:
        from .exchange import suggest_grid_range
        return suggest_grid_range(client, symbol, days=days, mult=mult,
                                  levels_target=levels_target)
    except Exception as exc:
        raise HTTPException(400, f"Авто-подбор не удался: {exc}") from exc


@app.post("/api/backtest")
def backtest(payload: dict) -> dict:
    """Бэктест grid-стратегии на исторических свечах."""
    rec = storage.get_api_key(payload["key_id"])
    if not rec:
        raise HTTPException(404, "Ключ не найден")
    client = make_client(
        rec["exchange"], rec["api_key"], rec["api_secret"],
        rec["passphrase"], rec["testnet"],
    )
    try:
        from .backtest import run_backtest, result_to_dict
        r = run_backtest(
            client,
            symbol=payload["symbol"],
            lower_price=float(payload["lower_price"]),
            upper_price=float(payload["upper_price"]),
            grid_levels=int(payload["grid_levels"]),
            order_size_quote=float(payload.get("order_size_quote", 100)),
            days=int(payload.get("days", 30)),
            timeframe=payload.get("timeframe", "5m"),
            fee_rate=float(payload.get("fee_rate", 0.001)),
        )
        return result_to_dict(r)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(400, f"Бэктест не удался: {exc}") from exc


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await stop_all()


# -------- Статика (фронт) --------

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
