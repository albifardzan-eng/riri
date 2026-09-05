from pydantic import BaseModel, Field


class ScoringResult(BaseModel):

    score: int = Field(
        ge=0,
        le=100
    )

    qualified: bool

    trend_score: int = Field(
        ge=0,
        le=20
    )

    momentum_score: int = Field(
        ge=0,
        le=15
    )

    volume_score: int = Field(
        ge=0,
        le=20
    )

    volatility_score: int = Field(
        ge=0,
        le=15
    )

    session_score: int = Field(
        ge=0,
        le=15
    )

    spread_score: int = Field(
        ge=0,
        le=15
    )

    rsi: float = Field(default=50.0, ge=0, le=100)

    reversal_score: int = Field(default=0, ge=0, le=100)
