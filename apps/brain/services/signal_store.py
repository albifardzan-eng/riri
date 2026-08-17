from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional


class SignalStore:

    SIGNAL_EXPIRY_SECONDS = 60

    def __init__(self):
        self.pending_signal: Optional[dict[str, Any]] = None
        self.created_at: Optional[datetime] = None
        self.delivered_at: Optional[datetime] = None
        self._lock = Lock()

    # ==================================================
    # SET SIGNAL
    # ==================================================

    def set_signal(
        self,
        signal: dict[str, Any]
    ) -> None:

        if not signal:
            return

        signal_copy = dict(signal)

        signal_id = signal_copy.get(
            "signal_id"
        )

        if not signal_id:
            raise ValueError(
                "Signal must contain signal_id"
            )

        with self._lock:

            self.pending_signal = signal_copy

            self.created_at = (
                datetime.now(
                    timezone.utc
                )
            )

            self.delivered_at = None

    # ==================================================
    # GET SIGNAL
    # ==================================================

    def get_signal(
        self
    ) -> Optional[dict[str, Any]]:

        with self._lock:

            if self.pending_signal is None:
                return None

            if self.created_at is None:

                self._clear_locked()

                return None

            age = (
                datetime.now(
                    timezone.utc
                )
                -
                self.created_at
            ).total_seconds()

            if (
                age >
                self.SIGNAL_EXPIRY_SECONDS
            ):

                self._clear_locked()

                return None

            return dict(
                self.pending_signal
            )

    # ==================================================
    # GET SIGNAL FOR DELIVERY
    # ==================================================
    #
    # Returns the signal only once per signal_id.
    #
    # This prevents MT5 polling every few seconds from
    # executing the same signal repeatedly.
    #
    # ==================================================

    def get_signal_for_delivery(
        self
    ) -> Optional[dict[str, Any]]:

        with self._lock:

            if self.pending_signal is None:
                return None

            if self.created_at is None:

                self._clear_locked()

                return None

            age = (
                datetime.now(
                    timezone.utc
                )
                -
                self.created_at
            ).total_seconds()

            if (
                age >
                self.SIGNAL_EXPIRY_SECONDS
            ):

                self._clear_locked()

                return None

            if self.delivered_at is not None:
                return None

            self.delivered_at = (
                datetime.now(
                    timezone.utc
                )
            )

            return dict(
                self.pending_signal
            )

    # ==================================================
    # CONFIRM SIGNAL
    # ==================================================

    def confirm(
        self,
        signal_id: str
    ) -> bool:

        if not signal_id:
            return False

        with self._lock:

            if self.pending_signal is None:
                return False

            current_signal_id = (
                self.pending_signal.get(
                    "signal_id"
                )
            )

            if (
                current_signal_id !=
                signal_id
            ):

                return False

            self._clear_locked()

            return True

    # ==================================================
    # IS CURRENT SIGNAL
    # ==================================================

    def is_current_signal(
        self,
        signal_id: str
    ) -> bool:

        if not signal_id:
            return False

        with self._lock:

            if self.pending_signal is None:
                return False

            current_signal_id = (
                self.pending_signal.get(
                    "signal_id"
                )
            )

            return (
                current_signal_id ==
                signal_id
            )

    # ==================================================
    # SIGNAL AGE
    # ==================================================

    def get_age_seconds(self) -> Optional[float]:

        with self._lock:

            if (
                self.pending_signal is None
                or
                self.created_at is None
            ):
                return None

            return (
                datetime.now(
                    timezone.utc
                )
                -
                self.created_at
            ).total_seconds()

    # ==================================================
    # DELIVERY STATUS
    # ==================================================

    def is_delivered(self) -> bool:

        with self._lock:

            return (
                self.delivered_at is not None
            )

    # ==================================================
    # RESET DELIVERY
    # ==================================================
    #
    # Allows a still-valid signal to be delivered again
    # after an execution failure.
    #
    # ==================================================

    def reset_delivery(
        self,
        signal_id: Optional[str] = None
    ) -> bool:

        with self._lock:

            if self.pending_signal is None:
                return False

            current_signal_id = (
                self.pending_signal.get(
                    "signal_id"
                )
            )

            if (
                signal_id is not None
                and
                current_signal_id !=
                signal_id
            ):
                return False

            self.delivered_at = None

            return True

    # ==================================================
    # CLEAR
    # ==================================================

    def clear(self) -> None:

        with self._lock:

            self._clear_locked()

    # ==================================================
    # INTERNAL CLEAR
    # ==================================================

    def _clear_locked(self) -> None:

        self.pending_signal = None

        self.created_at = None

        self.delivered_at = None


# ==================================================
# SINGLETON
# ==================================================

signal_store = SignalStore()