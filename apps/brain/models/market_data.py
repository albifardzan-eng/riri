from pydantic import BaseModel, Field


class Candle(BaseModel):
    """
    OHLCV candle.
    """

    time: int = 0

    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0


class Position(BaseModel):
    """
    Currently open MT5 position.
    """

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
    """
    Fundamental and economic-calendar information.

    The current RIRI implementation may not have an
    external news provider yet, therefore all fields
    have safe defaults.
    """

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
    """
    Complete market snapshot received from MT5.

    This object is the primary market-state contract
    consumed by scoring, statistics, pattern,
    fundamental and risk services.
    """

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