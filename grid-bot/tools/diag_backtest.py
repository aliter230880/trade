"""Диагностика бэктеста."""
from backend.storage import get_api_key
from backend.exchange import make_client
from backend.backtest import run_backtest, result_to_dict


def run(days: int, timeframe: str = "5m"):
    rec = get_api_key(1)
    c = make_client(rec["exchange"], rec["api_key"], rec["api_secret"],
                    rec["passphrase"], rec["testnet"])
    res = run_backtest(
        c, "BTC/USDT",
        lower_price=69200, upper_price=82665, grid_levels=12,
        order_size_quote=100, days=days, timeframe=timeframe,
        fee_rate=0.001,
    )
    d = result_to_dict(res)
    print(f"\n=== {days} дней, tf={d['timeframe']} ===")
    print(f"  свечей: {d['candles_used']}")
    print(f"  start price: {d['start_price']:.2f} → end: {d['end_price']:.2f} "
          f"({d['price_change_pct']:+.2f}%)")
    print(f"  всего сделок: {d['total_trades']} (закрытых пар: {d['matched_pairs']})")
    print(f"  Realized PnL: {d['realized_pnl_usdt']:+.4f} USDT")
    print(f"  Комиссии: {d['fees_paid_usdt']:.4f} USDT")
    print(f"  Доходность от капитала: {d['pnl_pct_on_capital']:+.3f}%")
    print(f"  В пересчёте на месяц: {d['estimated_monthly_pct']:+.2f}%")
    print(f"  Max drawdown: {d['max_drawdown_pct']:.2f}%")


if __name__ == "__main__":
    run(7, "5m")
    run(30, "5m")
    run(90, "5m")
