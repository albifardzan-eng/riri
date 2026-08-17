from fastapi import APIRouter
import time

from models.status import StatusResponse
from models.market_data import MarketData

from config.settings import settings
from config.trading_config import (
    MIN_SCORE,
    MAX_ACTIVE_TRADES
)

from services.market_store import market_store
from services.execution_service import ExecutionService
from services.trade_journal import trade_journal
from services.signal_store import signal_store

from scoring.scoring_engine import ScoringEngine

from trader.trader import AITrader
from risk.risk import AIRisk

from utils.logger import logger

from websocket.websocket_server import manager

from research.statistics_service import StatisticsService
from research.fundamental_service import FundamentalService
from research.pattern_service import PatternService


router = APIRouter()


# ==================================================
# SERVICES
# ==================================================

scoring_engine = ScoringEngine()

statistics_service = StatisticsService()

fundamental_service = FundamentalService()

pattern_service = PatternService()

ai_trader = AITrader()

ai_risk = AIRisk()

execution_service = ExecutionService()


# ==================================================
# TRADE COOLDOWN
# ==================================================

TRADE_COOLDOWN_SECONDS = 30 * 60


def get_trade_cooldown_status(
    positions,
    symbol
):
    """
    Determine whether AI Trader is allowed to be called.

    Rules:

    0 active trades
        -> AI Trader allowed

    1 active trade
        -> wait 30 minutes from trade #1 open_time

    2 active trades
        -> wait 30 minutes from trade #2 open_time

    3 active trades
        -> AI Trader must NOT be called

    Cooldown is based on the most recently opened
    active trade.
    """

    active_positions = [
        position
        for position in positions
        if position.symbol == symbol
    ]

    active_trade_count = len(
        active_positions
    )

    # ==================================================
    # MAX ACTIVE TRADES
    # ==================================================

    if active_trade_count >= MAX_ACTIVE_TRADES:

        return {
            "allowed": False,
            "reason": "MAX_ACTIVE_TRADES",
            "remaining_seconds": 0
        }

    # ==================================================
    # NO ACTIVE TRADE
    # ==================================================

    if active_trade_count == 0:

        return {
            "allowed": True,
            "reason": "NO_ACTIVE_TRADES",
            "remaining_seconds": 0
        }

    # ==================================================
    # FIND MOST RECENT OPEN TRADE
    # ==================================================

    valid_open_times = [
        int(position.open_time)
        for position in active_positions
        if position.open_time > 0
    ]

    # ==================================================
    # SAFETY:
    # If MT5 does not provide open_time,
    # do NOT block the system indefinitely.
    #
    # Existing positions with unknown open_time
    # cannot be reliably used to calculate cooldown.
    # ==================================================

    if not valid_open_times:

        return {
            "allowed": True,
            "reason": "OPEN_TIME_UNAVAILABLE",
            "remaining_seconds": 0
        }

    latest_open_time = max(
        valid_open_times
    )

    now = int(
        time.time()
    )

    elapsed_seconds = (
        now -
        latest_open_time
    )

    remaining_seconds = max(
        0,
        TRADE_COOLDOWN_SECONDS -
        elapsed_seconds
    )

    # ==================================================
    # COOLDOWN ACTIVE
    # ==================================================

    if remaining_seconds > 0:

        return {
            "allowed": False,
            "reason": "TRADE_COOLDOWN",
            "remaining_seconds":
                remaining_seconds
        }

    # ==================================================
    # COOLDOWN COMPLETE
    # ==================================================

    return {
        "allowed": True,
        "reason": "COOLDOWN_COMPLETE",
        "remaining_seconds": 0
    }


# ==================================================
# HEALTH
# ==================================================

@router.get("/health")
async def health():

    return {
        "status": "healthy"
    }


# ==================================================
# STATUS
# ==================================================

@router.get(
    "/status",
    response_model=StatusResponse
)
async def status():

    return StatusResponse(
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        status="running"
    )


# ==================================================
# RECEIVE MARKET DATA
# ==================================================

