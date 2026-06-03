"""Диагностика баланса Bybit demo через ccxt."""

from backend.storage import get_api_key
from backend.exchange import make_client


def main() -> None:
    rec = get_api_key(1)
    c = make_client(
        rec["exchange"], rec["api_key"], rec["api_secret"],
        rec["passphrase"], rec["testnet"],
    )

    print("--- ccxt id:", c.id)
    print("--- API url:", c.urls.get("api"))

    # Прямой вызов v5 endpoint (минуя обёртку fetch_balance)
    print("\n--- direct privateGetV5AccountWalletBalance ---")
    try:
        r = c.privateGetV5AccountWalletBalance({"accountType": "UNIFIED"})
        print("retCode:", r.get("retCode"), "retMsg:", r.get("retMsg"))
        result = r.get("result", {})
        for acc in result.get("list", []):
            print("  accountType:", acc.get("accountType"),
                  "totalEquity:", acc.get("totalEquity"))
            for coin in acc.get("coin", []):
                if coin.get("coin") in ("USDT", "USDC", "BTC", "ETH"):
                    print(f"    {coin['coin']}: walletBalance={coin.get('walletBalance')} "
                          f"equity={coin.get('equity')} usdValue={coin.get('usdValue')}")
    except Exception as exc:
        print("ERR:", exc)

    print("\n--- ccxt fetch_balance variants ---")
    for params in [{}, {"accountType": "UNIFIED"}, {"type": "unified"}, {"type": "spot"}]:
        try:
            b = c.fetch_balance(params)
            usdt = (b.get("total") or {}).get("USDT")
            print(f"params={params}  USDT={usdt}")
        except Exception as exc:
            print(f"params={params}  ERR: {str(exc)[:120]}")


if __name__ == "__main__":
    main()
