from pydantic import BaseModel


class RiskDecision(BaseModel):
    approved: bool
    risk_score: int