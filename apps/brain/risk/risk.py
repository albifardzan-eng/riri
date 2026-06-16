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
                risk_score=0
            )

        positions = market.positions

        active_trades = len(
            positions
        )

        total_lot = sum(
            p.lot
            for p in positions
        )

        if active_trades >= MAX_ACTIVE_TRADES:

            return RiskDecision(
                approved=False,
                risk_score=20
            )

        if total_lot >= MAX_TOTAL_LOT:

            return RiskDecision(
                approved=False,
                risk_score=20
            )

        if market.free_margin <= 0:

            return RiskDecision(
                approved=False,
                risk_score=10
            )

        risk_score = 90

        return RiskDecision(
            approved=True,
            risk_score=risk_score
        )