@router.post("/mt5/market")
async def receive_market_data(
    data: MarketData
):

    # ==================================================
    # STORE MARKET
    # ==================================================

    market_store.update(
        data
    )

    # ==================================================
    # SCORING ENGINE
    # ==================================================

    score = (
        scoring_engine.calculate(
            data
        )
    )

    market_store.update_score(
        score
    )

    # ==================================================
    # RESEARCH
    # ==================================================

    statistics = (
        statistics_service.analyze(
            data
        )
    )

    fundamental = (
        await fundamental_service.analyze()
    )

    pattern = (
        pattern_service.analyze(
            data
        )
    )

    market_store.update_statistics(
        statistics
    )

    market_store.update_fundamental(
        fundamental
    )

    market_store.update_pattern(
        pattern
    )

    # ==================================================
    # DEFAULT PIPELINE RESULT
    # ==================================================

    decision = None

    risk = None

    execution = None

    journal_record = None

    # ==================================================
    # SCORE QUALIFICATION
    #
    # Score < MIN_SCORE:
    # Do NOT call AI Trader.
    # ==================================================

    if score.qualified:

        # ==================================================
        # TRADE COOLDOWN / ACTIVE TRADE CONTROL
        #
        # IMPORTANT:
        # This check happens BEFORE AI Trader.
        #
        # Therefore AI Trader will NOT be called when:
        #
        # 1. There are already 3 active trades
        # 2. The latest active trade is less than
        #    30 minutes old
        #
        # Example:
        #
        # Trade #1 opened 10:00
        # AI Trader cannot be called again before 10:30
        #
        # Trade #2 opened 10:35
        # AI Trader cannot be called again before 11:05
        # ==================================================

        cooldown = (
            get_trade_cooldown_status(
                positions=data.positions,
                symbol=data.symbol
            )
        )

        if cooldown["allowed"]:

            # ==================================================
            # AI TRADER
            # ==================================================

            decision = (
                await ai_trader.decide(

                    market={
                        "symbol":
                        data.symbol,

                        "bid":
                        data.bid,

                        "ask":
                        data.ask,

                        "spread":
                        data.spread,

                        "atr":
                        data.atr,

                        "tick_volume":
                        data.tick_volume,

                        "balance":
                        data.balance,

                        "equity":
                        data.equity,

                        "free_margin":
                        data.free_margin,

                        "candles": [
                            candle.model_dump()
                            for candle
                            in data.candles
                        ],

                        "positions": [
                            position.model_dump()
                            for position
                            in data.positions
                        ]
                    },

                    statistics=statistics,

                    fundamental=fundamental,

                    pattern=pattern
                )
            )

            # ==================================================
            # STORE AI DECISION
            # ==================================================

            market_store.update_decision(
                decision
            )

            # ==================================================
            # AI RISK
            # ==================================================

            risk = (
                await ai_risk.evaluate(

                    market=data,

                    trader_decision=decision
                )
            )

            market_store.update_risk(
                risk
            )

            # ==================================================
            # EXECUTION
            # ==================================================

            execution = (
                await execution_service.execute(

                    decision=decision,

                    risk=risk,

                    market=data
                )
            )

            market_store.update_execution(
                execution
            )

            # ==================================================
            # JOURNAL
            # ==================================================

            journal_record = {

                "symbol":
                data.symbol,

                "score":
                score.model_dump(),

                "statistics":
                statistics,

                "fundamental":
                fundamental,

                "pattern":
                pattern,

                "decision":
                (
                    decision.model_dump()
                    if decision
                    else None
                ),

                "risk":
                (
                    risk.model_dump()
                    if risk
                    else None
                ),

                "execution":
                (
                    execution.model_dump()
                    if execution
                    else None
                )
            }

            trade_journal.write(
                journal_record
            )

            market_store.update_journal(
                journal_record
            )

        else:

            # ==================================================
            # COOLDOWN / MAX TRADE
            #
            # AI Trader is NOT called.
            # ==================================================

            logger.info(
                f"AI Trader skipped: "
                f"reason={cooldown['reason']} "
                f"remaining="
                f"{cooldown['remaining_seconds']}s "
                f"active_trades="
                f"{len(data.positions)}"
            )

    # ==================================================
    # WEBSOCKET
    # ==================================================

    await manager.broadcast(
        {

            "type":
            "market_update",

            "market":
            data.model_dump(),

            "score":
            score.model_dump(),

            "statistics":
            statistics,

            "fundamental":
            fundamental,

            "pattern":
            pattern,

            "decision":
            (
                decision.model_dump()
                if decision
                else None
            ),

            "risk":
            (
                risk.model_dump()
                if risk
                else None
            ),

            "execution":
            (
                execution.model_dump()
                if execution
                else None
            )
        }
    )

    # ==================================================
    # LOG
    # ==================================================

    logger.info(
        f"Score={score.score} "
        f"Qualified={score.qualified} "
        f"Decision="
        f"{decision.decision if decision else 'NONE'} "
        f"Risk="
        f"{risk.approved if risk else 'NONE'} "
        f"Execution="
        f"{execution.executed if execution else 'NONE'}"
    )

    # ==================================================
    # RESPONSE
    # ==================================================

    return {

        "success":
        True,

        "score":
        score.score,

        "qualified":
        score.qualified,

        "decision":
        (
            decision.model_dump()
            if decision
            else None
        ),

        "risk":
        (
            risk.model_dump()
            if risk
            else None
        ),

        "execution":
        (
            execution.model_dump()
            if execution
            else None
        )
    }


