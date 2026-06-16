from pydantic import BaseModel


class ExecutionSignal(BaseModel):

    signal_id: str

    symbol: str

    action: str

    lot: float

    tp_points: int

    sl_points: int

    confidence: int

    status: str