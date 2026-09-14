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
    retry_after_seconds: int = 0


class AICallGate:
    """Durable, identity-scoped throttle for billable AI calls."""

    def __init__(self, path: str | Path | None = None, interval_seconds: int | None = None,
                 event_interval_seconds: int | None = None) -> None:
        configured = Path(path or settings.RIRI_STATE_DIR)
        state_dir = configured if configured.is_absolute() else BASE_DIR / configured
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "ai_call_state.sqlite3"
        self.interval_seconds = interval_seconds if interval_seconds is not None else settings.AI_MIN_CALL_INTERVAL_SECONDS
        self.event_interval_seconds = min(self.interval_seconds,
            event_interval_seconds if event_interval_seconds is not None else settings.AI_EVENT_MIN_INTERVAL_SECONDS)
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
            # Additive migration only: preserve all previous call reservations.
            db.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in db.execute("PRAGMA table_info(ai_call_state)")}
            if "opportunity_json" not in columns:
                db.execute("ALTER TABLE ai_call_state ADD COLUMN opportunity_json TEXT")
            db.commit()

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

    @staticmethod
    def opportunity_changed(previous, current) -> bool:
        if not previous or not current:
            return False
        if current["candle_time"] > previous["candle_time"]:
            return True
        # A newly possible direction or lower confidence requirement is useful;
        # losing eligibility is not a reason to pay for another analysis.
        if any(action not in previous["required_confidence"] or minimum < previous["required_confidence"][action]
               for action, minimum in current["required_confidence"].items()):
            return True
        return abs(current["mid"] - previous["mid"]) >= max(
            previous["atr"] * settings.AI_PRICE_CHANGE_ATR, previous["point"])

    def claim(self, identity_key: str, fundamental: Any, *, opportunity: dict | None = None,
              now: int | None = None) -> AICallGateResult:
        """Atomically reserve one AI call; a timeout is still a call attempt."""
        current = now if now is not None else int(datetime.now(timezone.utc).timestamp())
        fingerprint = self.news_fingerprint(fundamental)
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT last_call_epoch, news_fingerprint, opportunity_json FROM ai_call_state WHERE identity_key=?",
                (identity_key,),
            ).fetchone()
            elapsed = current - int(row[0]) if row else 0
            previous = json.loads(row[2]) if row and row[2] else None
            news_changed = fingerprint is not None and row is not None and fingerprint != row[1]
            material_change = self.opportunity_changed(previous, opportunity)
            if row is None:
                result = AICallGateResult(True, "AI_CALLED_INITIAL_QUALIFIED")
            elif news_changed and elapsed >= self.event_interval_seconds:
                result = AICallGateResult(True, "AI_CALLED_NEWS_CHANGED", True)
            elif material_change and elapsed >= self.event_interval_seconds:
                result = AICallGateResult(True, "AI_CALLED_OPPORTUNITY_CHANGED")
            elif elapsed >= self.interval_seconds:
                result = AICallGateResult(True, "AI_CALLED_INTERVAL_ELAPSED")
            else:
                db.commit()
                wait = (self.event_interval_seconds if news_changed or material_change else self.interval_seconds) - elapsed
                return AICallGateResult(False, "AI_SKIPPED_RATE_LIMIT", retry_after_seconds=max(0, wait))

            db.execute(
                """INSERT INTO ai_call_state(identity_key, last_call_epoch, news_fingerprint, opportunity_json)
                   VALUES(?, ?, ?, ?)
                   ON CONFLICT(identity_key) DO UPDATE SET
                     last_call_epoch=excluded.last_call_epoch,
                     news_fingerprint=excluded.news_fingerprint,
                     opportunity_json=excluded.opportunity_json""",
                (identity_key, current, fingerprint, json.dumps(opportunity) if opportunity else None),
            )
            db.commit()
            return result


ai_call_gate = AICallGate()
