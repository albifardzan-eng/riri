from models.risk_decision import RiskDecision
from scoring.scoring_engine import ScoringEngine
from services.entry_eligibility import entry_rejection


class AIRisk:
    async def evaluate(self, market, trader_decision, *, initial_score: int | None = None) -> RiskDecision:
        score = ScoringEngine().calculate(market).score
        if initial_score is not None:
            score = min(score, initial_score)
        reason = entry_rejection(market, trader_decision, initial_score=score)
        return RiskDecision(approved=reason is None, risk_score=0 if reason else 100,
                            reason=reason or "PASS")
