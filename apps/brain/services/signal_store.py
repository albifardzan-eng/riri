import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from config.settings import BASE_DIR, settings


class SignalStore:
    """Durable, account-scoped signal queue with atomic delivery leases."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = Path(path or settings.RIRI_STATE_DIR)
        state_dir = configured if configured.is_absolute() else BASE_DIR / configured
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "signals.sqlite3"
        self._lock = Lock()
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS pending_signals (
                    identity_key TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    delivered_at INTEGER
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10, isolation_level=None)

    @staticmethod
    def _serialize(signal: Any) -> dict[str, Any]:
        return signal.model_dump(mode="json") if hasattr(signal, "model_dump") else dict(signal)

    def set_signal(self, identity_key: str, signal: Any) -> None:
        item = self._serialize(signal)
        signal_id = item.get("signal_id")
        expires_at = int(item.get("expires_at_epoch", 0))
        if not signal_id or not expires_at:
            raise ValueError("signal_id and expires_at_epoch are required")
        with self._lock, self._connect() as db:
            db.execute(
                """INSERT INTO pending_signals(identity_key, signal_id, payload, expires_at, delivered_at)
                   VALUES(?, ?, ?, ?, NULL)
                   ON CONFLICT(identity_key) DO UPDATE SET
                     signal_id=excluded.signal_id, payload=excluded.payload,
                     expires_at=excluded.expires_at, delivered_at=NULL""",
                (identity_key, signal_id, json.dumps(item, separators=(",", ":")), expires_at),
            )

    def get_signal(self, identity_key: str) -> dict[str, Any] | None:
        now = int(datetime.now(timezone.utc).timestamp())
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT payload, expires_at FROM pending_signals WHERE identity_key=?",
                (identity_key,),
            ).fetchone()
            if row is None:
                return None
            if row[1] <= now:
                db.execute("DELETE FROM pending_signals WHERE identity_key=?", (identity_key,))
                return None
            return json.loads(row[0])

    def claim_signal(self, identity_key: str) -> dict[str, Any] | None:
        now = int(datetime.now(timezone.utc).timestamp())
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload, expires_at, delivered_at FROM pending_signals WHERE identity_key=?",
                (identity_key,),
            ).fetchone()
            if row is None:
                db.commit()
                return None
            if row[1] <= now:
                db.execute("DELETE FROM pending_signals WHERE identity_key=?", (identity_key,))
                db.commit()
                return None
            if row[2] is not None and now - row[2] < settings.SIGNAL_DELIVERY_LEASE_SECONDS:
                db.commit()
                return None
            db.execute(
                "UPDATE pending_signals SET delivered_at=? WHERE identity_key=?",
                (now, identity_key),
            )
            db.commit()
            signal = json.loads(row[0])
            signal["status"] = "DELIVERED"
            return signal

    def confirm(
        self,
        identity_key: str,
        signal_id: str,
        action: str | None = None,
        requested_lot: float | None = None,
    ) -> dict[str, Any] | None:
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM pending_signals WHERE identity_key=? AND signal_id=?",
                (identity_key, signal_id),
            ).fetchone()
            if row is None:
                db.commit()
                return None
            signal = json.loads(row[0])
            if action is not None and signal.get("action") != action.upper():
                db.commit()
                return None
            if (
                requested_lot is not None
                and abs(float(signal.get("lot", 0)) - requested_lot) > 1e-8
            ):
                db.commit()
                return None
            db.execute(
                "DELETE FROM pending_signals WHERE identity_key=? AND signal_id=?",
                (identity_key, signal_id),
            )
            db.commit()
            return signal

    def clear(self, identity_key: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM pending_signals WHERE identity_key=?", (identity_key,))


signal_store = SignalStore()
