import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from config.settings import BASE_DIR, settings
from services import entry_state


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
            entry_state.initialize(db)
            from services.capital_plans import initialize
            initialize(db)
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

    def reconcile_market(self, market):
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            latest = entry_state.reconcile(db, market)
            db.commit()
            return market.model_copy(update={"last_entry_server_time": latest})

    def reserve(self, market, signal):
        with self._lock, self._connect() as db:
            return entry_state.reserve(db, market, signal)

    def authorize(self, identity_key, signal_id, token):
        """A broker submission permit is issued ONCE, even across terminals."""
        now = int(datetime.now(timezone.utc).timestamp())
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT expires_at,delivered_at FROM pending_signals WHERE identity_key=? AND signal_id=?", (identity_key,signal_id)).fetchone()
            if row is None or row[0] <= now or row[1] is None:
                db.commit()
                return False
            cursor = db.execute("UPDATE account_entry_state SET authorized=? WHERE owner=? AND reservation=? AND authorized IS NULL", (token,identity_key,signal_id))
            db.commit()
            return cursor.rowcount == 1

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
                "SELECT payload, expires_at, delivered_at FROM pending_signals WHERE identity_key=?",
                (identity_key,),
            ).fetchone()
            if row is None:
                return None
            if row[1] <= now:
                if row[2] is None:
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
                if row[2] is None:
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
            db.execute("UPDATE account_entry_state SET delivered=? WHERE reservation=?",
                       (now, json.loads(row[0])["signal_id"]))
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
        outcome: str = "REJECTED",
        entry_server_time: int = 0,
        execution_token: str = "",
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
            permit = db.execute("SELECT authorized FROM account_entry_state WHERE reservation=?", (signal_id,)).fetchone()
            if permit and permit[0] is not None and str(permit[0]) != execution_token:
                db.commit()
                return None
            if outcome == "UNKNOWN":
                db.commit()
                return signal
            if outcome == "EXECUTED" and entry_server_time <= 0:
                db.commit()
                return None
            if outcome == "EXECUTED" and signal.get("ai_capital_profile") and signal.get("protection_plan"):
                account_key = json.dumps([signal["terminal_id"],signal["account_id"],signal["symbol"],signal["magic_number"]],separators=(",",":"))
                db.execute("INSERT OR REPLACE INTO capital_plans VALUES(?,?,?,?,?)",
                    (account_key,signal_id,entry_server_time,signal["action"],json.dumps(signal["protection_plan"])))
            db.execute("UPDATE account_entry_state SET last_fill=MAX(last_fill,?),reservation=NULL,delivered=NULL WHERE reservation=?",
                       (entry_server_time if outcome == "EXECUTED" else 0, signal_id))
            db.execute(
                "DELETE FROM pending_signals WHERE identity_key=? AND signal_id=?",
                (identity_key, signal_id),
            )
            db.commit()
            return signal

    def clear(self, identity_key: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM pending_signals WHERE identity_key=?", (identity_key,))
            # Explicit administrative/test reset only; never called by normal close.
            db.execute("DELETE FROM account_entry_state WHERE owner=?", (identity_key,))


signal_store = SignalStore()
