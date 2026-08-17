from pathlib import Path
from datetime import datetime, date, timezone
from enum import Enum
import json


class TradeJournal:

    def __init__(self):

        self.path = Path(
            "trade_journal.json"
        )

        if not self.path.exists():

            self.path.write_text(
                "[]",
                encoding="utf-8"
            )

    # ==================================================
    # SERIALIZE
    # ==================================================

    @staticmethod
    def _serialize(value):

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
            return value.value

        if isinstance(
            value,
            dict
        ):

            return {
                str(key):
                TradeJournal._serialize(val)

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
                TradeJournal._serialize(item)
                for item in value
            ]

        # Pydantic models

        if hasattr(
            value,
            "model_dump"
        ):

            return TradeJournal._serialize(
                value.model_dump()
            )

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

        # NumPy / Pandas arrays

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

    def _load(self):

        try:

            content = (
                self.path.read_text(
                    encoding="utf-8"
                )
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
    # ADD JOURNAL RECORD
    # ==================================================

    def add(
        self,
        trade
    ):

        trades = self._load()

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

        record["timestamp"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        trades.append(
            record
        )

        serialized = json.dumps(
            trades,
            indent=2,
            ensure_ascii=False,
            allow_nan=False
        )

        self.path.write_text(
            serialized,
            encoding="utf-8"
        )

        return record

    # ==================================================
    # WRITE
    # ==================================================

    def write(
        self,
        trade
    ):

        return self.add(
            trade
        )

    # ==================================================
    # ALL
    # ==================================================

    def all(self):

        return self._load()

    # ==================================================
    # LATEST
    # ==================================================

    def latest(
        self,
        limit=100
    ):

        trades = self._load()

        if limit <= 0:

            return []

        return trades[-limit:]

    # ==================================================
    # LAST EXECUTED TRADE
    # ==================================================

    def last_executed_trade(self):

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

                return datetime.fromisoformat(
                    timestamp
                )

            except (
                ValueError,
                TypeError
            ):

                continue

        return None


# ==================================================
# SINGLETON
# ==================================================

trade_journal = TradeJournal()