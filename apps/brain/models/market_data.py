from pydantic import BaseModel, Field


class Candle(BaseModel):

    time: int = 0

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

    open_time: int = 0

    open_price: float = 0.0

    sl: float = 0.0

    tp: float = 0.0


class FundamentalData(BaseModel):

    available: bool = False

    high_impact_news: bool = False

    event: str | None = None

    currency: str = "USD"

    impact: str = "NONE"

    phase: str | None = None

    minutes_to_news: int | None = None

    news_time: int | None = None

    event_id: int | None = None

    actual: float | None = None

    forecast: float | None = None

    previous: float | None = None


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

    candles: list[Candle] = Field(
        default_factory=list
    )

    positions: list[Position] = Field(
        default_factory=list
    )

    fundamental: FundamentalData = Field(
        default_factory=FundamentalData
    )