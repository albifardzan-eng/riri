import math
import uuid
from datetime import datetime, timedelta, timezone

from config.settings import settings
from config.trading_config import (
    DEFAULT_LOT, EQUITY_STEP, LOT_STEP, MAX_ACTIVE_TRADES, MAX_TOTAL_LOT,
    MAX_SPREAD, MIN_ATR, MIN_CONFIDENCE, MIN_ENTRY_INTERVAL_SECONDS,
    SL_POINTS, TP_POINTS,
)
from models.execution import ExecutionResult
from models.execution_signal import ExecutionSignal
from services.signal_store import signal_store


class ExecutionService:
    """Creates a signal only after independently rechecking every hard rule."""

    async def execute(self, decision, risk, market) -> ExecutionResult:
        rejected = self._preflight_reason(decision, risk, market)
        if rejected:
            return self._result(rejected)

        if signal_store.get_signal(market.identity_key) is not None:
            return self._result("SIGNAL_PENDING")

        positions = [position for position in market.positions if position.symbol == market.symbol]
        active_lot = sum(float(position.lot) for position in positions)
        lot = round(DEFAULT_LOT + math.floor(market.equity / EQUITY_STEP) * LOT_STEP, 2)
        remaining_lot = max(0.0, MAX_TOTAL_LOT - active_lot)
        remaining_lot = math.floor((remaining_lot + 1e-9) * 100) / 100
        lot = min(lot, remaining_lot, MAX_TOTAL_LOT)
        if lot <= 0:
            return self._result("INVALID_OR_EXHAUSTED_LOT")

        now = datetime.now(timezone.utc)
        signal = ExecutionSignal(
            signal_id=str(uuid.uuid4()),
            symbol=market.symbol,
            action=decision.decision,
            lot=lot,
            tp_points=TP_POINTS,
            sl_points=SL_POINTS,
            confidence=decision.confidence,
            account_id=market.account_id,
            terminal_id=market.terminal_id,
            instance_id=market.instance_id,
            market_time=market.market_time,
            created_at=now,
            expires_at=now + timedelta(seconds=settings.SIGNAL_EXPIRY_SECONDS),
            created_at_epoch=int(now.timestamp()),
            expires_at_epoch=int(now.timestamp()) + settings.SIGNAL_EXPIRY_SECONDS,
        )
        signal_store.set_signal(market.identity_key, signal)
        return ExecutionResult(
            signal_created=True,
            order_type=decision.decision,
            lot=lot,
            reason="SIGNAL_CREATED",
            signal_id=signal.signal_id,
        )

    @staticmethod
    def _preflight_reason(decision, risk, market) -> str | None:
        if decision is None:
            return "NO_DECISION"
        if decision.decision not in {"BUY", "SELL"}:
            return "NO_SIGNAL"
        if decision.confidence < MIN_CONFIDENCE:
            return "CONFIDENCE_BELOW_70"
        if risk is None or not risk.approved:
            return "RISK_REJECTED"
        if market.symbol != "XAUUSD":
            return "SYMBOL_NOT_ALLOWED"
        now = int(datetime.now(timezone.utc).timestamp())
        age = now - int(market.market_time)
        if age < 0 or age > settings.MAX_MARKET_AGE_SECONDS:
            return "STALE_MARKET_DATA"
        if market.free_margin <= 0:
            return "INSUFFICIENT_FREE_MARGIN"
        if market.spread > MAX_SPREAD:
            return "SPREAD_ABOVE_LIMIT"
        if market.atr < MIN_ATR:
            return "ATR_BELOW_LIMIT"

        positions = [position for position in market.positions if position.symbol == market.symbol]
        if len(positions) >= MAX_ACTIVE_TRADES:
            return "MAX_ACTIVE_TRADES"
        if sum(float(position.lot) for position in positions) >= MAX_TOTAL_LOT:
            return "MAX_TOTAL_LOT"
        opposite = "SELL" if decision.decision == "BUY" else "BUY"
        if any(position.type == opposite for position in positions):
            return "HEDGING_FORBIDDEN"
        if any(position.type == decision.decision and position.profit < 0 for position in positions):
            return "AVERAGING_FORBIDDEN"
        open_times = [int(position.open_time) for position in positions if position.open_time > 0]
        if open_times and now - max(open_times) < MIN_ENTRY_INTERVAL_SECONDS:
            return "MIN_ENTRY_INTERVAL"
        return None

    @staticmethod
    def _result(reason: str) -> ExecutionResult:
        return ExecutionResult(signal_created=False, order_type="NONE", lot=0.0, reason=reason)
