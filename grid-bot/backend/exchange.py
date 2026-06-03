"""Обёртка над ccxt с unified-API для бирж."""

from decimal import Decimal, ROUND_DOWN
from typing import Optional

import ccxt


def make_client(
    exchange: str,
    api_key: str,
    api_secret: str,
    passphrase: str = "",
    testnet: bool = True,
) -> ccxt.Exchange:
    """Создаёт настроенный ccxt-клиент для нужной биржи.

    testnet=True означает «не трогать реальные деньги» и использует:
    - для Bybit: Demo Trading (api-demo.bybit.com), не testnet
    - для остальных: их sandbox/testnet через set_sandbox_mode
    """
    if exchange not in ccxt.exchanges:
        raise ValueError(f"ccxt не знает биржу '{exchange}'")

    cls = getattr(ccxt, exchange)
    params = {
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
    }
    if passphrase:
        params["password"] = passphrase  # OKX, KuCoin

    client: ccxt.Exchange = cls(params)
    # Для grid-бота на споте лучший дефолт — spot
    if hasattr(client, "options") and isinstance(client.options, dict):
        client.options["defaultType"] = "spot"

    if testnet:
        if exchange == "bybit":
            _switch_to_bybit_demo(client)
        else:
            try:
                client.set_sandbox_mode(True)
            except Exception:
                pass
    return client


def _switch_to_bybit_demo(client: ccxt.Exchange) -> None:
    """Bybit Demo Trading использует отдельный хост api-demo.bybit.com.

    Это НЕ testnet. ccxt-флаг sandbox даёт testnet, поэтому переписываем URLs руками.
    """
    demo_url = "https://api-demo.bybit.com"
    api_urls = client.urls.get("api")
    if isinstance(api_urls, dict):
        for k in list(api_urls.keys()):
            api_urls[k] = demo_url
    elif isinstance(api_urls, str):
        client.urls["api"] = demo_url
    client.hostname = "api-demo.bybit.com"


def fetch_balance_usdt(client: ccxt.Exchange) -> Optional[float]:
    """Возвращает суммарный баланс USDT по всем кошелькам биржи.

    Для Bybit Demo использует прямой вызов /v5/account/wallet-balance,
    т.к. ccxt-обёртка fetch_balance дёргает asset-эндпоинты, которые в demo
    не поддерживаются.
    """
    # Bybit demo / unified — самый надёжный путь
    if client.id == "bybit":
        try:
            r = client.privateGetV5AccountWalletBalance({"accountType": "UNIFIED"})
            for acc in (r.get("result") or {}).get("list", []):
                for coin in acc.get("coin", []):
                    if coin.get("coin") == "USDT":
                        v = coin.get("walletBalance") or coin.get("equity")
                        if v is not None:
                            return float(v)
        except Exception:
            pass
        # fallback: обычный путь (для mainnet)
        try:
            bal = client.fetch_balance({"accountType": "UNIFIED"})
            v = (bal.get("total") or {}).get("USDT")
            if v is not None:
                return float(v)
        except Exception:
            return None
        return None

    # Прочие биржи
    found: list[float] = []
    attempts: list[dict] = [{}]
    if client.id == "okx":
        attempts += [{"type": "trading"}, {"type": "funding"}]
    elif client.id == "binance":
        attempts += [{"type": "spot"}, {"type": "future"}]

    for params in attempts:
        try:
            bal = client.fetch_balance(params)
        except Exception:
            continue
        total = bal.get("total") or {}
        v = total.get("USDT") or total.get("usdt")
        if v is not None:
            try:
                found.append(float(v))
            except (TypeError, ValueError):
                pass
    return max(found) if found else None


def fetch_ticker(client: ccxt.Exchange, symbol: str) -> dict:
    if client.id == "bybit":
        return _bybit_fetch_ticker(client, symbol)
    t = client.fetch_ticker(symbol)
    return {
        "symbol": t["symbol"],
        "last": float(t["last"]),
        "bid": float(t.get("bid") or t["last"]),
        "ask": float(t.get("ask") or t["last"]),
        "timestamp": int(t["timestamp"] or 0),
    }


def _bybit_market_id(symbol: str) -> str:
    """'BTC/USDT' -> 'BTCUSDT' для v5 API."""
    return symbol.replace("/", "").replace(":USDT", "").upper()


def _bybit_fetch_ticker(client: ccxt.Exchange, symbol: str) -> dict:
    """Прямой вызов /v5/market/tickers — работает на mainnet, testnet и demo."""
    market_id = _bybit_market_id(symbol)
    r = client.publicGetV5MarketTickers({"category": "spot", "symbol": market_id})
    items = (r.get("result") or {}).get("list") or []
    if not items:
        raise RuntimeError(f"тикер {symbol} не найден")
    t = items[0]
    last = float(t["lastPrice"])
    bid = float(t.get("bid1Price") or last)
    ask = float(t.get("ask1Price") or last)
    return {
        "symbol": symbol,
        "last": last,
        "bid": bid,
        "ask": ask,
        "timestamp": int(t.get("time") or 0),
    }


