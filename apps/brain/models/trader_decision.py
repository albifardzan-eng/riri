from pydantic import BaseModel


class TraderDecision(BaseModel):
    decision: str
    confidence: int