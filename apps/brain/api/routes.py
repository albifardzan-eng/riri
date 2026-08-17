from datetime import datetime, timezone

from fastapi import APIRouter

from models.status import StatusResponse
from models.market_data import MarketData

from config.settings import settings
from config.trading_config import MAX_ACTIVE_TRADES

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

scoring_engine = ScoringEngine()

statistics_service = StatisticsService()
fundamental_service = FundamentalService()
pattern_service = PatternService()

ai_trader = AITrader()
ai_risk = AIRisk()

execution_service = ExecutionService()


# ==================================================
# CONFIGURATION
# ==================================================

MIN_ENTRY_INTERVAL_SECONDS = 30 * 60


# ==================================================
# HELPERS
# ==================================================

def can_call_ai_trader(
    market: MarketData
) -> tuple[bool, str]:

    positions = market.positions

    active_trades = len(
        positions
    )

    # --------------------------------------------------
    # MAX ACTIVE TRADES
    # --------------------------------------------------

    if active_trades >= MAX_ACTIVE_TRADES:

        return (
            False,
            "MAX_ACTIVE_TRADES"
        )

    # --------------------------------------------------
    # FIRST TRADE
    #
    # No existing position means AI can evaluate
    # immediately once scoring qualifies.
    # --------------------------------------------------

    if active_trades == 0:

        return (
            True,
            "FIRST_ENTRY"
        )

    # --------------------------------------------------
    # FIND LATEST POSITION
    # --------------------------------------------------

    latest_open_time = max(
        (
            int(position.open_time)
            for position in positions
            if position.open_time > 0
        ),
        default=0
    )

    # --------------------------------------------------
    # NO VALID OPEN TIME
    # --------------------------------------------------

    if latest_open_time <= 0:

        return (
            False,
            "INVALID_POSITION_TIME"
        )

    # --------------------------------------------------
    # 30-MINUTE ENTRY INTERVAL
    # --------------------------------------------------

    now = int(
        datetime.now(
            timezone.utc
        ).timestamp()
    )

    elapsed_seconds = (
        now -
        latest_open_time
    )

    if elapsed_seconds < MIN_ENTRY_INTERVAL_SECONDS:

        remaining_seconds = (
            MIN_ENTRY_INTERVAL_SECONDS
            - elapsed_seconds
        )

        remaining_minutes = max(
            1,
            int(
                (
                    remaining_seconds
                    + 59
                ) / 60
            )
        )

        return (
            False,
            f"ENTRY_INTERVAL_{remaining_minutes}MIN"
        )

    return (
        True,
        "NEXT_ENTRY"
    )


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
    # MARKET
    # ==================================================

    market_store.update(
        data
    )

    # ==================================================
    # SCORING
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
    #
    # These services are local calculations.
    # They do NOT consume AI tokens.
    # ==================================================

    statistics = (
        statistics_service.analyze(
            data
        )
    )

    fundamental = (
    await fundamental_service.analyze(
        data
    )
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
    # DEFAULT RESULT
    # ==================================================

    decision = None
    risk = None
    execution = None

    # ==================================================
    # CHECK WHETHER AI TRADER MAY BE CALLED
    # ==================================================

    ai_allowed, ai_reason = (
        can_call_ai_trader(
            data
        )
    )

    # ==================================================
    # AI PIPELINE
    # ==================================================

    if score.qualified and ai_allowed:

        # ==============================================
        # AI TRADER
        # ==============================================

        decision = (
            await ai_trader.decide(

                # --------------------------------------
                # MARKET
                # --------------------------------------
                market={
                    "symbol": data.symbol,

                    "bid": data.bid,

                    "ask": data.ask,

                    "spread": data.spread,

                    "atr": data.atr,

                    "tick_volume": data.tick_volume,

                    "equity": data.equity,

                    "free_margin": data.free_margin,

                    "positions": [
                        position.model_dump()
                        for position
                        in data.positions
                    ],

                    # Full candle history
                    # is required for:
                    # - reversal
                    # - SNR
                    # - exhaustion
                    # - failed breakout
                    # - candle sequence
                    "candles": [
                        candle.model_dump()
                        for candle
                        in data.candles
                    ]
                },

                # --------------------------------------
                # RESEARCH
                # --------------------------------------

                statistics=statistics,

                fundamental=fundamental,

                pattern=pattern
            )
        )

        market_store.update_decision(
            decision
        )

        # ==============================================
        # AI RISK
        # ==============================================

        risk = (
            await ai_risk.evaluate(
                market=data,
                trader_decision=decision
            )
        )

        market_store.update_risk(
            risk
        )

        # ==============================================
        # EXECUTION
        # ==============================================

        execution = (
            await execution_service.execute(
                decision,
                risk,
                data
            )
        )

        market_store.update_execution(
            execution
        )

        # ==============================================
        # JOURNAL
        # ==============================================

        journal_record = {

            "symbol": data.symbol,

            "score": (
                score.model_dump()
            ),

            "statistics": statistics,

            "fundamental": fundamental,

            "pattern": pattern,

            "decision": (
                decision.model_dump()
                if decision
                else None
            ),

            "risk": (
                risk.model_dump()
                if risk
                else None
            ),

            "execution": (
                execution.model_dump()
                if execution
                else None
            ),

            "ai_call_reason": ai_reason
        }

        trade_journal.write(
            journal_record
        )

        market_store.update_journal(
            journal_record
        )

    # ==================================================
    # AI NOT CALLED
    #
    # Important:
    #
    # Qualified=False
    #     -> scoring rejected
    #
    # MAX_ACTIVE_TRADES
    #     -> already 3 positions
    #
    # ENTRY_INTERVAL
    #     -> less than 30 minutes
    #
    # This prevents unnecessary AI API calls.
    # ==================================================

    else:

        if not score.qualified:

            ai_reason = (
                "SCORE_NOT_QUALIFIED"
            )

        # No AI decision is generated here.

    # ==================================================
    # WEBSOCKET
    # ==================================================

    await manager.broadcast(
        {
            "type": "market_update",

            "market": (
                data.model_dump()
            ),

            "score": (
                score.model_dump()
            ),

            "statistics": statistics,

            "fundamental": fundamental,

            "pattern": pattern,

            "decision": (
                decision.model_dump()
                if decision
                else None
            ),

            "risk": (
                risk.model_dump()
                if risk
                else None
            ),

            "execution": (
                execution.model_dump()
                if execution
                else None
            ),

            "ai_allowed": ai_allowed,

            "ai_call_reason": ai_reason
        }
    )

    # ==================================================
    # LOG
    # ==================================================

    logger.info(
        f"Score={score.score} "
        f"Qualified={score.qualified} "
        f"AIAllowed={ai_allowed} "
        f"AIReason={ai_reason}"
    )

    # ==================================================
    # RESPONSE
    # ==================================================

    return {

        "success": True,

        "score": score.score,

        "qualified": score.qualified,

        "ai_allowed": ai_allowed,

        "ai_call_reason": ai_reason,

        "decision": (
            decision.model_dump()
            if decision
            else None
        ),

        "risk": (
            risk.model_dump()
            if risk
            else None
        ),

        "execution": (
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
            "message": "No market data available"
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
            "message": "No score available"
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
            "message": "No statistics available"
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
            "message": "No fundamental data available"
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
            "message": "No pattern data available"
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
            "message": "No decision available"
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
            "message": "No risk available"
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
            "message": "No execution available"
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
            "message": "No journal available"
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
            "signal": None
        }

    return signal


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
        "success": True
    }


# ==================================================
# FULL JOURNAL
# ==================================================

@router.get("/journal")
async def journal():

    return trade_journal.all()