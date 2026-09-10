from dataclasses import dataclass
from datetime import datetime, timezone

from config.settings import settings
from config.trading_config import (
    MAX_ACTIVE_TRADES, MAX_SPREAD, MAX_TOTAL_LOT, MIN_ATR,
    MIN_ENTRY_INTERVAL_SECONDS,
)


@dataclass(frozen=True)
class EntryEligibility:
    """Deterministic pre-gate for directions that could create a new order."""

    allowed_actions: tuple[str, ...]
    reason: str
    action_reasons: dict[str, str]


def eligible_actions(market, *, now: int | None = None) -> EntryEligibility:
    """Evaluate both directions without invoking AI or creating a signal.

    This intentionally mirrors immutable entry protections.  It does not decide
    a direction; it only prevents paying for a decision that cannot be executed.
    ExecutionService and AIRisk still recheck every rule after the model responds.
    """
    current = now if now is not None else int(datetime.now(timezone.utc).timestamp())

    common_checks = (
        (market.symbol != "XAUUSD", "SYMBOL_NOT_ALLOWED"),
        (current - int(market.market_time) < 0 or current - int(market.market_time) > settings.MAX_MARKET_AGE_SECONDS,
         "STALE_MARKET_DATA"),
        (market.free_margin <= 0, "INSUFFICIENT_FREE_MARGIN"),
        (market.spread > MAX_SPREAD, "SPREAD_ABOVE_LIMIT"),
        (market.atr < MIN_ATR, "ATR_BELOW_LIMIT"),
    )
    for blocked, reason in common_checks:
        if blocked:
            return EntryEligibility((), reason, {"BUY": reason, "SELL": reason})

    positions = [position for position in market.positions if position.symbol == market.symbol]
    if len(positions) >= MAX_ACTIVE_TRADES:
        return EntryEligibility((), "MAX_ACTIVE_TRADES", {"BUY": "MAX_ACTIVE_TRADES", "SELL": "MAX_ACTIVE_TRADES"})
    if sum(float(position.lot) for position in positions) >= MAX_TOTAL_LOT:
        return EntryEligibility((), "MAX_TOTAL_LOT", {"BUY": "MAX_TOTAL_LOT", "SELL": "MAX_TOTAL_LOT"})

    if positions:
        open_times = [int(position.open_time) for position in positions if position.open_time > 0]
        if not open_times:
            return EntryEligibility((), "OPEN_TIME_UNAVAILABLE", {"BUY": "OPEN_TIME_UNAVAILABLE", "SELL": "OPEN_TIME_UNAVAILABLE"})
        if current - max(open_times) < MIN_ENTRY_INTERVAL_SECONDS:
            return EntryEligibility((), "MIN_ENTRY_INTERVAL", {"BUY": "MIN_ENTRY_INTERVAL", "SELL": "MIN_ENTRY_INTERVAL"})

    blocked: dict[str, str] = {}
    for action in ("BUY", "SELL"):
        opposite = "SELL" if action == "BUY" else "BUY"
        if any(position.type == opposite for position in positions):
            blocked[action] = "HEDGING_FORBIDDEN"
        elif any(position.type == action and position.profit < 0 for position in positions):
            blocked[action] = "AVERAGING_FORBIDDEN"

    allowed = tuple(action for action in ("BUY", "SELL") if action not in blocked)
    return EntryEligibility(allowed, "PASS" if allowed else "NO_EXECUTABLE_DIRECTION", blocked)
