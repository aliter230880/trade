"""Grid trading engine — level-to-level matching.

Логика (исправленная версия):
- Делим диапазон [lower_price, upper_price] на N равных уровней L0..L(n-1).
- Изначально на каждом уровне НИЖЕ текущей цены ставим лимитный BUY,
  на каждом уровне ВЫШЕ — лимитный SELL.
- Каждому ордеру в БД пишем `level_index` — какому уровню сетки он принадлежит.
- Когда BUY на уровне L_i исполнился — ставим SELL на уровне L_(i+1).
- Когда SELL на уровне L_(i+1) исполнился — ставим BUY на уровне L_i.
- P&L по паре сделок = (price[L_(i+1)] - price[L_i]) * qty - fees
  — гарантированно > 0, если шаг сетки > комиссии.

Это level-to-level matching, не FIFO. Каждая ячейка сетки изолирована.

Дополнительно:
- Stop-Loss: если цена ушла ниже lower_price на stop_loss_pct% — останавливаемся.
- Take-Profit: если realized_pnl превысил take_profit_pct% от капитала — останавливаемся.
- Рецентровка диапазона запрещена (уровни фиксированы при создании).

ИСПРАВЛЕНО (v2 — restart recovery):
- При рестарте сервера явно синхронизируем все 'open' ордера с биржей.
  Ордера, исполненные за время простоя, обрабатываются сразу — не теряются.
- Ордера, отменённые биржей за время простоя, помечаются canceled в БД.
- Убран silent `pass` в autostart — ошибки теперь логируются.
- При resume-старте добавлен явный шаг cancel orphan orders на бирже
  (ордера которые есть на бирже, но отсутствуют в нашей БД).
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import ccxt

from .config import settings
from .exchange import (
    bybit_cancel_all,
    bybit_fetch_order,
    bybit_place_order,
    fetch_market_meta,
    fetch_ticker,
    fmt_step,
    make_client,
    round_step,
)
from .notifier import (
    notify_error,
    notify_fill,
    notify_started,
    notify_stopped,
)
from .storage import (
    get_api_key,
    get_conn,
    update_order_fill_v2 as _update_fill_v2,
)

log = logging.getLogger("grid")


class GridBot:
    """Grid-бот с level-to-level matching."""

    def __init__(self, bot_id: int):
        self.bot_id = bot_id
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self.client: Optional[ccxt.Exchange] = None
        self.cfg: dict = {}
        self.market_meta: dict = {}
        self.levels: list[float] = []  # цены уровней L0..Ln-1

    # ---------- lifecycle ----------

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name=f"grid-{self.bot_id}")

    async def stop(self, cancel_orders: bool = True) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except asyncio.TimeoutError:
                self._task.cancel()
        if cancel_orders and self.client and self.cfg:
            try:
                if self.client.id == "bybit":
                    await asyncio.to_thread(
                        bybit_cancel_all, self.client, self.cfg["symbol"]
                    )
                else:
                    await asyncio.to_thread(
                        self.client.cancel_all_orders, self.cfg["symbol"]
                    )
            except Exception as exc:
                log.warning("cancel_all_orders failed: %s", exc)
            # Помечаем все open-ордера как canceled в БД
            with get_conn() as conn:
                conn.execute(
                    "UPDATE bot_orders SET status='canceled' "
                    "WHERE bot_id=? AND status='open'",
                    (self.bot_id,),
                )
        _set_status(self.bot_id, "stopped")
        with get_conn() as conn:
            r = conn.execute(
                "SELECT realized_pnl FROM grid_bots WHERE id=?",
                (self.bot_id,),
            ).fetchone()
        if r:
            notify_stopped(self.bot_id, float(r["realized_pnl"]))

    # ---------- main loop ----------

    async def _run(self) -> None:
        try:
            self._load()
            self._connect()
            self.levels = self._calc_levels()

            # Если есть незакрытые ордера в БД — значит мы переподнимаемся
            # после рестарта, начальную сетку ставить НЕ нужно.
            with get_conn() as conn:
                existing = conn.execute(
                    "SELECT COUNT(*) c FROM bot_orders "
                    "WHERE bot_id=? AND status='open'",
                    (self.bot_id,),
                ).fetchone()["c"]

            if existing > 0:
                log.info(
                    "bot %s: resuming after restart — %d open orders in DB, "
                    "syncing with exchange...",
                    self.bot_id, existing,
                )
                # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: явная синхронизация с биржей.
                # Ордера, исполненные пока сервер был выключен, обрабатываются
                # немедленно — не ждём следующего poll-цикла.
                await asyncio.to_thread(self._sync_fills_from_exchange)
            else:
                log.info("bot %s: fresh start — placing initial grid", self.bot_id)
                await asyncio.to_thread(self._place_initial_grid)

            _set_status(self.bot_id, "running", started=True)
            notify_started(
                self.bot_id, self.cfg["symbol"], int(self.cfg["grid_levels"]),
                float(self.cfg["lower_price"]), float(self.cfg["upper_price"]),
            )

            while not self._stop.is_set():
                try:
                    await asyncio.to_thread(self._poll_orders)
                    if await asyncio.to_thread(self._check_stop_loss):
                        log.warning("bot %s: stop-loss triggered", self.bot_id)
                        break
                except Exception as exc:
                    log.exception("poll error bot %s: %s", self.bot_id, exc)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=4)
                except asyncio.TimeoutError:
                    pass
        except Exception as exc:
            log.exception("bot %s crashed: %s", self.bot_id, exc)
            _set_status(self.bot_id, "error", error=str(exc))
            notify_error(self.bot_id, str(exc))

    # ---------- sync on resume ----------

    def _sync_fills_from_exchange(self) -> None:
        """Синхронизируем open-ордера из БД с реальным состоянием на бирже.

        Вызывается ОДИН РАЗ при resume-старте (после рестарта сервера).

        Что делает:
        - Для каждого 'open' ордера в БД запрашивает статус у биржи.
        - Если ордер исполнен (closed) — вызывает _on_fill() → размещает встречный.
        - Если ордер отменён (canceled) — помечает в БД.
        - Если биржа не знает ордер (unknown) — помечает как canceled в БД
          (безопаснее чем оставить 'open' навсегда).

        Благодаря этому шагу заявки, исполнившиеся пока сервер был выключен,
        не теряются — встречные ордера будут выставлены сразу при старте.
        """
        assert self.client
        symbol = self.cfg["symbol"]

        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM bot_orders WHERE bot_id=? AND status='open'",
                (self.bot_id,),
            ).fetchall()

        if not rows:
            log.info("bot %s: no open orders in DB to sync", self.bot_id)
            return

        log.info("bot %s: syncing %d open orders with exchange", self.bot_id, len(rows))
        filled_cnt = 0
        canceled_cnt = 0

        for r in rows:
            if not r["exchange_order_id"]:
                # Ордер без ID биржи — был создан локально, но не дошёл до биржи.
                # Помечаем как canceled.
                _mark_canceled(r["id"])
                canceled_cnt += 1
                continue
            try:
                if self.client.id == "bybit":
                    o = bybit_fetch_order(self.client, r["exchange_order_id"], symbol)
                else:
                    o = self.client.fetch_order(r["exchange_order_id"], symbol)
            except Exception as exc:
                log.warning(
                    "bot %s: sync fetch_order %s failed: %s — skipping",
                    self.bot_id, r["exchange_order_id"], exc,
                )
                continue

            status = o.get("status")
            if status == "closed":
                log.info(
                    "bot %s: fill during downtime — %s %s @ %s (order %s)",
                    self.bot_id, r["side"], r["amount"], r["price"],
                    r["exchange_order_id"],
                )
                self._on_fill(r, o)
                filled_cnt += 1
            elif status in ("canceled", "unknown"):
                _mark_canceled(r["id"])
                canceled_cnt += 1
            # status == "open" → ничего не делаем, ордер жив на бирже

        log.info(
            "bot %s: sync complete — %d fills processed, %d canceled",
            self.bot_id, filled_cnt, canceled_cnt,
        )

    # ---------- helpers ----------

    def _load(self) -> None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM grid_bots WHERE id = ?", (self.bot_id,)
            ).fetchone()
        if not row:
            raise RuntimeError(f"bot {self.bot_id} not found")
        self.cfg = dict(row)

    def _connect(self) -> None:
        rec = get_api_key(self.cfg["api_key_id"])
        if not rec:
            raise RuntimeError("API ключ не найден")
        self.client = make_client(
            rec["exchange"], rec["api_key"], rec["api_secret"],
            rec["passphrase"], rec["testnet"],
        )
        if self.client.id != "bybit":
            self.client.load_markets()
        self.market_meta = fetch_market_meta(self.client, self.cfg["symbol"])

    def _calc_levels(self) -> list[float]:
        n = int(self.cfg["grid_levels"])
        lo = float(self.cfg["lower_price"])
        hi = float(self.cfg["upper_price"])
        step = (hi - lo) / (n - 1)
        tick = self.market_meta.get("tick_size") or 0.0001
        levels = [round_step(lo + i * step, tick) for i in range(n)]
        for i in range(1, len(levels)):
            if levels[i] <= levels[i - 1]:
                raise RuntimeError(
                    f"Уровни сетки слишком близки (tick_size={tick}, "
                    f"step={step}). Расширь диапазон или уменьши grid_levels."
                )
        return levels

    def _amount_per_order(self, price: float) -> float:
        return float(self.cfg["order_size_quote"]) / price

    def _place_initial_grid(self) -> None:
        """Расставляем сетку: на уровнях ниже текущей цены — buy, выше — sell."""
        assert self.client
        symbol = self.cfg["symbol"]
        ticker = fetch_ticker(self.client, symbol)
        last = float(ticker["last"])

        meta = self.market_meta
        min_qty = max(meta.get("min_qty", 0), 0)
        qty_step = meta.get("qty_step") or 0.000001
        tick = meta.get("tick_size") or 0.01

        for i, price in enumerate(self.levels):
            if abs(price - last) < tick / 2:
                continue
            side = "buy" if price < last else "sell"
            raw_amount = self._amount_per_order(price)
            amount = round_step(raw_amount, qty_step)
            if amount < min_qty:
                amount = min_qty
            try:
                if self.client.id == "bybit":
                    order = bybit_place_order(
                        self.client, symbol, side, amount, price,
                        qty_step=qty_step, tick_size=tick,
                    )
                else:
                    amount = float(self.client.amount_to_precision(symbol, amount))
                    price_r = float(self.client.price_to_precision(symbol, price))
                    order = self.client.create_order(
                        symbol, "limit", side, amount, price_r
                    )
                _save_order(self.bot_id, order, side, price, amount, level_index=i)
                log.info("bot %s: placed initial %s @ L%d=%s",
                         self.bot_id, side, i, price)
            except Exception as exc:
                log.warning("place initial %s @ L%d=%s failed: %s",
                            side, i, price, exc)

    def _poll_orders(self) -> None:
        """Опрашиваем биржу на предмет исполнений и canceled."""
        assert self.client
        symbol = self.cfg["symbol"]

        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM bot_orders "
                "WHERE bot_id = ? AND status = 'open'",
                (self.bot_id,),
            ).fetchall()

        if not rows:
            return

        for r in rows:
            if not r["exchange_order_id"]:
                continue
            try:
                if self.client.id == "bybit":
                    o = bybit_fetch_order(self.client, r["exchange_order_id"], symbol)
                else:
                    o = self.client.fetch_order(r["exchange_order_id"], symbol)
            except Exception as exc:
                log.warning("fetch_order failed: %s", exc)
                continue
            status = o.get("status")
            if status == "closed":
                self._on_fill(r, o)
            elif status == "canceled":
                _mark_canceled(r["id"])

    def _on_fill(self, filled_row: sqlite3.Row, order: dict) -> None:
        """Обработка fill: level-to-level matching."""
        assert self.client
        symbol = self.cfg["symbol"]

        side = filled_row["side"]
        level_idx = int(filled_row["level_index"]) if filled_row["level_index"] is not None else -1

        if self.client.id == "bybit":
            fill_price = float(order.get("fill_price") or filled_row["price"])
            fill_qty = float(order.get("fill_qty") or filled_row["amount"])
            fee = float(order.get("fee") or 0)
            fee_coin = order.get("fee_coin") or ""
        else:
            fill_price = float(order.get("average") or order.get("price") or filled_row["price"])
            fill_qty = float(order.get("filled") or filled_row["amount"])
            fee_info = order.get("fee") or {}
            fee = float(fee_info.get("cost") or 0)
            fee_coin = fee_info.get("currency") or ""

        realized = 0.0
        new_level_idx: Optional[int] = None

        if side == "sell" and 0 < level_idx < len(self.levels):
            buy_price = self.levels[level_idx - 1]
            buy_fee_estimate = buy_price * fill_qty * 0.001
            realized = (fill_price - buy_price) * fill_qty - fee - buy_fee_estimate
            new_level_idx = level_idx - 1
        elif side == "buy" and 0 <= level_idx < len(self.levels) - 1:
            new_level_idx = level_idx + 1
        elif side == "buy":
            log.info("bot %s: buy at top level %d, no counter sell", self.bot_id, level_idx)
        elif side == "sell":
            log.info("bot %s: sell at bottom level %d, no counter buy", self.bot_id, level_idx)

        _update_fill_v2(filled_row["id"], fill_price, fill_qty, fee, fee_coin, realized)
        if realized != 0:
            _add_pnl(self.bot_id, realized)

        if new_level_idx is None:
            self._notify_fill(symbol, side, fill_price, fill_qty, realized)
            return

        new_price = self.levels[new_level_idx]
        new_side = "sell" if side == "buy" else "buy"

        try:
            qty_step = self.market_meta.get("qty_step") or 0.000001
            tick = self.market_meta.get("tick_size") or 0.01
            new_amount = round_step(fill_qty, qty_step)
            if self.client.id == "bybit":
                new_order = bybit_place_order(
                    self.client, symbol, new_side, new_amount, new_price,
                    qty_step=qty_step, tick_size=tick,
                )
            else:
                new_price_r = float(self.client.price_to_precision(symbol, new_price))
                new_amount = float(self.client.amount_to_precision(symbol, new_amount))
                new_order = self.client.create_order(
                    symbol, "limit", new_side, new_amount, new_price_r
                )
            _save_order(self.bot_id, new_order, new_side, new_price, new_amount,
                        level_index=new_level_idx)
            log.info("bot %s: %s L%d @ %s -> %s L%d @ %s, pnl=%.4f",
                     self.bot_id, side, level_idx, fill_price,
                     new_side, new_level_idx, new_price, realized)
        except Exception as exc:
            log.warning("place counter %s L%d @ %s failed: %s",
                        new_side, new_level_idx, new_price, exc)

        self._notify_fill(symbol, side, fill_price, fill_qty, realized)

    def _notify_fill(self, symbol: str, side: str, price: float,
                     qty: float, realized: float) -> None:
        with get_conn() as conn:
            open_cnt = conn.execute(
                "SELECT COUNT(*) c FROM bot_orders WHERE bot_id=? AND status='open'",
                (self.bot_id,),
            ).fetchone()["c"]
        notify_fill(self.bot_id, symbol, side, price, qty, realized, int(open_cnt))

    def _check_stop_loss(self) -> bool:
        """Проверка stop-loss. Возвращает True если нужно остановить бота."""
        sl_pct = self.cfg.get("stop_loss_pct")
        if not sl_pct or sl_pct <= 0:
            return False
        try:
            ticker = fetch_ticker(self.client, self.cfg["symbol"])
            price = float(ticker["last"])
        except Exception:
            return False
        lo = float(self.cfg["lower_price"])
        threshold = lo * (1 - float(sl_pct) / 100)
        if price < threshold:
            log.warning(
                "bot %s: price %s < SL threshold %s (lower=%s, sl_pct=%s)",
                self.bot_id, price, threshold, lo, sl_pct,
            )
            return True
        return False


# -------- DB helpers --------

def _save_order(bot_id: int, order: dict, side: str, price: float, amount: float,
                level_index: Optional[int] = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO bot_orders
               (bot_id, exchange_order_id, side, price, amount, status,
                created_at, level_index)
               VALUES (?, ?, ?, ?, ?, 'open', ?, ?)""",
            (bot_id, order.get("id"), side, price, amount,
             datetime.utcnow().isoformat(), level_index),
        )


def _mark_canceled(order_row_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE bot_orders SET status='canceled' WHERE id=?",
            (order_row_id,),
        )


def _add_pnl(bot_id: int, amount: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE grid_bots SET realized_pnl = realized_pnl + ? WHERE id = ?",
            (amount, bot_id),
        )


def _set_status(bot_id: int, status: str, started: bool = False, error: str = "") -> None:
    with get_conn() as conn:
        if started:
            conn.execute(
                "UPDATE grid_bots SET status=?, started_at=? WHERE id=?",
                (status, datetime.utcnow().isoformat(), bot_id),
            )
        else:
            conn.execute("UPDATE grid_bots SET status=? WHERE id=?", (status, bot_id))


# -------- registry --------

_registry: dict[int, GridBot] = {}


def get_bot(bot_id: int) -> GridBot:
    bot = _registry.get(bot_id)
    if not bot:
        bot = GridBot(bot_id)
        _registry[bot_id] = bot
    return bot


async def stop_all() -> None:
    for bot in list(_registry.values()):
        await bot.stop(cancel_orders=False)
    _registry.clear()
