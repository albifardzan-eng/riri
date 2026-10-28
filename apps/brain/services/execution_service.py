import math
import uuid
from datetime import datetime, timedelta, timezone

from config.settings import settings
from config.trading_config import (
    DEFAULT_LOT, EQUITY_STEP, LOT_STEP, MAX_TOTAL_LOT,
    ENTRY_POLICY_VERSION, RIRI_MAGIC_NUMBER,
    REDUCED_CONFIDENCE_LOT, STANDARD_CONFIDENCE,
    SL_POINTS, TP_POINTS,
)
from models.execution import ExecutionResult
from models.execution_signal import ExecutionSignal
from services.signal_store import signal_store
from services.entry_eligibility import entry_rejection, riri_positions
from scoring.scoring_engine import ScoringEngine
from services.exposure import exposure


class ExecutionService:
    """Creates a signal only after independently rechecking every hard rule."""

    async def execute(self, decision, risk, market, *, initial_score: int | None = None) -> ExecutionResult:
        score = ScoringEngine().calculate(market).score
        # Rechecking can only tighten the original snapshot's score gate.
        if initial_score is not None:
            score = min(score, initial_score)
        rejected = entry_rejection(market, decision, initial_score=score)
        if not rejected and (risk is None or not risk.approved):
            rejected = "RISK_REJECTED"
        if rejected:
            return self._result(rejected)

        if signal_store.get_signal(market.identity_key) is not None:
            return self._result("SIGNAL_PENDING")

        tp_points, sl_points = TP_POINTS, SL_POINTS
        capital_fields = {}
        if settings.AI_CAPITAL_PROFILE:
            from services.capital_policy import validate_plan, risk_lot
            try:
                plan = validate_plan(market, decision.plan)
                capital_lot = risk_lot(market, plan)
            except ValueError as exc:
                return self._result(str(exc))
            tp_points, sl_points = plan.tp_points, plan.sl_points
            capital_fields = dict(ai_capital_profile=True, protection_plan=plan.model_dump(),
                trailing_start_points=plan.trailing_start_points,
                trailing_distance_points=plan.trailing_distance_points,
                trailing_step_points=plan.trailing_step_points,
                review_move_points=plan.review_move_points,
                cost_buffer_points=settings.CAPITAL_COST_BUFFER_POINTS)
        active_lot = exposure(market)["gross_lot"]
        # A 60-69 probability is an executable but reduced-risk setup. It
        # never receives the normal equity-based size. 70+ retains the locked
        # sizing formula unchanged.
        if decision.confidence < STANDARD_CONFIDENCE:
            lot = REDUCED_CONFIDENCE_LOT
        else:
            lot = round(DEFAULT_LOT + math.floor(market.equity / EQUITY_STEP) * LOT_STEP, 2)
        if settings.AI_CAPITAL_PROFILE:
            lot = capital_lot
        remaining_lot = max(0.0, MAX_TOTAL_LOT - active_lot)
        remaining_lot = math.floor((remaining_lot + 1e-9) * 100) / 100
        lot = min(lot, remaining_lot, MAX_TOTAL_LOT)
        if lot <= 0:
            return self._result("INVALID_OR_EXHAUSTED_LOT")

        if not exposure(market, lot, sl_points)["risk_allowed"]:
            return self._result("PORTFOLIO_SL_RISK_LIMIT")

        now = datetime.now(timezone.utc)
        signal = ExecutionSignal(
            signal_id=str(uuid.uuid4()),
            symbol=market.symbol,
            action=decision.decision,
            lot=lot,
            tp_points=tp_points,
            sl_points=sl_points,
            **capital_fields,
            confidence=decision.confidence,
            initial_score=score,
            entry_policy_version=4 if settings.AI_CAPITAL_PROFILE else ENTRY_POLICY_VERSION,
            max_spread_points=30 if settings.AI_CAPITAL_PROFILE else (150 if score>80 and decision.confidence>95 else 60) if settings.EXPERIMENTAL_SPREAD else 30,
            small_equity_strict=settings.SMALL_EQUITY_STRICT,
            max_sl_risk_percent=settings.CAPITAL_RISK_PERCENT if settings.AI_CAPITAL_PROFILE else (settings.MAX_SL_RISK_EQUITY_PERCENT or 0),
            preclose_enabled=settings.PRECLOSE_ENABLED,
            magic_number=RIRI_MAGIC_NUMBER,
            account_id=market.account_id,
            terminal_id=market.terminal_id,
            instance_id=market.instance_id,
            market_time=market.market_time,
            created_at=now,
            expires_at=now + timedelta(seconds=settings.SIGNAL_EXPIRY_SECONDS),
            created_at_epoch=int(now.timestamp()),
            expires_at_epoch=int(now.timestamp()) + settings.SIGNAL_EXPIRY_SECONDS,
        )
        reservation_error = signal_store.reserve(market, signal)
        if reservation_error:
            return self._result(reservation_error)
        return ExecutionResult(
            signal_created=True,
            order_type=decision.decision,
            lot=lot,
            reason="SIGNAL_CREATED",
            signal_id=signal.signal_id,
        )

    @staticmethod
    def _result(reason: str) -> ExecutionResult:
        return ExecutionResult(signal_created=False, order_type="NONE", lot=0.0, reason=reason)
