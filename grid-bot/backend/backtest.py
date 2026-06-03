"""Backtest grid-стратегии на исторических свечах."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .exchange import fetch_ohlcv


@dataclass
class GridLevel:
    price: float
    side: str  # 'buy' | 'sell'
    state: str = "open"  # open | filled


@dataclass
class Trade:
    side: str
    price: float
    qty: float
    fee: float
    ts: int
    realized_pnl: float = 0.0


@dataclass
class BacktestResult:
    symbol: str
    days: int
    timeframe: str
    candles_used: int
    lower_price: float
    upper_price: float
    grid_levels: int
    order_size_quote: float
    fee_rate: float

    start_ts: int = 0
    end_ts: int = 0
    start_price: float = 0
    end_price: float = 0

    # итоги
    total_trades: int = 0  # включая buy и sell
    matched_pairs: int = 0  # закрытых пар (buy+sell)
    realized_pnl: float = 0
    fees_paid: float = 0
    unrealized_value: float = 0  # стоимость остатков base-актива по цене закрытия минус
                                  # средняя цена набора
    max_drawdown_pct: float = 0
    equity_curve: list[dict] = field(default_factory=list)  # [{ts, equity}]
    trades: list[dict] = field(default_factory=list)


def run_backtest(
    client,
    symbol: str,
    lower_price: float,
    upper_price: float,
    grid_levels: int,
    order_size_quote: float = 100.0,
    days: int = 30,
    timeframe: str = "5m",
    fee_rate: float = 0.001,
) -> BacktestResult:
    if upper_price <= lower_price or grid_levels < 3:
        raise ValueError("Некорректные параметры grid")

    # Размер свечного окна
    minutes_per_candle = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "2h": 120, "4h": 240, "1d": 1440,
    }.get(timeframe, 5)

    # Bybit API ограничен 1000 свечами на запрос. Если запрашиваемый период не
    # помещается — автоматически переключаемся на больший таймфрейм.
    needed = int(days * 24 * 60 / minutes_per_candle)
    if needed > 1000:
        # Перебираем таймфреймы по возрастанию пока не влезет 1000
        for tf, mins in [("15m", 15), ("30m", 30), ("1h", 60),
                        ("2h", 120), ("4h", 240), ("1d", 1440)]:
            if int(days * 24 * 60 / mins) <= 1000:
                timeframe = tf
                minutes_per_candle = mins
                break
    limit = min(int(days * 24 * 60 / minutes_per_candle), 1000)

    candles = fetch_ohlcv(client, symbol, timeframe, limit=limit)
    if not candles or len(candles) < 5:
        raise RuntimeError(f"Нет свечей для {symbol} (получено {len(candles) if candles else 0})")

    res = BacktestResult(
        symbol=symbol, days=days, timeframe=timeframe, candles_used=len(candles),
        lower_price=lower_price, upper_price=upper_price, grid_levels=grid_levels,
        order_size_quote=order_size_quote, fee_rate=fee_rate,
        start_ts=int(candles[0][0]), end_ts=int(candles[-1][0]),
        start_price=float(candles[0][1]), end_price=float(candles[-1][4]),
    )

    # Расстановка сетки: уровни равномерно. Используем "кольцевую" модель —
    # уровни всегда находятся на одной из сторон, переключаются после каждого fill.
    step = (upper_price - lower_price) / (grid_levels - 1)
    init_price = float(candles[0][1])
    # Каждый уровень имеет фиксированную цену и текущую сторону (buy/sell), которая
    # переключается после исполнения. Так сетка не "размножается".
    levels: list[GridLevel] = []
    for i in range(grid_levels):
        p = lower_price + i * step
        side = "buy" if p < init_price else "sell"
        levels.append(GridLevel(price=p, side=side))

    # FIFO стек buys без пары для расчёта realized
    buy_queue: list[Trade] = []

    # Equity = (USDT кеш) + (qty BTC * price)
    # Изначально считаем что стартовый кеш = order_size_quote * grid_levels * 1.5
    starting_cash = order_size_quote * grid_levels * 1.5
    cash = starting_cash
    base_qty = 0.0  # стартуем без позиции в base
    peak_equity = starting_cash
    min_equity = starting_cash

    for c in candles:
        ts, o, hi, lo, cl, vol = c
        ts = int(ts); hi = float(hi); lo = float(lo); cl = float(cl)

        # Проверяем какие уровни сетки могла пересечь свеча
        # На каждой свече каждый уровень может сработать максимум ОДИН раз.
        # После исполнения уровень переключает сторону на противоположную и
        # становится снова активным после движения цены за этот уровень.
        for lv in levels:
            if lv.state != "open":
                continue
            if lv.side == "buy" and lo <= lv.price <= hi:
                qty = order_size_quote / lv.price
                fee = order_size_quote * fee_rate
                cash -= order_size_quote + fee
                base_qty += qty
                t = Trade(side="buy", price=lv.price, qty=qty, fee=fee, ts=ts)
                res.trades.append({
                    "ts": ts, "side": "buy", "price": lv.price,
                    "qty": qty, "fee": fee, "pnl": 0.0,
                })
                buy_queue.append(t)
                res.fees_paid += fee
                res.total_trades += 1
                # Уровень "переворачивается": теперь он ждёт sell
                lv.side = "sell"
                lv.state = "armed"  # станет open когда цена выйдет выше
            elif lv.side == "sell" and lo <= lv.price <= hi:
                if base_qty <= 0 or not buy_queue:
                    continue
                pair = buy_queue.pop(0)
                qty = pair.qty
                proceeds = lv.price * qty
                fee = proceeds * fee_rate
                cash += proceeds - fee
                base_qty -= qty
                pnl = (lv.price - pair.price) * qty - fee - pair.fee
                res.trades.append({
                    "ts": ts, "side": "sell", "price": lv.price,
                    "qty": qty, "fee": fee, "pnl": pnl,
                })
                res.fees_paid += fee
                res.realized_pnl += pnl
                res.matched_pairs += 1
                res.total_trades += 1
                lv.side = "buy"
                lv.state = "armed"

        # Перевод armed → open: если цена ушла дальше уровня, его можно "перевзвести"
        for lv in levels:
            if lv.state == "armed":
                if lv.side == "buy" and cl > lv.price * 1.001:
                    lv.state = "open"
                elif lv.side == "sell" and cl < lv.price * 0.999:
                    lv.state = "open"

        # Equity на конец свечи
        equity = cash + base_qty * cl
        peak_equity = max(peak_equity, equity)
        min_equity = min(min_equity, equity)
        dd = (peak_equity - equity) / peak_equity * 100 if peak_equity > 0 else 0
        res.max_drawdown_pct = max(res.max_drawdown_pct, dd)
        res.equity_curve.append({"ts": ts, "equity": equity, "price": cl})

    # Финальная оценка остатков
    end_price = res.end_price
    res.unrealized_value = base_qty * end_price - sum(b.price * b.qty for b in buy_queue)

    return res


def result_to_dict(r: BacktestResult) -> dict:
    pnl_pct = r.realized_pnl / (r.order_size_quote * r.grid_levels) * 100
    duration_days = (r.end_ts - r.start_ts) / 1000 / 86400 if r.start_ts else r.days
    monthly = pnl_pct * (30 / duration_days) if duration_days > 0 else 0
    return {
        "symbol": r.symbol,
        "timeframe": r.timeframe,
        "days": r.days,
        "candles_used": r.candles_used,
        "params": {
            "lower_price": r.lower_price,
            "upper_price": r.upper_price,
            "grid_levels": r.grid_levels,
            "order_size_quote": r.order_size_quote,
            "fee_rate": r.fee_rate,
        },
        "start_price": r.start_price,
        "end_price": r.end_price,
        "price_change_pct": (r.end_price - r.start_price) / r.start_price * 100,
        "total_trades": r.total_trades,
        "matched_pairs": r.matched_pairs,
        "realized_pnl_usdt": round(r.realized_pnl, 4),
        "fees_paid_usdt": round(r.fees_paid, 4),
        "unrealized_value_usdt": round(r.unrealized_value, 4),
        "pnl_pct_on_capital": round(pnl_pct, 3),
        "estimated_monthly_pct": round(monthly, 2),
        "max_drawdown_pct": round(r.max_drawdown_pct, 2),
        "equity_curve": r.equity_curve[::max(1, len(r.equity_curve) // 200)],  # max 200 точек
        "trades": r.trades[-50:],  # последние 50 для UI
    }
