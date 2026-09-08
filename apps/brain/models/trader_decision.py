from typing import Literal

from pydantic import BaseModel, Field


class TraderDecision(BaseModel):
    """
    Decision produced by AI Trader.

    The AI Trader may identify a normal trend trade
    or a reversal opportunity.

    The execution layer must only receive BUY or SELL.
    REVERSAL is represented separately through
    strategy and reason fields.
    """

    decision: Literal[
        "BUY",
        "SELL",
        "NONE"
    ] = Field(
        description="Final trading direction."
    )

    confidence: int = Field(
        ge=0,
        le=100,
        description="AI confidence score from 0 to 100."
    )

    # Backend-generated diagnostics, never requested from the model or sent
    # as instructions to MT5. UNKNOWN preserves the meaning of legacy rows.
    status: Literal["UNKNOWN", "COMPLETED", "FILTERED", "ERROR", "UNAVAILABLE"] = "UNKNOWN"
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)

    strategy: Literal[
        "TREND",
        "REVERSAL",
        "NONE"
    ] = Field(
        default="NONE",
        description=(
            "Trading strategy behind the decision."
        )
    )

    reason: str = Field(
        default="",
        description=(
            "Concise explanation of the trading decision."
        )
    )
