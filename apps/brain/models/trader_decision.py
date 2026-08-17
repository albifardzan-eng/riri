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