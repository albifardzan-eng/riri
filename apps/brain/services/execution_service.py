import math
import uuid

from config.trading_config import (
    TP_POINTS,
    SL_POINTS,
    DEFAULT_LOT,
    MAX_TOTAL_LOT
)

from models.execution import ExecutionResult
from models.execution_signal import ExecutionSignal

from services.signal_store import signal_store


EQUITY_STEP = 500.0
LOT_STEP = 0.01


class ExecutionService:

    async def execute(
        self,
        decision,
        risk,
        market
    ):

        # ==================================================
        # NO DECISION
        # ==================================================

        if decision is None:
            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="NO_DECISION"
            )

        # ==================================================
        # NO SIGNAL
        # ==================================================

        if decision.decision == "NONE":
            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="NO_SIGNAL"
            )

        # ==================================================
        # NO RISK
        # ==================================================

        if risk is None:
            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="NO_RISK"
            )

        # ==================================================
        # RISK REJECTED
        # ==================================================

        if not risk.approved:
            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="RISK_REJECTED"
            )

        # ==================================================
        # EXISTING PENDING SIGNAL
        # ==================================================

        existing_signal = (
            signal_store.get_signal()
        )

        if existing_signal is not None:
            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="SIGNAL_PENDING"
            )

        # ==================================================
        # EQUITY-BASED LOT MANAGEMENT
        #
        # $0 - < $500       -> 0.01
        # $500 - < $1000    -> 0.02
        # $1000 - < $1500   -> 0.03
        # $1500 - < $2000   -> 0.04
        # ...
        #
        # Maximum total lot = 0.50
        # ==================================================

        equity = max(
            0.0,
            float(market.equity)
        )

        equity_steps = math.floor(
            equity / EQUITY_STEP
        )

        lot = (
            LOT_STEP *
            (equity_steps + 1)
        )

        lot = round(
            lot,
            2
        )

        # ==================================================
        # MAX LOT CAP
        # ==================================================

        lot = min(
            lot,
            MAX_TOTAL_LOT
        )

        # ==================================================
        # EXISTING ACTIVE LOT
        # ==================================================

        active_lot = sum(
            float(position.lot)
            for position in market.positions
        )

        remaining_lot = round(
            MAX_TOTAL_LOT - active_lot,
            2
        )

        if remaining_lot <= 0:
            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="MAX_TOTAL_LOT"
            )

        # ==================================================
        # FIT LOT INTO REMAINING EXPOSURE
        # ==================================================

        lot = min(
            lot,
            remaining_lot
        )

        lot = round(
            lot,
            2
        )

        if lot <= 0:
            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="INVALID_LOT"
            )

        # ==================================================
        # CREATE EXECUTION SIGNAL
        # ==================================================

        signal = ExecutionSignal(
            signal_id=str(
                uuid.uuid4()
            ),
            symbol=market.symbol,
            action=decision.decision,
            lot=lot,
            tp_points=TP_POINTS,
            sl_points=SL_POINTS,
            confidence=max(
                0,
                min(
                    100,
                    decision.confidence
                )
            ),
            status="PENDING"
        )

        # ==================================================
        # STORE SIGNAL
        # ==================================================

        signal_store.set_signal(
            signal
        )

        return ExecutionResult(
            executed=True,
            order_type=decision.decision,
            lot=lot,
            reason="SIGNAL_CREATED"
        )