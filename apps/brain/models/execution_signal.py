from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExecutionSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal_id: str
    symbol: Literal["XAUUSD"]
    action: Literal["BUY", "SELL"]
    lot: float = Field(gt=0, le=0.50)
    tp_points: int = Field(gt=0)
    sl_points: int = Field(gt=0)
    protection_plan: dict | None = None
    ai_capital_profile: bool = False
    trailing_start_points: int = Field(default=0, ge=0)
    trailing_distance_points: int = Field(default=0, ge=0)
    trailing_step_points: int = Field(default=0, ge=0)
    review_move_points: int = Field(default=0, ge=0)
    cost_buffer_points: int = Field(default=0, ge=0)
    confidence: int = Field(ge=60, le=100)
    initial_score: int = Field(ge=70, le=100)
    entry_policy_version: int
    max_spread_points: float = Field(default=30, gt=0, le=150)
    small_equity_strict: bool = True
    max_sl_risk_percent: float = Field(default=0, ge=0, le=100)
    preclose_enabled: bool = False
    magic_number: int
    account_id: str
    terminal_id: str
    instance_id: str
    market_time: int
    created_at: datetime
    expires_at: datetime
    created_at_epoch: int
    expires_at_epoch: int
    status: Literal["PENDING"] = "PENDING"
