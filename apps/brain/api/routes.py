import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from config.settings import settings
from config.trading_config import MAX_ACTIVE_TRADES, MIN_ENTRY_INTERVAL_SECONDS, SL_POINTS, TP_POINTS
from models.execution import ExecutionConfirmation, TradeCloseEvent
from models.market_data import MarketData
from models.status import StatusResponse
from research.fundamental_service import FundamentalService
from research.pattern_service import PatternService
from research.statistics_service import StatisticsService
from risk.risk import AIRisk
from scoring.scoring_engine import ScoringEngine
from security import MT5Identity, require_dashboard, require_mt5
from services.execution_service import ExecutionService
from services.market_store import market_store
from services.signal_store import signal_store
from services.snapshot_guard import snapshot_guard
from services.trade_journal import trade_journal
from trader.trader import AITrader
from utils.logger import logger


router = APIRouter()
scoring_engine = ScoringEngine()
statistics_service = StatisticsService()
fundamental_service = FundamentalService()
pattern_service = PatternService()
ai_trader = AITrader()
ai_risk = AIRisk()
execution_service = ExecutionService()


def serialize(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def assert_identity(data: MarketData, identity: MT5Identity) -> None:
    if (
        data.account_id != identity.account_id
        or data.terminal_id != identity.terminal_id
        or data.instance_id != identity.instance_id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="body/header identity mismatch")


def cooldown_status(data: MarketData) -> tuple[bool, str]:
    positions = [position for position in data.positions if position.symbol == data.symbol]
    if len(positions) >= MAX_ACTIVE_TRADES:
        return False, "MAX_ACTIVE_TRADES"
    if not positions:
        return True, "NO_ACTIVE_TRADES"
    times = [position.open_time for position in positions if position.open_time > 0]
    if not times:
        return False, "OPEN_TIME_UNAVAILABLE"
    if int(time.time()) - max(times) < MIN_ENTRY_INTERVAL_SECONDS:
        return False, "MIN_ENTRY_INTERVAL"
    return True, "COOLDOWN_COMPLETE"


@router.get("/health")
async def health():
    return {"status": "healthy"}


@router.get("/ready")
async def ready():
    missing = []
    if not settings.OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if len(settings.RIRI_MT5_API_KEY) < 32:
        missing.append("RIRI_MT5_API_KEY")
    if len(settings.RIRI_DASHBOARD_API_KEY) < 32:
        missing.append("RIRI_DASHBOARD_API_KEY")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "missing_configuration": missing},
        )
    return {"status": "ready"}


@router.get("/status", response_model=StatusResponse, dependencies=[Depends(require_dashboard)])
async def application_status():
    return StatusResponse(name=settings.APP_NAME, version=settings.APP_VERSION, status="running")


@router.post("/mt5/market")
async def receive_market_data(data: MarketData, identity: MT5Identity = Depends(require_mt5)):
    assert_identity(data, identity)
    key = identity.key
    market_age = int(time.time()) - data.market_time
    if market_age < 0 or market_age > settings.MAX_MARKET_AGE_SECONDS:
        raise HTTPException(status_code=422, detail="stale or future market snapshot")
    if not snapshot_guard.accept(key, data.market_time):
        raise HTTPException(status_code=409, detail="replayed or out-of-order market snapshot")
    market_store.begin_cycle(key, data)

    score = scoring_engine.calculate(data)
    statistics = statistics_service.analyze(data)
    fundamental = await fundamental_service.analyze(data.fundamental)
    pattern = pattern_service.analyze(data)
    for stage, value in (
        ("score", score), ("statistics", statistics),
        ("fundamental", fundamental), ("pattern", pattern),
    ):
        market_store.update_stage(key, stage, value)

    decision = risk = execution = None
    allowed, gate_reason = cooldown_status(data)
    if score.qualified and allowed:
        market_context = data.model_dump()
        market_context["target"] = {
            "tp_points": TP_POINTS,
            "sl_points": SL_POINTS,
            "buy_tp_price": round(data.ask + TP_POINTS * data.point, data.digits),
            "buy_sl_price": round(data.ask - SL_POINTS * data.point, data.digits),
            "sell_tp_price": round(data.bid - TP_POINTS * data.point, data.digits),
            "sell_sl_price": round(data.bid + SL_POINTS * data.point, data.digits),
        }
        decision = await ai_trader.decide(
            market=market_context,
            statistics=statistics,
            fundamental=fundamental,
            pattern=pattern,
        )
        market_store.update_stage(key, "decision", decision)
        risk = await ai_risk.evaluate(market=data, trader_decision=decision)
        market_store.update_stage(key, "risk", risk)
        execution = await execution_service.execute(decision=decision, risk=risk, market=data)
        market_store.update_stage(key, "execution", execution)
    elif score.qualified:
        logger.info(f"AI Trader skipped for {key}: {gate_reason}")

    event = "SIGNAL_CREATED" if execution and execution.signal_created else "ANALYSIS"
    journal_record = trade_journal.event(
        event,
        account_id=data.account_id,
        terminal_id=data.terminal_id,
        instance_id=data.instance_id,
        symbol=data.symbol,
        market_time=data.market_time,
        gate_reason=gate_reason,
        score=serialize(score),
        statistics=statistics,
        fundamental=fundamental,
        pattern=pattern,
        decision=serialize(decision),
        risk=serialize(risk),
        execution=serialize(execution),
    )
    market_store.update_stage(key, "journal", journal_record)

    return {
        "success": True,
        "score": score.score,
        "qualified": score.qualified,
        "gate_reason": gate_reason,
        "decision": serialize(decision),
        "risk": serialize(risk),
        "execution": serialize(execution),
    }


