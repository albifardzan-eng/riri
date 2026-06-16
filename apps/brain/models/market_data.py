from pydantic import BaseModel


class Candle(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float


class Position(BaseModel):
    ticket: int
    symbol: str
    type: str
    lot: float
    profit: float


class MarketData(BaseModel):
    symbol: str

    bid: float
    ask: float

    spread: float

    balance: float
    equity: float
    free_margin: float

    tick_volume: float
    atr: float

    candles: list[Candle] = []

    positions: list[Position] = []