# ==================================================
# LATEST MARKET
# ==================================================

@router.get("/mt5/latest")
async def latest_market():

    market = (
        market_store.get()
    )

    if market is None:

        return {
            "message":
            "No market data available"
        }

    return market


# ==================================================
# LATEST SCORE
# ==================================================

@router.get("/score/latest")
async def latest_score():

    score = (
        market_store.get_score()
    )

    if score is None:

        return {
            "message":
            "No score available"
        }

    return score


# ==================================================
# LATEST STATISTICS
# ==================================================

@router.get("/research/statistics")
async def latest_statistics():

    statistics = (
        market_store.get_statistics()
    )

    if statistics is None:

        return {
            "message":
            "No statistics available"
        }

    return statistics


# ==================================================
# LATEST FUNDAMENTAL
# ==================================================

@router.get("/research/fundamental")
async def latest_fundamental():

    fundamental = (
        market_store.get_fundamental()
    )

    if fundamental is None:

        return {
            "message":
            "No fundamental data available"
        }

    return fundamental


# ==================================================
# LATEST PATTERN
# ==================================================

@router.get("/research/pattern")
async def latest_pattern():

    pattern = (
        market_store.get_pattern()
    )

    if pattern is None:

        return {
            "message":
            "No pattern available"
        }

    return pattern


# ==================================================
# LATEST TRADER DECISION
# ==================================================

@router.get("/trader/latest")
async def latest_decision():

    decision = (
        market_store.get_decision()
    )

    if decision is None:

        return {
            "message":
            "No decision available"
        }

    return decision


# ==================================================
# LATEST RISK
# ==================================================

@router.get("/risk/latest")
async def latest_risk():

    risk = (
        market_store.get_risk()
    )

    if risk is None:

        return {
            "message":
            "No risk available"
        }

    return risk


# ==================================================
# LATEST EXECUTION
# ==================================================

@router.get("/execution/latest")
async def latest_execution():

    execution = (
        market_store.get_execution()
    )

    if execution is None:

        return {
            "message":
            "No execution available"
        }

    return execution


# ==================================================
# LATEST JOURNAL
# ==================================================

@router.get("/journal/latest")
async def latest_journal():

    journal = (
        market_store.get_journal()
    )

    if journal is None:

        return {
            "message":
            "No journal available"
        }

    return journal


# ==================================================
# JOURNAL HISTORY
# ==================================================

@router.get("/journal/history")
async def journal_history():

    return trade_journal.latest(
        limit=100
    )


# ==================================================
# PENDING EXECUTION SIGNAL
# ==================================================

@router.get("/execution/pending")
async def execution_pending():

    signal = (
        signal_store.get_signal()
    )

    if signal is None:

        return {
            "signal":
            None
        }

    return {
        "signal":
        signal
    }


# ==================================================
# CONFIRM EXECUTION
# ==================================================

@router.post("/execution/confirm")
async def execution_confirm(
    payload: dict
):

    trade_journal.add(
        payload
    )

    signal_store.clear()

    return {
        "success":
        True
    }


# ==================================================
# FULL JOURNAL
# ==================================================

@router.get("/journal")
async def journal():

    return trade_journal.all()