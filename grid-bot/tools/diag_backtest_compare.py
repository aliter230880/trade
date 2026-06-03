"""Сравнение бэктеста по разным монетам."""
from backend.storage import get_api_key
from backend.exchange import make_client, suggest_grid_range
from backend.backtest import run_backtest, result_to_dict


def test(symbol: str, days: int = 30):
    rec = get_api_key(1)
    c = make_client(rec["exchange"], rec["api_key"], rec["api_secret"],
                    rec["passphrase"], rec["testnet"])
    # авто-параметры от текущей цены
    sg = suggest_grid_range(c, symbol, days=7, mult=1.5, levels_target=15)
    res = run_backtest(
        c, symbol,
        lower_price=sg["lower_price"], upper_price=sg["upper_price"],
        grid_levels=sg["grid_levels"],
        order_size_quote=100, days=days, timeframe="5m",
        fee_rate=0.001,
    )
    d = result_to_dict(res)
    print(f"{symbol:12} {d['timeframe']:>4} | "
          f"start {d['start_price']:>10.4f} → end {d['end_price']:>10.4f} "
          f"({d['price_change_pct']:+6.2f}%) | "
          f"trades={d['total_trades']:>3}, pairs={d['matched_pairs']:>3} | "
          f"PnL {d['realized_pnl_usdt']:+8.2f}$ | "
          f"мес {d['estimated_monthly_pct']:+6.2f}% | "
          f"DD {d['max_drawdown_pct']:5.2f}%")


if __name__ == "__main__":
    print("Период: 30 дней, 1500 USDT капитала, 100 USDT/уровень, 0.1% комиссия\n")
    print(f"{'Symbol':12} {'TF':>4} | {'Старт цена':>12} → {'Конец':>12} "
          f"({'Δ':>5}) | {'trades':>15} | {'P&L':>11} | "
          f"{'%/мес':>9} | {'DD':>6}")
    print("-" * 130)
    for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", "XRP/USDT",
                "LINK/USDT", "AVAX/USDT", "MATIC/USDT", "ARB/USDT", "OP/USDT"]:
        try:
            test(sym, days=30)
        except Exception as e:
            print(f"{sym:12}  ERR: {str(e)[:80]}")
