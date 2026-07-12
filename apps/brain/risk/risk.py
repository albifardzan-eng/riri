from models.risk_decision import RiskDecision

from config.trading_config import (
    MAX_ACTIVE_TRADES,
    MAX_TOTAL_LOT
)


class AIRisk:

    async def evaluate(
        self,
        market,
        trader_decision
    ) -> RiskDecision:

        if trader_decision is None:

            return RiskDecision(
                approved=False,
                risk_score=0,
                reason="NO_TRADER_DECISION"
            )

        if trader_decision.decision == "NONE":

            return RiskDecision(
                approved=False,
                risk_score=0,
                reason="NO_SIGNAL"
            )

        active_trades = len(
            market.positions
        )

        total_lot = sum(
            position.lot
            for position
            in market.positions
        )

        free_margin = (
            market.free_margin
        )

        spread = (
            market.spread
        )

        atr = (
            market.atr
        )

        score = 100

        reasons = []

        if active_trades >= MAX_ACTIVE_TRADES:

            score -= 50

            reasons.append(
                "MAX_ACTIVE_TRADES"
            )

        if total_lot >= MAX_TOTAL_LOT:

            score -= 40

            reasons.append(
                "MAX_TOTAL_LOT"
            )

        if free_margin < 100:

            score -= 30

            reasons.append(
                "LOW_MARGIN"
            )

        if spread > 30:

            score -= 20

            reasons.append(
                "HIGH_SPREAD"
            )

        if atr < 1:

            score -= 10

            reasons.append(
                "LOW_VOLATILITY"
            )

        score = max(
            0,
            min(
                score,
                100
            )
        )

        approved = (
            score >= 70
        )

        if not reasons:

            reasons.append(
                "PASS"
            )

        return RiskDecision(
            approved=approved,
            risk_score=score,
            reason=", ".join(
                reasons
            )
        )