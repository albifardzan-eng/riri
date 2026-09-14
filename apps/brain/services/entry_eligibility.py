from dataclasses import dataclass
from datetime import datetime, timezone

from config.settings import settings
from config.trading_config import (
    ENTRY_POLICY_VERSION, EXCEPTION_THRESHOLD, RIRI_MAGIC_NUMBER,
    MAX_ACTIVE_TRADES, MAX_SPREAD, MAX_TOTAL_LOT, MIN_ATR,
    MIN_CONFIDENCE, MIN_ENTRY_INTERVAL_SECONDS, MIN_SCORE,
)
from scoring.scoring_engine import ScoringEngine


def riri_positions(market):
    return [p for p in market.positions
            if p.symbol == market.symbol and p.magic_number == RIRI_MAGIC_NUMBER]


@dataclass(frozen=True)
class EntryEligibility:
    allowed_actions: tuple[str, ...]
    reason: str
    action_reasons: dict[str, str]
    required_confidence: dict[str, int]
    diagnostics: dict


def eligible_actions(market, *, now: int | None = None,
                     initial_score: int | None = None) -> EntryEligibility:
    """Pre-AI feasibility only; confidence is checked after a fresh decision.

    All independent blockers are exposed, even during cooldown. Position rules
    use only RIRI's magic number, while margin remains account-wide. Netting
    accounts fail closed because magic-based position isolation is not safe.
    """
    current = now if now is not None else int(datetime.now(timezone.utc).timestamp())
    score = ScoringEngine().calculate(market).score if initial_score is None else initial_score
    positions = riri_positions(market)
    lot = sum(float(p.lot) for p in positions)
    latest = max((int(p.open_time) for p in positions), default=0)
    invalid_time = bool(positions) and (
        market.server_time <= 0 or any(p.open_time <= 0 for p in positions)
        or latest > market.server_time
    )
    # Conservative age at snapshot time, not a synthetic UTC conversion. This
    # is independent of broker timezone, including UTC+2/UTC+3 servers.
    age = market.server_time - latest if positions and not invalid_time else None
    remaining = max(0, MIN_ENTRY_INTERVAL_SECONDS - age) if age is not None else 0

    checks = (
        (market.executor_policy_version != ENTRY_POLICY_VERSION, "EXECUTOR_UPGRADE_REQUIRED"),
        (market.symbol != "XAUUSD", "SYMBOL_NOT_ALLOWED"),
        (current - market.market_time < 0 or current - market.market_time > settings.MAX_MARKET_AGE_SECONDS,
         "STALE_MARKET_DATA"),
        (not market.hedging_account, "HEDGING_ACCOUNT_REQUIRED"),
        (not market.trade_allowed, "TRADING_NOT_ALLOWED"),
        (score < MIN_SCORE, "SCORE_BELOW_THRESHOLD"),
        (invalid_time, "POSITION_TIME_INVALID"),
        (remaining > 0, "MIN_ENTRY_INTERVAL"),
        (market.free_margin <= 0, "INSUFFICIENT_FREE_MARGIN"),
        (market.spread > MAX_SPREAD, "SPREAD_ABOVE_LIMIT"),
        (market.atr < MIN_ATR, "ATR_BELOW_LIMIT"),
        (len(positions) >= MAX_ACTIVE_TRADES, "MAX_ACTIVE_TRADES"),
        (lot >= MAX_TOTAL_LOT - 1e-9, "MAX_TOTAL_LOT"),
    )
    common = [reason for blocked, reason in checks if blocked]
    reasons, required, blockers, exceptions = {}, {}, {}, {}
    for action in ("BUY", "SELL"):
        needs = []
        if any(p.type != action for p in positions):
            needs.append("HEDGING")
        if any(p.type == action and p.profit < 0 for p in positions):
            needs.append("AVERAGING")
        exceptions[action] = needs
        required[action] = EXCEPTION_THRESHOLD + 1 if needs else MIN_CONFIDENCE
        blockers[action] = common + [f"{need}_REQUIRES_SCORE_ABOVE_80"
                                     for need in needs if score <= EXCEPTION_THRESHOLD]
        reasons[action] = blockers[action][0] if blockers[action] else "PASS"

    allowed = tuple(action for action in ("BUY", "SELL") if not blockers[action])
    reason = "PASS" if allowed else common[0] if common else "POSITION_POLICY_BLOCKED"
    diagnostics = {
        "initial_score": score,
        "cooldown_seconds": MIN_ENTRY_INTERVAL_SECONDS,
        "cooldown_remaining_seconds": None if invalid_time else remaining,
        "latest_entry_server_time": latest or None,
        "latest_entry_age_seconds": age,
        "server_time": market.server_time,
        "riri_positions": len(positions),
        "riri_lot": round(lot, 8),
        "riri_profit": round(sum(p.profit for p in positions), 2),
        "foreign_positions": len(market.positions) - len(positions),
        "account_xauusd_gross_lot": round(sum(p.lot for p in market.positions), 8),
        "common_blockers": common,
        "action_blockers": blockers,
        "exceptions": exceptions,
    }
    return EntryEligibility(allowed, reason, reasons, required, diagnostics)


def entry_rejection(market, decision, *, initial_score: int) -> str | None:
    """Same policy enforced by risk and execution, not just by the AI prompt."""
    if decision is None or decision.decision not in {"BUY", "SELL"}:
        return "NO_SIGNAL"
    if decision.confidence < MIN_CONFIDENCE:
        return "CONFIDENCE_BELOW_60"
    gate = eligible_actions(market, initial_score=initial_score)
    action = decision.decision
    if action not in gate.allowed_actions:
        return gate.action_reasons[action]
    if decision.confidence < gate.required_confidence[action]:
        return "POSITION_EXCEPTION_REQUIRES_CONFIDENCE_ABOVE_80"
    return None
