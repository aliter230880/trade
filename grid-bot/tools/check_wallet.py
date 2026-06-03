"""Показать все монеты на Bybit Mainnet."""
import sys
sys.path.insert(0, "/app")
from backend.storage import get_api_key
from backend.exchange import make_client


rec = get_api_key(3)
c = make_client(rec["exchange"], rec["api_key"], rec["api_secret"],
                rec["passphrase"], rec["testnet"])
r = c.privateGetV5AccountWalletBalance({"accountType": "UNIFIED"})
for acc in r["result"]["list"]:
    print(f"Account: {acc['accountType']}")
    print(f"  Total equity: ${acc.get('totalEquity', 'n/a')}")
    for coin in acc["coin"]:
        bal = float(coin.get("walletBalance") or 0)
        if bal > 0:
            usd = coin.get("usdValue", "?")
            print(f"  {coin['coin']:8} = {bal:.6f}  (~${usd})")
