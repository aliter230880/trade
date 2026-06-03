from backend.storage import get_api_key
from backend.exchange import make_client, suggest_grid_range, fetch_ohlcv

rec = get_api_key(1)
c = make_client(rec["exchange"], rec["api_key"], rec["api_secret"],
                rec["passphrase"], rec["testnet"])

# Сначала проверим что свечи берутся
print("Тест свечей по разным монетам:")
for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", "MATIC/USDT"]:
    try:
        c1h = fetch_ohlcv(c, sym, "5m", limit=10)
        print(f"  {sym}: {len(c1h)} свечей, last close={c1h[-1][4] if c1h else 'нет'}")
    except Exception as e:
        print(f"  {sym}: ERR {str(e)[:80]}")
