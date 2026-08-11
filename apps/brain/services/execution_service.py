import uuid

from config.trading_config import (
    TP_POINTS,
    SL_POINTS,
    DEFAULT_LOT,
    MAX_TOTAL_LOT
)

from models.execution import (
    ExecutionResult
)

from models.execution_signal import (
    ExecutionSignal
)

from services.signal_store import (
    signal_store
)


class ExecutionService:

    async def execute(
        self,
        decision,
        risk
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
        #
        # Do not create another signal while the previous
        # signal is still waiting for MT5 execution.
        #
        # SignalStore automatically removes expired signals.
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
        # CONFIDENCE
        # ==================================================

        confidence = max(
            0,
            min(
                100,
                decision.confidence
            )
        )

        # ==================================================
        # LOT MANAGEMENT
        #
        # Keep existing RIRI lot management unchanged.
        # ==================================================

        lot = DEFAULT_LOT

        if confidence >= 95:

            lot = min(
                0.05,
                MAX_TOTAL_LOT
            )

        elif confidence >= 90:

            lot = min(
                0.04,
                MAX_TOTAL_LOT
            )

        elif confidence >= 85:

            lot = min(
                0.03,
                MAX_TOTAL_LOT
            )

        elif confidence >= 80:

            lot = min(
                0.02,
                MAX_TOTAL_LOT
            )

        # ==================================================
        # CREATE EXECUTION SIGNAL
        # ==================================================

        signal = ExecutionSignal(

            signal_id=str(
                uuid.uuid4()
            ),

            symbol="XAUUSD",

            action=decision.decision,

            lot=lot,

            tp_points=TP_POINTS,

            sl_points=SL_POINTS,

            confidence=confidence,

            status="PENDING"
        )

        # ==================================================
        # STORE SIGNAL
        # ==================================================

        signal_store.set_signal(
            signal
        )

        # ==================================================
        # RESULT
        # ==================================================

        return ExecutionResult(

            executed=True,

            order_type=decision.decision,

            lot=lot,

            reason="SIGNAL_CREATED"
        )