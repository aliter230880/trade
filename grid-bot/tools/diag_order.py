"""Тестовое размещение одного ордера на Bybit Demo."""

from backend.storage import get_api_key
from backend.exchange import (
    make_client,
    fetch_market_meta,
    fetch_ticker,
    bybit_place_order,
    bybit_cancel_all,
    fmt_step,
    round_step,
)


def main() -> None:
    rec = get_api_key(1)
    c = make_client(
        rec["exchange"], rec["api_key"], rec["api_secret"],
        rec["passphrase"], rec["testnet"],
    )
    symbol = "BTC/USDT"
    meta = fetch_market_meta(c, symbol)
    print("meta:", meta)

    ticker = fetch_ticker(c, symbol)
    last = ticker["last"]
    print("last:", last)

    # Buy на 5% ниже
    target_price = last * 0.95
    qty_step = meta["qty_step"]
    tick = meta["tick_size"]
    min_notional = meta["min_notional"]
    min_qty = meta["min_qty"]

    # Хотим 100 USDT
    quote = 100.0
    raw_qty = quote / target_price
    qty = round_step(raw_qty, qty_step)
    if qty < min_qty:
        qty = min_qty
    price = round_step(target_price, tick)

    print(f"will place buy: qty={fmt_step(qty,qty_step)} price={fmt_step(price,tick)} "
          f"notional={qty*price:.2f}")
    print(f"min_qty={min_qty} min_notional={min_notional}")

    try:
        order = bybit_place_order(c, symbol, "buy", qty, price,
                                  qty_step=qty_step, tick_size=tick)
        print("OK order id:", order.get("id"))
    except Exception as exc:
        print("FAIL:", exc)
        return

    # cleanup
    bybit_cancel_all(c, symbol)
    print("cancelled")


if __name__ == "__main__":
    main()
