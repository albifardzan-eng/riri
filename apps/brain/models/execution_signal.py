from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExecutionSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal_id: str
    symbol: Literal["XAUUSD"]
    action: Literal["BUY", "SELL"]
    lot: float = Field(gt=0, le=0.50)
    tp_points: int
    sl_points: int
    confidence: int = Field(ge=70, le=100)
    account_id: str
    terminal_id: str
    instance_id: str
    market_time: int
    created_at: datetime
    expires_at: datetime
    created_at_epoch: int
    expires_at_epoch: int
    status: Literal["PENDING"] = "PENDING"
