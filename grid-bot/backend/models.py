"""Pydantic-модели API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


SUPPORTED_EXCHANGES = ("bybit", "okx", "bitget", "mexc", "kucoin", "gateio", "binance")
ExchangeName = Literal["bybit", "okx", "bitget", "mexc", "kucoin", "gateio", "binance"]


class ApiKeyIn(BaseModel):
    exchange: ExchangeName
    api_key: str
    api_secret: str
    passphrase: str = ""  # нужен для OKX, KuCoin
    testnet: bool = True
    label: str = "default"


class ApiKeyOut(BaseModel):
    id: int
    exchange: str
    label: str
    testnet: bool
    masked_key: str
    created_at: datetime


class ExchangeStatus(BaseModel):
    exchange: str
    testnet: bool
    connected: bool
    balance_usdt: Optional[float] = None
    error: Optional[str] = None


class GridConfigIn(BaseModel):
    """Параметры grid-стратегии."""

    api_key_id: int
    symbol: str = Field(..., description="Например BTC/USDT")
    lower_price: float = Field(..., gt=0)
    upper_price: float = Field(..., gt=0)
    grid_levels: int = Field(..., ge=3, le=200)
    order_size_quote: float = Field(..., gt=0, description="Размер ордера в USDT")
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None


class GridBotOut(BaseModel):
    id: int
    api_key_id: int
    exchange: str
    symbol: str
    lower_price: float
    upper_price: float
    grid_levels: int
    order_size_quote: float
    status: str  # idle, running, stopped, error
    realized_pnl: float
    open_orders: int
    filled_orders: int
    created_at: datetime
    started_at: Optional[datetime]


class TickerOut(BaseModel):
    symbol: str
    last: float
    bid: float
    ask: float
    timestamp: int


class ApiResponse(BaseModel):
    ok: bool = True
    message: str = ""
