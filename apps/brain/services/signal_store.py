from datetime import datetime, timezone
from typing import Any, Optional


class SignalStore:

    SIGNAL_EXPIRY_SECONDS = 30

    def __init__(self):
        self.pending_signal: Optional[dict[str, Any]] = None
        self.created_at: Optional[datetime] = None

    def set_signal(
        self,
        signal: dict[str, Any]
    ) -> None:

        self.pending_signal = dict(signal)

        self.created_at = datetime.now(
            timezone.utc
        )

    def get_signal(self) -> Optional[dict[str, Any]]:

        if self.pending_signal is None:
            return None

        if self.created_at is None:
            self.clear()
            return None

        age = (
            datetime.now(timezone.utc)
            - self.created_at
        ).total_seconds()

        if age > self.SIGNAL_EXPIRY_SECONDS:
            self.clear()
            return None

        return dict(
            self.pending_signal
        )

    def clear(self) -> None:

        self.pending_signal = None
        self.created_at = None


signal_store = SignalStore()