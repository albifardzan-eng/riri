from fastapi import APIRouter

from models.status import StatusResponse
from models.market_data import MarketData

from config.settings import settings

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

    # --------------------------------------------------
    # MARKET
    # --------------------------------------------------

    market_store.update(data)

    # --------------------------------------------------
    # SCORING
    # --------------------------------------------------

    score = scoring_engine.calculate(
        data
    )

    market_store.update_score(
        score
    )

    # --------------------------------------------------
    # RESEARCH
    # --------------------------------------------------

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

    # --------------------------------------------------
    # DEFAULT RESULT
    # --------------------------------------------------

    decision = None
    risk = None
    execution = None

    # --------------------------------------------------
    # AI PIPELINE
    # --------------------------------------------------

    if score.qualified:

        # ----------------------------------------------
        # AI TRADER
        # ----------------------------------------------

        decision = (
            await ai_trader.decide(
                market={
                    "symbol": data.symbol,
                    "bid": data.bid,
                    "ask": data.ask,
                    "spread": data.spread,
                    "atr": data.atr,
                    "tick_volume": data.tick_volume
                },
                statistics=statistics,
                fundamental=fundamental,
                pattern=pattern
            )
        )

        market_store.update_decision(
            decision
        )

        # ----------------------------------------------
        # AI RISK
        # ----------------------------------------------

        risk = (
            await ai_risk.evaluate(
                market=data,
                trader_decision=decision
            )
        )

        market_store.update_risk(
            risk
        )

        # ----------------------------------------------
        # EXECUTION
        # ----------------------------------------------

        execution = (
            await execution_service.execute(
                decision,
                risk
            )
        )

        market_store.update_execution(
            execution
        )

        # ----------------------------------------------
        # JOURNAL
        # ----------------------------------------------

        journal_record = {
            "symbol": data.symbol,

            "score": score.model_dump(),

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
            )
        }

        trade_journal.write(
            journal_record
        )

        market_store.update_journal(
            journal_record
        )

    # --------------------------------------------------
    # WEBSOCKET
    # --------------------------------------------------

    await manager.broadcast(
        {
            "type": "market_update",

            "market": data.model_dump(),

            "score": score.model_dump(),

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
            )
        }
    )

    # --------------------------------------------------
    # LOG
    # --------------------------------------------------

    logger.info(
        f"Score={score.score} "
        f"Qualified={score.qualified}"
    )

    # --------------------------------------------------
    # RESPONSE
    # --------------------------------------------------

    return {
        "success": True,

        "score": score.score,

        "qualified": score.qualified,

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

    market = market_store.get()

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

    score = market_store.get_score()

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

    risk = market_store.get_risk()

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