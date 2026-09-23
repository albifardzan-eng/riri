"""Account-wide atomic reservations, durable fills and conservative ambiguity handling.

Shares the signal DB so reservation, publication, delivery and confirmation can
be committed together. The account key excludes the executor instance.
"""
import json
import sqlite3
import time
from config.trading_config import MIN_ENTRY_INTERVAL_SECONDS


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS account_entry_state (
        account_key TEXT PRIMARY KEY, last_fill INTEGER NOT NULL DEFAULT 0,
        reservation TEXT, owner TEXT, expires INTEGER, delivered INTEGER,
        baseline_fill INTEGER NOT NULL DEFAULT 0
    )''')
    db.execute("BEGIN IMMEDIATE")
    if "authorized" not in {r[1] for r in db.execute("PRAGMA table_info(account_entry_state)")}:
        db.execute("ALTER TABLE account_entry_state ADD COLUMN authorized TEXT")

    db.commit()


def reconcile(db, market):
    key = market.account_key
    latest = max([market.last_entry_server_time] + [p.open_time for p in market.positions
                  if p.magic_number == 20260701])
    db.execute("INSERT OR IGNORE INTO account_entry_state(account_key) VALUES(?)", (key,))
    db.execute("UPDATE account_entry_state SET last_fill=MAX(last_fill,?) WHERE account_key=?", (latest, key))
    row = db.execute("SELECT last_fill,reservation,owner,expires,delivered,baseline_fill FROM account_entry_state WHERE account_key=?", (key,)).fetchone()
    # A freshly reconciled broker fill can replace an in-flight reservation;
    # no lot is counted twice. It also restarts account cooldown.
    if row[1] and latest > row[5]:
        db.execute("DELETE FROM pending_signals WHERE identity_key=? AND signal_id=?", (row[2],row[1]))
        db.execute("UPDATE account_entry_state SET reservation=NULL,delivered=NULL WHERE account_key=?", (key,))
    elif row[1] and row[4] is None and row[3] <= int(time.time()):
        db.execute("DELETE FROM pending_signals WHERE identity_key=? AND signal_id=?", (row[2],row[1]))
        db.execute("UPDATE account_entry_state SET reservation=NULL WHERE account_key=?", (key,))
    return max(latest, row[0])


def reserve(db, market, signal):
    db.execute("BEGIN IMMEDIATE")
    latest = reconcile(db, market)
    if latest > market.server_time or (latest and market.server_time-latest < MIN_ENTRY_INTERVAL_SECONDS):
        db.rollback()
        return "MIN_ENTRY_INTERVAL"
    row = db.execute("SELECT reservation FROM account_entry_state WHERE account_key=?", (market.account_key,)).fetchone()
    if row[0]:
        db.rollback()
        return "ACCOUNT_ENTRY_PENDING"
    item = signal.model_dump(mode="json")
    db.execute("UPDATE account_entry_state SET reservation=?,owner=?,expires=?,delivered=NULL,authorized=NULL,baseline_fill=? WHERE account_key=?",
               (signal.signal_id, market.identity_key, signal.expires_at_epoch, latest, market.account_key))
    db.execute("INSERT OR REPLACE INTO pending_signals VALUES(?,?,?,?,NULL)",
               (market.identity_key,signal.signal_id,json.dumps(item),signal.expires_at_epoch))
    db.commit()
    return None
