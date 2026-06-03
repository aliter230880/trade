"""SQLite хранилище: API-ключи (зашифрованы), боты, ордера."""

import base64
import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

from .config import settings


def _make_fernet(secret: str) -> Fernet:
    """Делает стабильный ключ Fernet из произвольной строки."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


_fernet = _make_fernet(settings.encryption_key)


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value: str) -> str:
    return _fernet.decrypt(value.encode("ascii")).decode("utf-8")


SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange      TEXT NOT NULL,
    label         TEXT NOT NULL DEFAULT 'default',
    testnet       INTEGER NOT NULL DEFAULT 1,
    api_key_enc   TEXT NOT NULL,
    api_secret_enc TEXT NOT NULL,
    passphrase_enc TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grid_bots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_id      INTEGER NOT NULL,
    exchange        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    lower_price     REAL NOT NULL,
    upper_price     REAL NOT NULL,
    grid_levels     INTEGER NOT NULL,
    order_size_quote REAL NOT NULL,
    take_profit_pct REAL,
    stop_loss_pct   REAL,
    status          TEXT NOT NULL DEFAULT 'idle',
    realized_pnl    REAL NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bot_orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id       INTEGER NOT NULL,
    exchange_order_id TEXT,
    side         TEXT NOT NULL,
    price        REAL NOT NULL,
    amount       REAL NOT NULL,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    filled_at    TEXT,
    fill_price   REAL,
    fill_qty     REAL,
    fee          REAL DEFAULT 0,
    fee_coin     TEXT DEFAULT '',
    realized_pnl REAL DEFAULT 0,
    pair_buy_id  INTEGER,
    FOREIGN KEY (bot_id) REFERENCES grid_bots(id) ON DELETE CASCADE
);
"""


# Миграция: добавляем колонки в существующую БД (если запускается на старой)
_MIGRATIONS = [
    "ALTER TABLE bot_orders ADD COLUMN fill_price REAL",
    "ALTER TABLE bot_orders ADD COLUMN fill_qty REAL",
    "ALTER TABLE bot_orders ADD COLUMN fee REAL DEFAULT 0",
    "ALTER TABLE bot_orders ADD COLUMN fee_coin TEXT DEFAULT ''",
    "ALTER TABLE bot_orders ADD COLUMN realized_pnl REAL DEFAULT 0",
    "ALTER TABLE bot_orders ADD COLUMN pair_buy_id INTEGER",
    "ALTER TABLE bot_orders ADD COLUMN level_index INTEGER",
]


def init_db(db_path: Path = settings.db_path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        # Применяем миграции, игнорируя ошибки "duplicate column"
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# -------- API keys --------

def save_api_key(
    exchange: str, api_key: str, api_secret: str, passphrase: str, testnet: bool, label: str
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO api_keys (exchange, label, testnet, api_key_enc, api_secret_enc,
                                  passphrase_enc, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exchange,
                label,
                1 if testnet else 0,
                encrypt(api_key),
                encrypt(api_secret),
                encrypt(passphrase or ""),
                datetime.utcnow().isoformat(),
            ),
        )
        return cur.lastrowid


def list_api_keys() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, exchange, label, testnet, api_key_enc, created_at FROM api_keys "
            "ORDER BY id DESC"
        ).fetchall()
    out = []
    for r in rows:
        api_key = decrypt(r["api_key_enc"])
        masked = api_key[:4] + "*" * max(0, len(api_key) - 8) + api_key[-4:]
        out.append(
            {
                "id": r["id"],
                "exchange": r["exchange"],
                "label": r["label"],
                "testnet": bool(r["testnet"]),
                "masked_key": masked,
                "created_at": datetime.fromisoformat(r["created_at"]),
            }
        )
    return out


def get_api_key(key_id: int) -> Optional[dict]:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?", (key_id,)
        ).fetchone()
    if not r:
        return None
    return {
        "id": r["id"],
        "exchange": r["exchange"],
        "label": r["label"],
        "testnet": bool(r["testnet"]),
        "api_key": decrypt(r["api_key_enc"]),
        "api_secret": decrypt(r["api_secret_enc"]),
        "passphrase": decrypt(r["passphrase_enc"]) if r["passphrase_enc"] else "",
    }


def delete_api_key(key_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))


# -------- Grid bots --------

