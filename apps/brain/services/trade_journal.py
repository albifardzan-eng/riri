from datetime import date, datetime, timezone
from enum import Enum
import json
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any

from config.settings import BASE_DIR, settings


class TradeJournal:
    """Durable SQLite lifecycle journal safe across API workers."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = Path(path or settings.RIRI_STATE_DIR)
        state_dir = configured if configured.is_absolute() else BASE_DIR / configured
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "journal.sqlite3"
        self._lock = Lock()
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event TEXT,
                    event_key TEXT,
                    payload TEXT NOT NULL
                )"""
            )
            columns = {
                row[1] for row in db.execute("PRAGMA table_info(journal)").fetchall()
            }
            if "event_key" not in columns:
                db.execute("ALTER TABLE journal ADD COLUMN event_key TEXT")
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS journal_event_key ON journal(event_key)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    @classmethod
    def _serialize(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Enum):
            return cls._serialize(value.value)
        if hasattr(value, "model_dump"):
            return cls._serialize(value.model_dump(mode="json"))
        if isinstance(value, dict):
            return {str(key): cls._serialize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._serialize(item) for item in value]
        if hasattr(value, "item"):
            return cls._serialize(value.item())
        if hasattr(value, "tolist"):
            return cls._serialize(value.tolist())
        return str(value)

    def add(self, trade: Any) -> dict:
        record = self._serialize(trade)
        if not isinstance(record, dict):
            record = {"data": record}
        record = dict(record)
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        payload = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO journal(timestamp, event, event_key, payload) VALUES(?, ?, ?, ?)",
                (record["timestamp"], record.get("event"), record.get("event_key"), payload),
            )
        return record

    def write(self, trade: Any) -> dict:
        return self.add(trade)

    def event(self, event: str, **data: Any) -> dict:
        return self.add({"event": event, **data})

    def all(self) -> list[dict]:
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT payload FROM journal ORDER BY id").fetchall()
        return [json.loads(row[0]) for row in rows]

    def latest(self, limit: int = 100) -> list[dict]:
        if limit <= 0:
            return []
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT payload FROM journal ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    def count(self, event: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM journal"
        params: tuple[Any, ...] = ()
        if event is not None:
            query += " WHERE event=?"
            params = (event,)
        with self._lock, self._connect() as db:
            return int(db.execute(query, params).fetchone()[0])


trade_journal = TradeJournal()
