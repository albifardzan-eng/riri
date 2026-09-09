from datetime import datetime, timezone

from config.settings import settings
from config.trading_config import (
    MAX_ACTIVE_TRADES, MAX_SPREAD, MAX_TOTAL_LOT, MIN_ATR,
    MIN_CONFIDENCE, MIN_ENTRY_INTERVAL_SECONDS,
)
from models.risk_decision import RiskDecision


class AIRisk:
    async def evaluate(self, market, trader_decision) -> RiskDecision:
        if trader_decision is None or trader_decision.decision == "NONE":
            return self._reject("NO_SIGNAL")
        if trader_decision.confidence < MIN_CONFIDENCE:
            return self._reject("CONFIDENCE_BELOW_60")
        if market.symbol != "XAUUSD":
            return self._reject("SYMBOL_NOT_ALLOWED")

        now = int(datetime.now(timezone.utc).timestamp())
        age = now - int(market.market_time)
        if age < 0 or age > settings.MAX_MARKET_AGE_SECONDS:
            return self._reject("STALE_MARKET_DATA")
        if market.free_margin <= 0:
            return self._reject("INSUFFICIENT_FREE_MARGIN")
        if market.spread > MAX_SPREAD:
            return self._reject("SPREAD_ABOVE_LIMIT")
        if market.atr < MIN_ATR:
            return self._reject("ATR_BELOW_LIMIT")

        positions = [position for position in market.positions if position.symbol == market.symbol]
        if len(positions) >= MAX_ACTIVE_TRADES:
            return self._reject("MAX_ACTIVE_TRADES")
        if sum(float(position.lot) for position in positions) >= MAX_TOTAL_LOT:
            return self._reject("MAX_TOTAL_LOT")

        opposite = "SELL" if trader_decision.decision == "BUY" else "BUY"
        if any(position.type == opposite for position in positions):
            return self._reject("HEDGING_FORBIDDEN")
        if any(position.type == trader_decision.decision and position.profit < 0 for position in positions):
            return self._reject("AVERAGING_FORBIDDEN")

        open_times = [int(position.open_time) for position in positions if position.open_time > 0]
        if open_times and now - max(open_times) < MIN_ENTRY_INTERVAL_SECONDS:
            return self._reject("MIN_ENTRY_INTERVAL")

        return RiskDecision(approved=True, risk_score=100, reason="PASS")

    @staticmethod
    def _reject(reason: str) -> RiskDecision:
        return RiskDecision(approved=False, risk_score=0, reason=reason)