def bybit_place_order(
    client: ccxt.Exchange,
    symbol: str,
    side: str,
    amount: float,
    price: float,
    qty_step: float = 0.000001,
    tick_size: float = 0.01,
) -> dict:
    """Лимитный ордер через /v5/order/create — обходит ccxt unified create_order."""
    market_id = _bybit_market_id(symbol)
    body = {
        "category": "spot",
        "symbol": market_id,
        "side": "Buy" if side.lower() == "buy" else "Sell",
        "orderType": "Limit",
        "qty": fmt_step(amount, qty_step),
        "price": fmt_step(price, tick_size),
        "timeInForce": "GTC",
    }
    r = client.privatePostV5OrderCreate(body)
    code = r.get("retCode")
    # Bybit может вернуть retCode как int или str в зависимости от пути
    try:
        code_int = int(code) if code is not None else 0
    except (TypeError, ValueError):
        code_int = -1
    if code_int != 0:
        raise RuntimeError(f"bybit place: {r.get('retMsg')} (code {code})")
    res = r.get("result") or {}
    return {"id": res.get("orderId"), "raw": r}


def bybit_fetch_order(client: ccxt.Exchange, order_id: str, symbol: str) -> dict:
    """Статус ордера. На demo всегда нужен 'openOnly=0' для исторических."""
    market_id = _bybit_market_id(symbol)
    # Сначала ищем среди открытых
    r = client.privateGetV5OrderRealtime(
        {"category": "spot", "symbol": market_id, "orderId": order_id}
    )
    items = (r.get("result") or {}).get("list") or []
    if items:
        return _normalize_bybit_order(items[0])
    # Если не нашли — смотрим в истории
    r = client.privateGetV5OrderHistory(
        {"category": "spot", "symbol": market_id, "orderId": order_id, "limit": 1}
    )
    items = (r.get("result") or {}).get("list") or []
    if items:
        return _normalize_bybit_order(items[0])
    return {"id": order_id, "status": "unknown"}


def _normalize_bybit_order(o: dict) -> dict:
    s = (o.get("orderStatus") or "").lower()
    if s in ("filled", "partiallyfilledcanceled"):
        status = "closed"
    elif s in ("cancelled", "canceled", "rejected"):
        status = "canceled"
    elif s in ("new", "partiallyfilled", "untriggered"):
        status = "open"
    else:
        status = s or "unknown"
    cum_qty = float(o.get("cumExecQty") or 0)
    cum_value = float(o.get("cumExecValue") or 0)
    avg_price = (cum_value / cum_qty) if cum_qty > 0 else float(o.get("avgPrice") or o.get("price") or 0)
    return {
        "id": o.get("orderId"),
        "status": status,
        "filled": cum_qty,
        "fill_price": avg_price,
        "fill_qty": cum_qty,
        "fee": float(o.get("cumExecFee") or 0),
        "fee_coin": o.get("feeCurrency") or "",
        "price": float(o.get("price") or 0),
    }


def bybit_cancel_all(client: ccxt.Exchange, symbol: str) -> None:
    market_id = _bybit_market_id(symbol)
    try:
        client.privatePostV5OrderCancelAll({"category": "spot", "symbol": market_id})
    except Exception:
        pass


def fetch_market_meta(client: ccxt.Exchange, symbol: str) -> dict:
    """Минимальные размеры/precision для пары. Для Bybit берём через v5/market/instruments-info."""
    if client.id == "bybit":
        market_id = _bybit_market_id(symbol)
        r = client.publicGetV5MarketInstrumentsInfo(
            {"category": "spot", "symbol": market_id}
        )
        items = (r.get("result") or {}).get("list") or []
        if not items:
            raise RuntimeError(f"инструмент {symbol} не найден")
        m = items[0]
        lot = m.get("lotSizeFilter") or {}
        price = m.get("priceFilter") or {}
        return {
            "min_qty": float(lot.get("minOrderQty") or 0),
            "qty_step": float(lot.get("basePrecision") or lot.get("qtyStep") or 0.000001),
            "min_notional": float(lot.get("minOrderAmt") or 0),
            "tick_size": float(price.get("tickSize") or 0.01),
        }
    # Прочие биржи — через стандартный markets
    client.load_markets()
    m = client.markets.get(symbol) or {}
    limits = m.get("limits") or {}
    return {
        "min_qty": (limits.get("amount") or {}).get("min") or 0,
        "qty_step": (m.get("precision") or {}).get("amount") or 0.000001,
        "min_notional": (limits.get("cost") or {}).get("min") or 0,
        "tick_size": (m.get("precision") or {}).get("price") or 0.01,
    }


