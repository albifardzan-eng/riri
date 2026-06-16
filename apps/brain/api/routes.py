from fastapi import APIRouter

from models.status import StatusResponse
from models.market_data import MarketData

from config.settings import settings

from services.market_store import market_store

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


@router.get("/health")
async def health():
    return {
        "status": "healthy"
    }


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


@router.post("/mt5/market")
async def receive_market_data(
    data: MarketData
):

    # Market

    market_store.update(data)

    # Score

    score = scoring_engine.calculate(data)

    market_store.update_score(score)

    # Research

    statistics = statistics_service.analyze(data)

    fundamental = (
        await fundamental_service.analyze()
    )

    pattern = pattern_service.analyze(data)

    market_store.update_statistics(
        statistics
    )

    market_store.update_fundamental(
        fundamental
    )

    market_store.update_pattern(
        pattern
    )

    # AI Trader

    decision = None
    risk = None

    if score.qualified:

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

        # AI Risk

        risk = await ai_risk.evaluate(
            market=data,
            trader_decision=decision
        )

        market_store.update_risk(
            risk
        )

    # Broadcast

    await manager.broadcast(
        {
            "type": "market_update",

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
            )
        }
    )

    logger.info(
        f"Score={score.score} "
        f"Qualified={score.qualified}"
    )

    return {
        "success": True,

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
        )
    }


@router.get("/mt5/latest")
async def latest_market():

    market = market_store.get()

    if market is None:

        return {
            "message":
            "No market data available"
        }

    return market


@router.get("/score/latest")
async def latest_score():

    score = market_store.get_score()

    if score is None:

        return {
            "message":
            "No score available"
        }

    return score


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


@router.get("/research/pattern")
async def latest_pattern():

    pattern = (
        market_store.get_pattern()
    )

    if pattern is None:

        return {
            "message":
            "No pattern data available"
        }

    return pattern


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


@router.get("/risk/latest")
async def latest_risk():

    risk = market_store.get_risk()

    if risk is None:

        return {
            "message":
            "No risk available"
        }

    return risk