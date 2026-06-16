import uuid

from models.execution import (
    ExecutionResult
)

from models.execution_signal import (
    ExecutionSignal
)

from services.signal_store import (
    signal_store
)

from config.trading_config import (
    TP_POINTS,
    SL_POINTS
)


class ExecutionService:

    async def execute(
        self,
        decision,
        risk
    ):

        if decision is None:

            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="NO_DECISION"
            )

        if not risk.approved:

            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="RISK_REJECTED"
            )

        signal = ExecutionSignal(

            signal_id=
            str(uuid.uuid4()),

            symbol="XAUUSD",

            action=
            decision.decision,

            lot=0.01,

            tp_points=
            TP_POINTS,

            sl_points=
            SL_POINTS,

            status="PENDING"
        )

        signal_store.set_signal(
            signal
        )

        return ExecutionResult(
            executed=True,

            order_type=
            decision.decision,

            lot=0.01,

            reason=
            "SIGNAL_CREATED"
        )