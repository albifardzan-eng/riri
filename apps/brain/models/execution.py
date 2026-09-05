from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionResult(BaseModel):
    signal_created: bool
    order_type: str
    lot: float
    reason: str
    signal_id: str | None = None


class ExecutionConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal_id: str
    status: Literal["EXECUTED", "REJECTED"]
    action: Literal["BUY", "SELL"]
    order_id: int = Field(default=0, ge=0)
    deal_id: int = Field(default=0, ge=0)
    requested_lot: float = Field(default=0.0, ge=0, le=0.50)
    filled_lot: float = Field(default=0.0, ge=0, le=0.50)
    executed_price: float = Field(default=0.0, ge=0)
    retcode: int = Field(default=0, ge=0)
    reason: str = ""

    @model_validator(mode="after")
    def validate_outcome(self):
        if self.status == "EXECUTED" and self.filled_lot <= 0:
            raise ValueError("executed confirmation requires filled_lot")
        if self.status == "REJECTED" and self.filled_lot != 0:
            raise ValueError("rejected confirmation cannot contain filled_lot")
        if self.filled_lot > self.requested_lot:
            raise ValueError("filled_lot exceeds requested_lot")
        return self


class TradeCloseEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["CLOSED"]
    deal_id: int = Field(gt=0)
    order_id: int = Field(ge=0)
    position_id: int = Field(ge=0)
    symbol: Literal["XAUUSD"]
    side: Literal["BUY", "SELL"]
    lot: float = Field(gt=0, le=0.50)
    price: float = Field(gt=0)
    profit: float
    event_time: int = Field(gt=0)
