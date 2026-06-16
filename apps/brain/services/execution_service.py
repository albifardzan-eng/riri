from models.execution_result import (
    ExecutionResult
)

from config.trading_config import (
    DEFAULT_LOT
)


class ExecutionService:

    async def execute(
        self,
        decision,
        risk
    ) -> ExecutionResult:

        if decision is None:

            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="NO_DECISION"
            )

        if risk is None:

            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="NO_RISK"
            )

        if not risk.approved:

            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="RISK_REJECTED"
            )

        if decision.decision == "NONE":

            return ExecutionResult(
                executed=False,
                order_type="NONE",
                lot=0.0,
                reason="NO_SIGNAL"
            )

        return ExecutionResult(
            executed=True,
            order_type=decision.decision,
            lot=DEFAULT_LOT,
            reason="READY_FOR_MT5"
        )