@router.get("/execution/pending")
async def execution_pending(identity: MT5Identity = Depends(require_mt5)):
    signal = signal_store.claim_signal(identity.key)
    if signal:
        logger.info(f"[SIGNAL] delivered identity={identity.key} signal_id={signal['signal_id']}")
    return {"signal": signal}


@router.post("/execution/confirm")
async def execution_confirm(
    payload: ExecutionConfirmation,
    identity: MT5Identity = Depends(require_mt5),
):
    confirmation_status = payload.status.upper()
    if confirmation_status not in {"EXECUTED", "REJECTED"}:
        raise HTTPException(status_code=422, detail="status must be EXECUTED or REJECTED")
    signal = signal_store.confirm(
        identity.key,
        payload.signal_id,
        payload.action,
        payload.requested_lot,
    )
    if signal is None:
        raise HTTPException(status_code=409, detail="signal missing, expired, or belongs to another identity")
    event = "TRADE_EXECUTED" if confirmation_status == "EXECUTED" else "TRADE_REJECTED"
    record = trade_journal.event(
        event,
        account_id=identity.account_id,
        terminal_id=identity.terminal_id,
        instance_id=identity.instance_id,
        signal=signal,
        confirmation=payload.model_dump(),
    )
    market_store.update_stage(identity.key, "journal", record)
    return {"success": True, "signal_id": payload.signal_id, "status": confirmation_status}


@router.post("/execution/trade-event")
async def execution_trade_event(
    payload: TradeCloseEvent,
    identity: MT5Identity = Depends(require_mt5),
):
    record = trade_journal.event(
        "TRADE_CLOSED",
        event_key=f"close:{identity.key}:{payload.deal_id}",
        account_id=identity.account_id,
        terminal_id=identity.terminal_id,
        instance_id=identity.instance_id,
        **payload.model_dump(),
    )
    market_store.update_stage(identity.key, "journal", record)
    return {"success": True, "deal_id": payload.deal_id}


@router.get("/dashboard/latest", dependencies=[Depends(require_dashboard)])
async def dashboard_latest():
    return market_store.snapshot()


@router.get("/mt5/latest", dependencies=[Depends(require_dashboard)])
async def latest_market():
    return market_store.get_stage("market") or {"message": "No market data available"}


@router.get("/score/latest", dependencies=[Depends(require_dashboard)])
async def latest_score():
    return market_store.get_stage("score") or {"message": "No score available"}


@router.get("/research/statistics", dependencies=[Depends(require_dashboard)])
async def latest_statistics():
    return market_store.get_stage("statistics") or {"message": "No statistics available"}


@router.get("/research/fundamental", dependencies=[Depends(require_dashboard)])
async def latest_fundamental():
    return market_store.get_stage("fundamental") or {"message": "No fundamental data available"}


@router.get("/research/pattern", dependencies=[Depends(require_dashboard)])
async def latest_pattern():
    return market_store.get_stage("pattern") or {"message": "No pattern available"}


@router.get("/trader/latest", dependencies=[Depends(require_dashboard)])
async def latest_decision():
    return market_store.get_stage("decision") or {"message": "No decision available"}


@router.get("/risk/latest", dependencies=[Depends(require_dashboard)])
async def latest_risk():
    return market_store.get_stage("risk") or {"message": "No risk available"}


@router.get("/execution/latest", dependencies=[Depends(require_dashboard)])
async def latest_execution():
    return market_store.get_stage("execution") or {"message": "No execution available"}


@router.get("/journal/latest", dependencies=[Depends(require_dashboard)])
async def latest_journal():
    return market_store.get_stage("journal") or {"message": "No journal available"}


@router.get("/journal/history", dependencies=[Depends(require_dashboard)])
async def journal_history():
    return trade_journal.latest(limit=100)


@router.get("/journal", dependencies=[Depends(require_dashboard)])
async def journal():
    return trade_journal.all()
