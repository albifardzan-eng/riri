"""Persistent shared entry/review quota with atomic reservations.

Charge a conservative UTF-8 byte estimate + maximum output up front; failed
or interrupted calls retain the charge. Actual usage is journaled separately.
This bounds attempted calls/tokens, not currency billing.
"""
import sqlite3
import time
from pathlib import Path
from config.settings import settings, BASE_DIR


class AIBudget:
    def __init__(self, directory=None):
        path = Path(directory or settings.RIRI_STATE_DIR)
        if not path.is_absolute(): path = BASE_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        self.path = path / "capital_budget.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS quota(day INTEGER PRIMARY KEY,calls INTEGER,tokens INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS lanes(account TEXT PRIMARY KEY,last_call INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS observations(key TEXT PRIMARY KEY,at INTEGER,price REAL,event TEXT)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10, isolation_level=None)

    def claim(self, account, prompt, schema, *, key, price, event, move, max_age, now=None):
        now = int(time.time()) if now is None else now
        charge = len(prompt.encode('utf-8')) + len(schema.encode('utf-8')) + settings.CAPITAL_AI_OUTPUT_TOKENS + 512
        day = now // 86400  # UTC, deliberate budget boundary
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT at,price,event FROM observations WHERE key=?", (key,)).fetchone()
            if prior and now-prior[0] < max_age and abs(price-prior[1]) < move and event == prior[2]:
                db.commit(); return "AI_NO_MATERIAL_CHANGE"
            last = db.execute("SELECT last_call FROM lanes WHERE account=?", (account,)).fetchone()
            if last and now-last[0] < settings.CAPITAL_AI_MIN_SECONDS:
                db.commit(); return "AI_MIN_INTERVAL"
            usage = db.execute("SELECT calls,tokens FROM quota WHERE day=?", (day,)).fetchone() or (0,0)
            # Reserve one third of the daily allowance for position management.
            if key.endswith('capital_entry') and (usage[0] >= max(1,settings.CAPITAL_AI_CALLS_PER_DAY*2//3) or
                    usage[1]+charge > settings.CAPITAL_AI_TOKENS_PER_DAY*2//3):
                db.commit(); return "AI_ENTRY_BUDGET_EXHAUSTED"
            if usage[0] >= settings.CAPITAL_AI_CALLS_PER_DAY or usage[1]+charge > settings.CAPITAL_AI_TOKENS_PER_DAY:
                db.commit(); return "AI_DAILY_BUDGET_EXHAUSTED"
            db.execute("INSERT OR REPLACE INTO quota VALUES(?,?,?)", (day,usage[0]+1,usage[1]+charge))
            db.execute("INSERT OR REPLACE INTO lanes VALUES(?,?)", (account,now))
            db.execute("INSERT OR REPLACE INTO observations VALUES(?,?,?,?)", (key,now,price,event))
            db.commit()
        return None
