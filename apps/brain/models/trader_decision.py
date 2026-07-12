from pydantic import BaseModel
from pydantic import Field


class TraderDecision(BaseModel):

    decision: str = Field(
        description="BUY | SELL | NONE"
    )

    confidence: int = Field(
        ge=0,
        le=100,
        description="AI confidence score"
    )