def round_step(value: float, step: float) -> float:
    """Квантование с округлением вниз — без float-хвостов."""
    if step <= 0:
        return value
    d_value = Decimal(str(value))
    d_step = Decimal(str(step))
    quantized = (d_value / d_step).to_integral_value(rounding=ROUND_DOWN) * d_step
    # нормализуем чтобы убрать научную нотацию
    return float(quantized)


def fmt_step(value: float, step: float) -> str:
    """Возвращает строковое представление с количеством знаков, как в step.

    Это нужно для Bybit: он строго проверяет число знаков после точки.
    """
    if step <= 0:
        return str(value)
    d_value = Decimal(str(value))
    d_step = Decimal(str(step))
    quantized = (d_value / d_step).to_integral_value(rounding=ROUND_DOWN) * d_step
    # Приводим к фиксированному числу знаков, как у step
    s = str(d_step.normalize())
    if "." in s:
        decimals = len(s.split(".")[1].rstrip("0"))
    elif "E" in s.upper():
        # шаг типа 1E-6
        exp = int(s.lower().split("e")[1])
        decimals = -exp if exp < 0 else 0
    else:
        decimals = 0
    return f"{quantized:.{decimals}f}"



def fetch_ohlcv(client: ccxt.Exchange, symbol: str, timeframe: str = "1h",
                limit: int = 168) -> list[list]:
    """Свечи. Для Bybit — через v5/market/kline (работает на demo)."""
    if client.id == "bybit":
        market_id = _bybit_market_id(symbol)
        # Маппинг timeframe -> bybit interval
        bybit_intervals = {
            "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
            "1h": "60", "2h": "120", "4h": "240", "6h": "360",
            "12h": "720", "1d": "D", "1w": "W",
        }
        interval = bybit_intervals.get(timeframe, "60")
        r = client.publicGetV5MarketKline({
            "category": "spot", "symbol": market_id,
            "interval": interval, "limit": limit,
        })
        items = (r.get("result") or {}).get("list") or []
        # bybit возвращает в обратном порядке (новые первые)
        items = list(reversed(items))
        return [
            [int(x[0]), float(x[1]), float(x[2]), float(x[3]),
             float(x[4]), float(x[5])]
            for x in items
        ]
    # Прочие биржи через ccxt
    return client.fetch_ohlcv(symbol, timeframe, limit=limit)


def suggest_grid_range(client: ccxt.Exchange, symbol: str, days: int = 7,
                        mult: float = 1.5, levels_target: int = 12) -> dict:
    """Авто-подбор диапазона по волатильности.

    Берём 1h-свечи за N дней, считаем средний размах (high-low) и текущую цену.
    Диапазон = текущая цена ± mult * std(returns) * sqrt(N) ~ 'ожидаемый коридор'.
    Возвращаем рекомендованные lower/upper/levels и оценку step%.
    """
    limit = max(24 * days, 24)
    candles = fetch_ohlcv(client, symbol, "1h", limit=limit)
    if len(candles) < 12:
        raise RuntimeError(f"Слишком мало свечей для {symbol} (получено {len(candles)})")

    # ATR упрощённый: среднее (high - low) / close
    closes = [c[4] for c in candles]
    ranges = [(c[2] - c[3]) / c[4] for c in candles if c[4] > 0]
    avg_range = sum(ranges) / len(ranges)

    last = closes[-1]
    # Размах сетки в долях от цены
    span_pct = max(avg_range * mult * len(candles) ** 0.5, 0.02)  # min 2%
    span_pct = min(span_pct, 0.20)  # max 20%

    lower = round(last * (1 - span_pct), 2)
    upper = round(last * (1 + span_pct), 2)

    # Шаг сетки между уровнями ~ avg_range — чтобы свечи реально пересекали
    desired_step_abs = max(avg_range * last, last * 0.001)
    levels = max(min(int((upper - lower) / desired_step_abs) + 1, 50), 5)
    if levels_target:
        # подгоняем ближе к желаемому
        levels = max(min(levels_target, 50), 5)

    return {
        "symbol": symbol,
        "current_price": last,
        "lower_price": lower,
        "upper_price": upper,
        "grid_levels": levels,
        "span_pct": round(span_pct * 100, 2),
        "avg_hourly_range_pct": round(avg_range * 100, 3),
        "step_pct": round((upper - lower) / lower / max(levels - 1, 1) * 100, 3),
        "candles_used": len(candles),
    }
