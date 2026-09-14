import asyncio
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from config.settings import settings
from config.trading_config import SL_POINTS, TP_POINTS
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
from services.ai_call_gate import ai_call_gate
from services.entry_eligibility import eligible_actions
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

# MT5 can submit a newer snapshot while a qualified snapshot is waiting for
# the model. Serialize only each account/terminal/instance pipeline so that a
# newer request cannot replace the durable cycle underneath an in-flight
# decision. Distinct identities remain independent.
_pipeline_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def serialize(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def assert_identity(data: MarketData, identity: MT5Identity) -> None:
    if (
        data.account_id != identity.account_id
        or data.terminal_id != identity.terminal_id
        or data.instance_id != identity.instance_id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="body/header identity mismatch")


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
    async with _pipeline_locks[key]:
        # Check age after queueing: a delayed snapshot must fail closed rather
        # than run after a previous AI call has completed.
        market_age = int(time.time()) - data.market_time
        if market_age < 0 or market_age > settings.MAX_MARKET_AGE_SECONDS:
            raise HTTPException(status_code=422, detail="stale or future market snapshot")
        if not snapshot_guard.accept(key, data.market_time):
            raise HTTPException(status_code=409, detail="replayed or out-of-order market snapshot")
        cycle_id = market_store.begin_cycle(key, data)
        try:
            return await analyze_market_cycle(data, key, cycle_id)
        except (Exception, asyncio.CancelledError) as exc:
            reason = "CYCLE_SUPERSEDED" if isinstance(exc, HTTPException) and exc.status_code == 409 else "PIPELINE_ERROR"
            if isinstance(exc, asyncio.CancelledError):
                reason = "PIPELINE_INTERRUPTED"
            pipeline = {
                "status": "SKIPPED" if reason == "CYCLE_SUPERSEDED" else "ERROR",
                "stage": "STOPPED", "reason": reason,
            }
            market_store.update_stage(key, "pipeline", pipeline, cycle_id=cycle_id)
            trade_journal.event(
                "ANALYSIS", account_id=data.account_id, terminal_id=data.terminal_id,
                instance_id=data.instance_id, symbol=data.symbol, market_time=data.market_time,
                pipeline={**pipeline, "cycle_id": cycle_id}, gate_reason=reason,
            )
            logger.warning(f"Market pipeline stopped: {reason}")
            if isinstance(exc, (HTTPException, asyncio.CancelledError)):
                raise
            raise HTTPException(status_code=503, detail="market analysis failed") from None


async def analyze_market_cycle(data: MarketData, key: str, cycle_id: str):
    def update(stage, value):
        if not market_store.update_stage(key, stage, value, cycle_id=cycle_id):
            raise HTTPException(status_code=409, detail="market analysis superseded by newer snapshot")

    score = scoring_engine.calculate(data)
    statistics = statistics_service.analyze(data)
    fundamental = await fundamental_service.analyze(data.fundamental)
    pattern = pattern_service.analyze(data)
    for stage, value in (
        ("score", score), ("statistics", statistics),
        ("fundamental", fundamental), ("pattern", pattern),
    ):
        update(stage, value)

    decision = risk = execution = None
    eligibility = eligible_actions(data, initial_score=score.score)
    allowed_actions = eligibility.allowed_actions
    gate_reason = eligibility.reason
    ai_gate = {
        "call": False,
        "reason": "AI_SKIPPED_ENTRY_COOLDOWN" if gate_reason == "MIN_ENTRY_INTERVAL" else f"AI_SKIPPED_{gate_reason}",
        "allowed_actions": list(allowed_actions),
        "action_reasons": eligibility.action_reasons,
        "required_confidence": eligibility.required_confidence,
        "diagnostics": eligibility.diagnostics,
        "retry_after_seconds": 0,
        "news_changed": False,
    }
    if not score.qualified:
        gate_reason = "SCORE_BELOW_THRESHOLD"
        ai_gate["reason"] = "AI_SKIPPED_SCORE_BELOW_70"
    elif signal_store.get_signal(key) is not None:
        gate_reason = "SIGNAL_PENDING"
        ai_gate["reason"] = "AI_SKIPPED_SIGNAL_PENDING"
    elif allowed_actions:
        gate_result = ai_call_gate.claim(key, fundamental, opportunity={
            "candle_time": max(c.time for c in data.candles),
            "mid": (data.bid + data.ask) / 2,
            "atr": data.atr,
            "point": data.point,
            "required_confidence": {action: eligibility.required_confidence[action] for action in allowed_actions},
        })
        ai_gate.update(
            call=gate_result.call,
            reason=gate_result.reason,
            news_changed=gate_result.news_changed,
            retry_after_seconds=gate_result.retry_after_seconds,
        )
        if not gate_result.call:
            gate_reason = gate_result.reason

    update("ai_gate", ai_gate)

    if score.qualified and allowed_actions and ai_gate["call"]:
        update("pipeline", {"stage": "AI"})
        market_context = data.model_dump()
        market_context["entry_policy"] = eligibility.diagnostics
        market_context["required_confidence"] = eligibility.required_confidence
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
            allowed_actions=allowed_actions,
            required_confidence=eligibility.required_confidence,
        )
        update("decision", decision)
        update("pipeline", {"stage": "RISK"})
        risk = await ai_risk.evaluate(market=data, trader_decision=decision, initial_score=score.score)
        update("risk", risk)
        update("pipeline", {"stage": "EXECUTION"})
        execution = await execution_service.execute(decision=decision, risk=risk, market=data,
                                                    initial_score=score.score)
        update("execution", execution)
    else:
        if score.qualified and not allowed_actions and gate_reason == "PASS":
            gate_reason = "NO_EXECUTABLE_DIRECTION"
        if score.qualified:
            logger.info(
                f"AI Trader skipped for {key}: {ai_gate['reason']} ({gate_reason}) "
                f"CooldownRemaining={eligibility.diagnostics['cooldown_remaining_seconds']} "
                f"BUY={eligibility.action_reasons['BUY']} SELL={eligibility.action_reasons['SELL']} "
                f"Blockers={eligibility.diagnostics['action_blockers']}"
            )

    pipeline = {"cycle_id": cycle_id, "status": "COMPLETED", "stage": "DONE", "reason": None}
    if decision is None:
        pipeline.update(status="SKIPPED", reason=gate_reason)
    elif decision.status in {"ERROR", "UNAVAILABLE"}:
        pipeline.update(status="ERROR", reason=decision.reason)
    # Persist the final marker only after the journal and all stages exist.
    event = "SIGNAL_CREATED" if execution and execution.signal_created else "ANALYSIS"
    journal_record = trade_journal.event(
        event,
        account_id=data.account_id,
        terminal_id=data.terminal_id,
        instance_id=data.instance_id,
        symbol=data.symbol,
        market_time=data.market_time,
        gate_reason=gate_reason,
        ai_gate=ai_gate,
        pipeline=pipeline,
        score=serialize(score),
        statistics=statistics,
        fundamental=fundamental,
        pattern=pattern,
        decision=serialize(decision),
        risk=serialize(risk),
        execution=serialize(execution),
    )
    update("journal", journal_record)
    update("pipeline", pipeline)

    return {
        "success": True,
        "score": score.score,
        "qualified": score.qualified,
        "gate_reason": gate_reason,
        "ai_gate": ai_gate,
        "pipeline": pipeline,
        "decision": serialize(decision),
        "risk": serialize(risk),
        "execution": serialize(execution),
        # Flat, non-sensitive MT5 telemetry. The EA logs this immediately so
        # an operator can correlate score, AI probability, risk and order
        # outcome without parsing nested JSON or exposing credentials.
        "ai_called": ai_gate["call"],
        "ai_gate_reason": ai_gate["reason"],
        "ai_decision": decision.decision if decision else "NONE",
        "ai_confidence": decision.confidence if decision else 0,
        "ai_status": decision.status if decision else "NOT_CALLED",
        "ai_reason": decision.reason if decision else gate_reason,
        "risk_approved": risk.approved if risk else False,
        "risk_reason": risk.reason if risk else gate_reason,
        "execution_reason": execution.reason if execution else gate_reason,
        "signal_lot": execution.lot if execution and execution.signal_created else 0.0,
        "cooldown_remaining_seconds": eligibility.diagnostics["cooldown_remaining_seconds"],
        "latest_entry_age_seconds": eligibility.diagnostics["latest_entry_age_seconds"],
        "latest_entry_server_time": eligibility.diagnostics["latest_entry_server_time"],
        "riri_position_count": eligibility.diagnostics["riri_positions"],
        "foreign_position_count": eligibility.diagnostics["foreign_positions"],
        "riri_position_profit": eligibility.diagnostics["riri_profit"],
        "buy_gate_reason": eligibility.action_reasons["BUY"],
        "sell_gate_reason": eligibility.action_reasons["SELL"],
        "buy_blockers": "|".join(eligibility.diagnostics["action_blockers"]["BUY"]) or "NONE",
        "sell_blockers": "|".join(eligibility.diagnostics["action_blockers"]["SELL"]) or "NONE",
        "buy_min_confidence": eligibility.required_confidence["BUY"],
        "sell_min_confidence": eligibility.required_confidence["SELL"],
        "ai_retry_after_seconds": ai_gate["retry_after_seconds"],
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
