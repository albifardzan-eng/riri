from pydantic import BaseModel


class ExecutionResult(BaseModel):

    executed: bool

    order_type: str

    lot: float

    reason: str