def create_grid_bot(cfg: dict) -> int:
    rec = get_api_key(cfg["api_key_id"])
    if not rec:
        raise ValueError("API ключ не найден")
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO grid_bots
               (api_key_id, exchange, symbol, lower_price, upper_price,
                grid_levels, order_size_quote, take_profit_pct, stop_loss_pct,
                status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'idle', ?)""",
            (
                cfg["api_key_id"],
                rec["exchange"],
                cfg["symbol"],
                cfg["lower_price"],
                cfg["upper_price"],
                cfg["grid_levels"],
                cfg["order_size_quote"],
                cfg.get("take_profit_pct"),
                cfg.get("stop_loss_pct"),
                datetime.utcnow().isoformat(),
            ),
        )
        return cur.lastrowid


def _row_to_bot(r) -> dict:
    open_count = filled_count = 0
    with get_conn() as conn:
        c = conn.execute(
            "SELECT status, COUNT(*) c FROM bot_orders WHERE bot_id=? GROUP BY status",
            (r["id"],),
        ).fetchall()
    for row in c:
        if row["status"] == "open":
            open_count = row["c"]
        elif row["status"] == "filled":
            filled_count = row["c"]
    return {
        "id": r["id"],
        "api_key_id": r["api_key_id"],
        "exchange": r["exchange"],
        "symbol": r["symbol"],
        "lower_price": r["lower_price"],
        "upper_price": r["upper_price"],
        "grid_levels": r["grid_levels"],
        "order_size_quote": r["order_size_quote"],
        "status": r["status"],
        "realized_pnl": r["realized_pnl"],
        "open_orders": open_count,
        "filled_orders": filled_count,
        "created_at": datetime.fromisoformat(r["created_at"]),
        "started_at": datetime.fromisoformat(r["started_at"]) if r["started_at"] else None,
    }


def list_grid_bots() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM grid_bots ORDER BY id DESC").fetchall()
    return [_row_to_bot(r) for r in rows]


def get_grid_bot(bot_id: int) -> Optional[dict]:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM grid_bots WHERE id=?", (bot_id,)).fetchone()
    return _row_to_bot(r) if r else None


def delete_grid_bot(bot_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM grid_bots WHERE id=?", (bot_id,))


def list_bot_orders(bot_id: int, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, side, price, amount, status, created_at, filled_at, "
            "fill_price, fill_qty, fee, fee_coin, realized_pnl, pair_buy_id, level_index "
            "FROM bot_orders WHERE bot_id=? ORDER BY id DESC LIMIT ?",
            (bot_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def list_filled_trades(bot_id: int, limit: int = 100) -> list[dict]:
    """Только закрытые ордера — для истории сделок и P&L."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, side, price, amount, status, created_at, filled_at, "
            "fill_price, fill_qty, fee, fee_coin, realized_pnl, pair_buy_id, level_index "
            "FROM bot_orders WHERE bot_id=? AND status='filled' "
            "ORDER BY filled_at DESC LIMIT ?",
            (bot_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def find_oldest_unmatched_buy(bot_id: int) -> Optional[dict]:
    """Находит самый старый исполненный buy, для которого ещё нет парного sell.

    Используется при FIFO-расчёте P&L: когда sell исполняется, мы
    привязываем его к buy и фиксируем точную прибыль.
    """
    with get_conn() as conn:
        r = conn.execute(
            """SELECT bo.id, bo.fill_price, bo.fill_qty, bo.fee
               FROM bot_orders bo
               WHERE bo.bot_id = ? AND bo.side = 'buy' AND bo.status = 'filled'
                 AND NOT EXISTS (
                     SELECT 1 FROM bot_orders s
                     WHERE s.pair_buy_id = bo.id
                 )
               ORDER BY bo.filled_at ASC
               LIMIT 1""",
            (bot_id,),
        ).fetchone()
    return dict(r) if r else None


def update_order_fill(
    order_id: int,
    fill_price: float,
    fill_qty: float,
    fee: float = 0,
    fee_coin: str = "",
    realized_pnl: float = 0,
    pair_buy_id: Optional[int] = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE bot_orders
               SET status='filled', filled_at=?, fill_price=?, fill_qty=?,
                   fee=?, fee_coin=?, realized_pnl=?, pair_buy_id=?
               WHERE id=?""",
            (
                datetime.utcnow().isoformat(),
                fill_price,
                fill_qty,
                fee,
                fee_coin,
                realized_pnl,
                pair_buy_id,
                order_id,
            ),
        )


def update_order_fill_v2(
    order_id: int,
    fill_price: float,
    fill_qty: float,
    fee: float = 0,
    fee_coin: str = "",
    realized_pnl: float = 0,
) -> None:
    """Версия для level-to-level matching: без pair_buy_id (не используется)."""
    with get_conn() as conn:
        conn.execute(
            """UPDATE bot_orders
               SET status='filled', filled_at=?, fill_price=?, fill_qty=?,
                   fee=?, fee_coin=?, realized_pnl=?
               WHERE id=?""",
            (
                datetime.utcnow().isoformat(),
                fill_price,
                fill_qty,
                fee,
                fee_coin,
                realized_pnl,
                order_id,
            ),
        )
