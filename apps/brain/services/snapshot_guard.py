import sqlite3
from pathlib import Path
from threading import Lock

from config.settings import BASE_DIR, settings


class SnapshotGuard:
    """Rejects replayed or out-of-order MT5 snapshots across API workers."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = Path(path or settings.RIRI_STATE_DIR)
        state_dir = configured if configured.is_absolute() else BASE_DIR / configured
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "snapshots.sqlite3"
        self._lock = Lock()
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS snapshot_guard (
                    identity_key TEXT PRIMARY KEY,
                    market_time INTEGER NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def accept(self, identity_key: str, market_time: int) -> bool:
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """INSERT INTO snapshot_guard(identity_key, market_time) VALUES(?, ?)
                   ON CONFLICT(identity_key) DO UPDATE SET market_time=excluded.market_time
                   WHERE excluded.market_time >= snapshot_guard.market_time + ?""",
                (identity_key, market_time, settings.MIN_MARKET_INTERVAL_SECONDS),
            )
            return cursor.rowcount == 1


snapshot_guard = SnapshotGuard()
