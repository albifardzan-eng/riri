from datetime import date, datetime, timezone
from enum import Enum
import json
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any

from config.settings import BASE_DIR, settings


class MarketStore:
    """Durable latest pipeline state per MT5 identity."""

    STAGES = {
        "market", "score", "statistics", "fundamental", "pattern",
        "decision", "risk", "execution", "journal",
    }

    def __init__(self, path: str | Path | None = None) -> None:
        configured = Path(path or settings.RIRI_STATE_DIR)
        state_dir = configured if configured.is_absolute() else BASE_DIR / configured
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "market_state.sqlite3"
        self._lock = Lock()
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS market_state (
                    identity_key TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(identity_key, stage)
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS market_metadata (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    latest_identity TEXT
                )"""
            )
            db.execute("INSERT OR IGNORE INTO market_metadata(id, latest_identity) VALUES(1, NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    @classmethod
    def _normalize(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Enum):
            return cls._normalize(value.value)
        if hasattr(value, "model_dump"):
            return cls._normalize(value.model_dump(mode="json"))
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._normalize(item) for item in value]
        if hasattr(value, "item"):
            return cls._normalize(value.item())
        if hasattr(value, "tolist"):
            return cls._normalize(value.tolist())
        return str(value)

    def begin_cycle(self, identity_key: str, market: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(self._normalize(market), allow_nan=False, separators=(",", ":"))
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM market_state WHERE identity_key=?", (identity_key,))
            db.execute(
                "INSERT INTO market_state(identity_key, stage, payload, updated_at) VALUES(?, 'market', ?, ?)",
                (identity_key, payload, now),
            )
            db.execute("UPDATE market_metadata SET latest_identity=? WHERE id=1", (identity_key,))

    def update_stage(self, identity_key: str, stage: str, data: Any) -> None:
        if stage not in self.STAGES:
            raise ValueError(f"unknown market-store stage: {stage}")
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(self._normalize(data), allow_nan=False, separators=(",", ":"))
        with self._lock, self._connect() as db:
            db.execute(
                """INSERT INTO market_state(identity_key, stage, payload, updated_at)
                   VALUES(?, ?, ?, ?)
                   ON CONFLICT(identity_key, stage) DO UPDATE SET
                     payload=excluded.payload, updated_at=excluded.updated_at""",
                (identity_key, stage, payload, now),
            )
            db.execute("UPDATE market_metadata SET latest_identity=? WHERE id=1", (identity_key,))

    def _identity(self, db: sqlite3.Connection, identity_key: str | None) -> str | None:
        if identity_key:
            return identity_key
        row = db.execute("SELECT latest_identity FROM market_metadata WHERE id=1").fetchone()
        return row[0] if row else None

    def get_stage(self, stage: str, identity_key: str | None = None) -> Any:
        with self._lock, self._connect() as db:
            key = self._identity(db, identity_key)
            if not key:
                return None
            row = db.execute(
                "SELECT payload FROM market_state WHERE identity_key=? AND stage=?",
                (key, stage),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def snapshot(self, identity_key: str | None = None) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            key = self._identity(db, identity_key)
            if not key:
                return {}
            rows = db.execute(
                "SELECT stage, payload, updated_at FROM market_state WHERE identity_key=?",
                (key,),
            ).fetchall()
        result = {stage: json.loads(payload) for stage, payload, _ in rows}
        if rows:
            result["updated_at"] = max(updated_at for _, _, updated_at in rows)
            result["identity"] = key
        return result


market_store = MarketStore()
