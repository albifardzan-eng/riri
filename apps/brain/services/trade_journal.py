from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
import json
import os
import tempfile
from typing import Any


class TradeJournal:
    """
    Persistent JSON journal for RIRI.

    The journal stores trade lifecycle events such as:

        SIGNAL_CREATED
        TRADE_EXECUTED
        TRADE_REJECTED
        TRADE_CLOSED

    The implementation uses:
        - UTC timestamps
        - JSON-safe serialization
        - thread protection
        - atomic file replacement

    This keeps the local journal reasonably safe for
    the current RIRI v1 architecture.
    """

    def __init__(
        self,
        path: str | Path = "trade_journal.json"
    ) -> None:

        self.path = Path(path)

        self._lock = Lock()

        self._ensure_file()


    # ==================================================
    # FILE INITIALIZATION
    # ==================================================

    def _ensure_file(self) -> None:

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if self.path.exists():
            return

        self.path.write_text(
            "[]",
            encoding="utf-8"
        )


    # ==================================================
    # SERIALIZATION
    # ==================================================

    @staticmethod
    def _serialize(
        value: Any
    ) -> Any:

        if value is None:
            return None

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool
            )
        ):

            return value

        if isinstance(
            value,
            (
                datetime,
                date
            )
        ):

            return value.isoformat()

        if isinstance(
            value,
            Enum
        ):

            return TradeJournal._serialize(
                value.value
            )

        if isinstance(
            value,
            dict
        ):

            return {
                str(key):
                TradeJournal._serialize(
                    val
                )
                for key, val in value.items()
            }

        if isinstance(
            value,
            (
                list,
                tuple,
                set
            )
        ):

            return [
                TradeJournal._serialize(
                    item
                )
                for item in value
            ]

        # Pydantic models

        if hasattr(
            value,
            "model_dump"
        ):

            try:

                return TradeJournal._serialize(
                    value.model_dump()
                )

            except (
                TypeError,
                ValueError
            ):

                pass

        # NumPy / Pandas scalar

        if hasattr(
            value,
            "item"
        ):

            try:

                return TradeJournal._serialize(
                    value.item()
                )

            except (
                ValueError,
                TypeError
            ):

                pass

        # NumPy / Pandas array

        if hasattr(
            value,
            "tolist"
        ):

            try:

                return TradeJournal._serialize(
                    value.tolist()
                )

            except (
                ValueError,
                TypeError
            ):

                pass

        return str(value)


    # ==================================================
    # LOAD
    # ==================================================

    def _load(self) -> list:

        self._ensure_file()

        try:

            content = self.path.read_text(
                encoding="utf-8"
            )

            if not content.strip():

                return []

            data = json.loads(
                content
            )

            if not isinstance(
                data,
                list
            ):

                return []

            return data

        except (
            json.JSONDecodeError,
            OSError
        ):

            return []


    # ==================================================
    # SAVE
    # ==================================================

    def _save(
        self,
        trades: list
    ) -> None:

        serialized = json.dumps(
            trades,
            indent=2,
            ensure_ascii=False,
            allow_nan=False
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # --------------------------------------------------
        # Atomic write
        #
        # Write to temporary file first, then replace the
        # existing journal.
        # --------------------------------------------------

        fd, temp_path = tempfile.mkstemp(
            prefix=".trade_journal_",
            suffix=".tmp",
            dir=str(
                self.path.parent
            )
        )

        try:

            with os.fdopen(
                fd,
                "w",
                encoding="utf-8"
            ) as temp_file:

                temp_file.write(
                    serialized
                )

                temp_file.flush()

                os.fsync(
                    temp_file.fileno()
                )

            os.replace(
                temp_path,
                self.path
            )

        finally:

            if os.path.exists(
                temp_path
            ):

                try:

                    os.remove(
                        temp_path
                    )

                except OSError:

                    pass


    # ==================================================
    # ADD
    # ==================================================

    def add(
        self,
        trade: Any
    ) -> dict:

        record = self._serialize(
            trade
        )

        if not isinstance(
            record,
            dict
        ):

            record = {
                "data": record
            }

        record = dict(
            record
        )

        record.setdefault(
            "timestamp",
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        with self._lock:

            trades = self._load()

            trades.append(
                record
            )

            self._save(
                trades
            )

        return record


    # ==================================================
    # WRITE
    # ==================================================

    def write(
        self,
        trade: Any
    ) -> dict:

        return self.add(
            trade
        )


    # ==================================================
    # EVENT
    # ==================================================

    def event(
        self,
        event: str,
        **data: Any
    ) -> dict:
        """
        Convenience method for writing standardized
        lifecycle events.

        Example:

            trade_journal.event(
                "TRADE_EXECUTED",
                signal_id="abc",
                action="BUY",
                lot=0.01
            )
        """

        record = {
            "event": event,
            **data
        }

        return self.add(
            record
        )


    # ==================================================
    # ALL
    # ==================================================

    def all(self) -> list:

        with self._lock:

            return self._load()


    # ==================================================
    # LATEST
    # ==================================================

    def latest(
        self,
        limit: int = 100
    ) -> list:

        if limit <= 0:
            return []

        with self._lock:

            trades = self._load()

            return trades[-limit:]


    # ==================================================
    # LAST EXECUTED TRADE
    # ==================================================

    def last_executed_trade(
        self
    ) -> datetime | None:

        trades = self._load()

        for record in reversed(
            trades
        ):

            if not isinstance(
                record,
                dict
            ):

                continue

            if record.get(
                "event"
            ) != "TRADE_EXECUTED":

                continue

            timestamp = record.get(
                "timestamp"
            )

            if not timestamp:

                continue

            try:

                parsed = datetime.fromisoformat(
                    timestamp
                )

                if parsed.tzinfo is None:

                    parsed = parsed.replace(
                        tzinfo=timezone.utc
                    )

                return parsed

            except (
                ValueError,
                TypeError
            ):

                continue

        return None


    # ==================================================
    # LAST EXECUTED TRADE TIMESTAMP
    # ==================================================

    def last_executed_timestamp(
        self
    ) -> int | None:

        timestamp = self.last_executed_trade()

        if timestamp is None:
            return None

        return int(
            timestamp.timestamp()
        )


    # ==================================================
    # COUNT
    # ==================================================

    def count(
        self,
        event: str | None = None
    ) -> int:

        with self._lock:

            trades = self._load()

        if event is None:

            return len(
                trades
            )

        return sum(
            1
            for record in trades
            if (
                isinstance(record, dict)
                and
                record.get("event") == event
            )
        )


# ==================================================
# SINGLETON
# ==================================================

trade_journal = TradeJournal()