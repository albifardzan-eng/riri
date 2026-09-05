from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Candle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: int = Field(gt=0)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self):
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("invalid OHLC range")
        if self.low > self.high:
            raise ValueError("candle low exceeds high")
        return self


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket: int = Field(gt=0)
    symbol: str
    type: str
    lot: float = Field(gt=0)
    profit: float
    open_time: int = Field(ge=0)
    open_price: float = Field(gt=0)
    sl: float = Field(ge=0)
    tp: float = Field(ge=0)
    magic_number: int

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        value = value.upper()
        if value != "XAUUSD":
            raise ValueError("only XAUUSD positions are accepted")
        return value

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        value = value.upper()
        if value not in {"BUY", "SELL"}:
            raise ValueError("position type must be BUY or SELL")
        return value


class FundamentalData(BaseModel):
    model_config = ConfigDict(extra="forbid")
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

    @model_validator(mode="after")
    def validate_availability(self):
        if self.high_impact_news and not self.available:
            raise ValueError("news cannot be asserted when calendar data is unavailable")
        return self


class MarketData(BaseModel):
    """Strict, account-scoped MT5 snapshot consumed by the decision pipeline."""

    model_config = ConfigDict(extra="forbid")
    symbol: str
    timeframe: str
    market_time: int = Field(gt=0)
    account_id: str = Field(min_length=1, max_length=64)
    terminal_id: str = Field(min_length=1, max_length=128)
    instance_id: str = Field(min_length=1, max_length=128)
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    spread: float = Field(ge=0)
    point: float = Field(gt=0)
    digits: int = Field(ge=0, le=10)
    tick_size: float = Field(gt=0)
    tick_value: float = Field(ge=0)
    balance: float = Field(ge=0)
    equity: float = Field(ge=0)
    free_margin: float
    tick_volume: float = Field(ge=0)
    atr: float = Field(ge=0)
    candles: list[Candle] = Field(default_factory=list, min_length=100, max_length=500)
    positions: list[Position] = Field(default_factory=list, max_length=100)
    fundamental: FundamentalData = Field(default_factory=FundamentalData)

    @field_validator("symbol")
    @classmethod
    def xauusd_only(cls, value: str) -> str:
        value = value.upper()
        if value != "XAUUSD":
            raise ValueError("RIRI v1 accepts XAUUSD only")
        return value

    @field_validator("timeframe")
    @classmethod
    def supported_timeframe(cls, value: str) -> str:
        value = value.upper()
        if value not in {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}:
            raise ValueError("unsupported timeframe")
        return value

    @model_validator(mode="after")
    def validate_quote(self):
        if self.ask <= self.bid:
            raise ValueError("ask must be greater than bid")
        calculated = (self.ask - self.bid) / self.point
        if abs(calculated - self.spread) > 1.0:
            raise ValueError("spread does not match bid, ask, and point")
        return self

    @property
    def identity_key(self) -> str:
        return f"{self.account_id}:{self.terminal_id}:{self.instance_id}"
