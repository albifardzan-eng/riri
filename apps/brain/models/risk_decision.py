from pydantic import BaseModel, Field


class RiskDecision(BaseModel):
    """
    Final risk decision produced by AI Risk.

    AI Risk is the final gate before a trading signal
    can be sent to MT5.

    A trade can only proceed when:
        approved == True

    risk_score is a normalized score from 0-100.

    reason contains a machine-readable explanation
    suitable for logs, dashboard and trade journal.
    """

    approved: bool = Field(
        description=(
            "Whether the proposed trade is approved "
            "by the risk engine."
        )
    )

    risk_score: int = Field(
        ge=0,
        le=100,
        description=(
            "Normalized risk approval score from 0 to 100."
        )
    )

    reason: str = Field(
        min_length=1,
        description=(
            "Machine-readable reason for the risk decision."
        )
    )