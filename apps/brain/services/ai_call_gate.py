from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any

from config.settings import BASE_DIR, settings


@dataclass(frozen=True)
class AICallGateResult:
    call: bool
    reason: str
    news_changed: bool = False


class AICallGate:
    """Durable, identity-scoped throttle for billable AI calls."""

    def __init__(self, path: str | Path | None = None, interval_seconds: int | None = None) -> None:
        configured = Path(path or settings.RIRI_STATE_DIR)
        state_dir = configured if configured.is_absolute() else BASE_DIR / configured
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "ai_call_state.sqlite3"
        self.interval_seconds = interval_seconds if interval_seconds is not None else settings.AI_MIN_CALL_INTERVAL_SECONDS
        self._lock = Lock()
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS ai_call_state (
                    identity_key TEXT PRIMARY KEY,
                    last_call_epoch INTEGER NOT NULL,
                    news_fingerprint TEXT
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10, isolation_level=None)

    @staticmethod
    def news_fingerprint(fundamental: Any) -> str | None:
        if hasattr(fundamental, "model_dump"):
            fundamental = fundamental.model_dump(mode="json")
        if not isinstance(fundamental, dict) or not fundamental.get("high_impact_news"):
            return None
        material = {
            key: fundamental.get(key)
            for key in ("event_id", "event", "currency", "impact", "phase", "actual", "forecast", "previous")
        }
        return sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    def claim(self, identity_key: str, fundamental: Any, *, now: int | None = None) -> AICallGateResult:
        """Atomically reserve one AI call; a timeout is still a call attempt."""
        current = now if now is not None else int(datetime.now(timezone.utc).timestamp())
        fingerprint = self.news_fingerprint(fundamental)
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT last_call_epoch, news_fingerprint FROM ai_call_state WHERE identity_key=?",
                (identity_key,),
            ).fetchone()
            if row is None:
                result = AICallGateResult(True, "AI_CALLED_INITIAL_QUALIFIED")
            elif fingerprint is not None and fingerprint != row[1]:
                result = AICallGateResult(True, "AI_CALLED_NEWS_CHANGED", True)
            elif current - int(row[0]) >= self.interval_seconds:
                result = AICallGateResult(True, "AI_CALLED_INTERVAL_ELAPSED")
            else:
                db.commit()
                return AICallGateResult(False, "AI_SKIPPED_RATE_LIMIT")

            db.execute(
                """INSERT INTO ai_call_state(identity_key, last_call_epoch, news_fingerprint)
                   VALUES(?, ?, ?)
                   ON CONFLICT(identity_key) DO UPDATE SET
                     last_call_epoch=excluded.last_call_epoch,
                     news_fingerprint=excluded.news_fingerprint""",
                (identity_key, current, fingerprint),
            )
            db.commit()
            return result


ai_call_gate = AICallGate()
