from pathlib import Path
from datetime import datetime, date
from enum import Enum
import json


class TradeJournal:

    def __init__(self):
        self.path = Path("trade_journal.json")

        if not self.path.exists():
            self.path.write_text(
                "[]",
                encoding="utf-8"
            )

    @staticmethod
    def _serialize(value):

        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, Enum):
            return value.value

        if isinstance(value, dict):
            return {
                str(key): TradeJournal._serialize(val)
                for key, val in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                TradeJournal._serialize(item)
                for item in value
            ]

        # Pydantic models
        if hasattr(value, "model_dump"):
            return TradeJournal._serialize(
                value.model_dump()
            )

        # NumPy / Pandas scalar values
        if hasattr(value, "item"):
            try:
                return TradeJournal._serialize(
                    value.item()
                )
            except (ValueError, TypeError):
                pass

        # NumPy / Pandas arrays
        if hasattr(value, "tolist"):
            try:
                return TradeJournal._serialize(
                    value.tolist()
                )
            except (ValueError, TypeError):
                pass

        # Last-resort conversion
        return str(value)

    def _load(self):

        try:
            content = self.path.read_text(
                encoding="utf-8"
            )

            if not content.strip():
                return []

            data = json.loads(content)

            if not isinstance(data, list):
                return []

            return data

        except (
            json.JSONDecodeError,
            OSError
        ):
            return []

    def add(self, trade):

        trades = self._load()

        record = self._serialize(trade)

        if not isinstance(record, dict):
            record = {
                "data": record
            }

        record["timestamp"] = (
            datetime.utcnow().isoformat()
        )

        trades.append(record)

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

    def write(self, trade):

        return self.add(trade)

    def all(self):

        return self._load()

    def latest(self, limit=100):

        trades = self._load()

        if limit <= 0:
            return []

        return trades[-limit:]


trade_journal = TradeJournal()