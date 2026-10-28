from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Candle(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
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
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
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
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
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


class PendingOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ticket: int = Field(gt=0)
    symbol: str
    type: str
    lot: float = Field(gt=0)
    open_price: float = Field(gt=0)
    sl: float = Field(ge=0)
    magic_number: int

    @model_validator(mode="after")
    def validate_order(self):
        if self.symbol != "XAUUSD" or self.type not in {"BUY", "SELL"}:
            raise ValueError("invalid pending order")
        return self


class BrokerSession(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    valid: bool = False
    close_time: int = Field(default=0, ge=0)
    next_open_time: int = Field(default=0, ge=0)
    weekly: bool = False

    @model_validator(mode="after")
    def validate_session(self):
        if self.valid and (self.close_time <= 0 or self.next_open_time <= self.close_time):
            raise ValueError("invalid broker session boundary")
        return self


class MarketData(BaseModel):
    """Strict, account-scoped MT5 snapshot consumed by the decision pipeline."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    symbol: str
    timeframe: str
    market_time: int = Field(gt=0)
    # Same broker clock as POSITION_TIME; legacy executors fail entry preflight.
    server_time: int = Field(default=0, ge=0)
    executor_policy_version: int = Field(default=0, ge=0)
    last_entry_server_time: int = Field(default=0, ge=0)
    history_ready: bool = False
    account_currency: str = ""
    tick_age_seconds: int = Field(default=0, ge=0)
    broker_session: BrokerSession = Field(default_factory=BrokerSession)
    pending_orders: list[PendingOrder] = Field(default_factory=list, max_length=100)
    timeframes: dict[str, list[Candle]] = Field(default_factory=dict)
    trade_allowed: bool = False
    hedging_account: bool = False
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
    volume_min: float = Field(default=0, ge=0)
    volume_max: float = Field(default=0, ge=0)
    volume_step: float = Field(default=0, ge=0)
    stops_level_points: int = Field(default=0, ge=0)
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
        if any(k not in {"M5", "M15", "H1", "H4"} or not 20 <= len(v) <= 120
               for k, v in self.timeframes.items()):
            raise ValueError("invalid multi-timeframe candles")
        if len({p.ticket for p in self.positions}) != len(self.positions):
            raise ValueError("duplicate position ticket")
        if len({p.ticket for p in self.pending_orders}) != len(self.pending_orders):
            raise ValueError("duplicate pending order ticket")
        if self.ask <= self.bid:
            raise ValueError("ask must be greater than bid")
        calculated = (self.ask - self.bid) / self.point
        if abs(calculated - self.spread) > 1.0:
            raise ValueError("spread does not match bid, ask, and point")
        return self

    @property
    def account_key(self) -> str:
        import json
        return json.dumps([self.terminal_id, self.account_id, self.symbol, 20260701], separators=(",", ":"))

    @property
    def identity_key(self) -> str:
        return f"{self.account_id}:{self.terminal_id}:{self.instance_id}"
