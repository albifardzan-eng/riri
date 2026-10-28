"""Entry rationale persisted atomically with confirmed execution in signal DB.

A missing/ambiguous broker confirmation leaves the entry thesis unknown. The
review uses current evidence and ATR instead of guessing a plan association.
"""
import json
import sqlite3
from pathlib import Path
from config.settings import settings, BASE_DIR


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS capital_plans(
        account TEXT, signal_id TEXT PRIMARY KEY, server_time INTEGER,
        action TEXT, plan TEXT)''')


class Plans:
    def for_position(self, market, position):
        directory=Path(settings.RIRI_STATE_DIR)
        if not directory.is_absolute(): directory=BASE_DIR/directory
        directory.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(directory/'signals.sqlite3')
        try:
            initialize(db)
            # Acknowledgement clock follows the broker fill. Cooldown + single
            # position prevents two matching entries in this 60-second window.
            row=db.execute('''SELECT plan FROM capital_plans WHERE account=?
                AND action=? AND server_time>=? AND server_time<=?
                ORDER BY server_time LIMIT 1''',
                (market.account_key,position.type,position.open_time,position.open_time+60)).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            db.close()


plans=Plans()
