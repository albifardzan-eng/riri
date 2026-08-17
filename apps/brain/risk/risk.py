from datetime import datetime, timezone

from models.risk_decision import RiskDecision

from config.trading_config import (
    MAX_ACTIVE_TRADES,
    MAX_TOTAL_LOT
)


# ==================================================
# RISK CONFIGURATION
# ==================================================

MIN_ENTRY_INTERVAL_SECONDS = 30 * 60

MIN_FREE_MARGIN = 0.0

MAX_SPREAD = 30.0

MIN_ATR = 1.0


class AIRisk:

    async def evaluate(
        self,
        market,
        trader_decision
    ) -> RiskDecision:

        # ==================================================
        # NO TRADER DECISION
        # ==================================================

        if trader_decision is None:

            return RiskDecision(
                approved=False,
                risk_score=0,
                reason="NO_TRADER_DECISION"
            )

        # ==================================================
        # NO SIGNAL
        # ==================================================

        if trader_decision.decision == "NONE":

            return RiskDecision(
                approved=False,
                risk_score=0,
                reason="NO_SIGNAL"
            )

        # ==================================================
        # POSITIONS
        # ==================================================

        positions = market.positions

        active_trades = len(
            positions
        )

        total_lot = sum(
            float(position.lot)
            for position in positions
        )

        total_lot = round(
            total_lot,
            2
        )

        # ==================================================
        # MAX ACTIVE TRADES
        # ==================================================

        if active_trades >= MAX_ACTIVE_TRADES:

            return RiskDecision(
                approved=False,
                risk_score=0,
                reason="MAX_ACTIVE_TRADES"
            )

        # ==================================================
        # MAX TOTAL LOT
        # ==================================================

        if total_lot >= MAX_TOTAL_LOT:

            return RiskDecision(
                approved=False,
                risk_score=0,
                reason="MAX_TOTAL_LOT"
            )

        # ==================================================
        # MINIMUM ENTRY INTERVAL
        #
        # Existing newest position must be at least
        # 30 minutes old before a new position is allowed.
        # ==================================================

        if active_trades > 0:

            latest_open_time = max(
                (
                    int(position.open_time)
                    for position in positions
                    if position.open_time > 0
                ),
                default=0
            )

            if latest_open_time > 0:

                now = int(
                    datetime.now(
                        timezone.utc
                    ).timestamp()
                )

                elapsed_seconds = (
                    now -
                    latest_open_time
                )

                if elapsed_seconds < 0:

                    elapsed_seconds = 0

                if (
                    elapsed_seconds
                    < MIN_ENTRY_INTERVAL_SECONDS
                ):

                    remaining_seconds = (
                        MIN_ENTRY_INTERVAL_SECONDS
                        - elapsed_seconds
                    )

                    remaining_minutes = max(
                        1,
                        int(
                            (
                                remaining_seconds
                                + 59
                            ) / 60
                        )
                    )

                    return RiskDecision(
                        approved=False,
                        risk_score=0,
                        reason=(
                            "MIN_ENTRY_INTERVAL_"
                            f"{remaining_minutes}MIN"
                        )
                    )

        # ==================================================
        # MARKET RISK DATA
        # ==================================================

        free_margin = float(
            market.free_margin
        )

        spread = float(
            market.spread
        )

        atr = float(
            market.atr
        )

        # ==================================================
        # BASE RISK SCORE
        # ==================================================

        score = 100

        reasons = []

        # ==================================================
        # FREE MARGIN
        # ==================================================

        if free_margin < MIN_FREE_MARGIN:

            score -= 30

            reasons.append(
                "LOW_MARGIN"
            )

        # ==================================================
        # SPREAD
        # ==================================================

        if spread > MAX_SPREAD:

            score -= 20

            reasons.append(
                "HIGH_SPREAD"
            )

        # ==================================================
        # VOLATILITY
        # ==================================================

        if atr < MIN_ATR:

            score -= 10

            reasons.append(
                "LOW_VOLATILITY"
            )

        # ==================================================
        # NORMALIZE
        # ==================================================

        score = max(
            0,
            min(
                100,
                score
            )
        )

        # ==================================================
        # APPROVAL
        # ==================================================

        approved = (
            score >= 70
        )

        # ==================================================
        # REASON
        # ==================================================

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