from pydantic import BaseModel


class ScoringResult(BaseModel):
    score: int
    qualified: bool

    trend_score: int
    momentum_score: int
    volume_score: int
    volatility_score: int
    session_score: int
    spread_score: int