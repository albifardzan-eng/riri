"""Offline regression tests: no live credentials, broker calls or production DBs."""
import asyncio
import json
import tempfile
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import test_rules as fixtures  # Sets isolated environment before app imports.
import httpx
from openai import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError

from api import routes
from config.settings import Settings
from models.trader_decision import TraderDecision
from security import MT5Identity
from services.market_store import MarketStore
from services.trade_journal import TradeJournal
from services.ai_call_gate import AICallGate
from services.entry_eligibility import eligible_actions
from services.signal_store import signal_store
from trader.trader import AITrader


class DecisionDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def decide(self, response=None, error=None):
        trader = AITrader()
        create = AsyncMock(return_value=response, side_effect=error)
        trader.client = NS(responses=NS(create=create))
        result = await trader.decide({}, {}, {}, {})
        self.assertEqual(create.await_count, 1, "Do not retry or bill twice")
        return result

    async def test_none_and_filtered_are_not_api_errors(self):
        for direction, confidence, expected in [
            ("NONE", 80, ("NONE", 0, "COMPLETED", "AI_NO_TRADE")),
            ("BUY", 59, ("NONE", 0, "FILTERED", "CONFIDENCE_BELOW_60")),
            ("BUY", 60, ("BUY", 60, "COMPLETED", "AI_DIRECTION_SELECTED_REDUCED_RISK")),
            ("SELL", 70, ("SELL", 70, "COMPLETED", "AI_DIRECTION_SELECTED")),
        ]:
            with self.subTest(direction=direction):
                result = await self.decide(NS(status="completed", output_text=json.dumps({
                    "decision": direction, "confidence": confidence,
                })))
                self.assertEqual((result.decision, result.confidence, result.status, result.reason), expected)

    async def test_incomplete_captures_usage_but_never_partial_direction(self):
        result = await self.decide(NS(
            status="incomplete", incomplete_details=NS(reason="max_output_tokens"),
            output_text='{"decision":"BUY","confidence":99}',
            usage=NS(input_tokens=1500, output_tokens=2048,
                     output_tokens_details=NS(reasoning_tokens=2048)),
        ))
        self.assertEqual((result.decision, result.confidence, result.reason), ("NONE", 0, "AI_MAX_OUTPUT_TOKENS"))
        self.assertEqual((result.input_tokens, result.output_tokens, result.reasoning_tokens), (1500, 2048, 2048))
        self.assertGreaterEqual(result.latency_ms, 0)

    async def test_empty_refusal_and_missing_status_are_distinct_failures(self):
        for response, reason in [
            (NS(status="completed", output_text=""), "AI_EMPTY_OUTPUT"),
            (NS(status="completed", output_text="", output=[NS(content=[NS(type="refusal")])]), "AI_REFUSAL"),
            (NS(output_text='{"decision":"BUY","confidence":90}'), "AI_RESPONSE_NOT_COMPLETED"),
        ]:
            with self.subTest(reason=reason):
                result = await self.decide(response)
                self.assertEqual((result.decision, result.confidence, result.status, result.reason), ("NONE", 0, "ERROR", reason))

    async def test_invalid_payloads_fail_closed(self):
        for payload in [[], {}, {"decision": "BUY", "confidence": True},
                        {"decision": "SELL", "confidence": 101},
                        {"decision": "HOLD", "confidence": 80}]:
            with self.subTest(payload=payload):
                result = await self.decide(NS(status="completed", output_text=json.dumps(payload)))
                self.assertEqual((result.decision, result.reason), ("NONE", "AI_INVALID_OUTPUT"))

    async def test_provider_errors_are_sanitized_and_not_retried(self):
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(429, request=request)
        cases = [
            (RateLimitError("sensitive", response=response, body={"code": "credit_balance_exhausted"}), "AI_QUOTA_EXHAUSTED"),
            (RateLimitError("sensitive", response=response, body={"error": {"type": "insufficient_quota"}}), "AI_QUOTA_EXHAUSTED"),
            (RateLimitError("sensitive", response=response, body={"code": "rate_limit_exceeded"}), "AI_RATE_LIMITED"),
            (APITimeoutError(request=request), "AI_TIMEOUT"),
            (APIConnectionError(request=request), "AI_CONNECTION_ERROR"),
            (AuthenticationError("sensitive", response=response, body=None), "AI_ACCESS_DENIED"),
            (RuntimeError("sensitive"), "AI_API_ERROR"),
        ]
        for error, reason in cases:
            with self.subTest(reason=reason):
                result = await self.decide(error=error)
                self.assertEqual((result.decision, result.confidence, result.status, result.reason), ("NONE", 0, "ERROR", reason))
                self.assertNotIn("sensitive", result.model_dump_json())

    async def test_unconfigured_is_not_a_normal_none(self):
        trader = AITrader()
        trader.client = None
        result = await trader.decide({}, {}, {}, {})
        self.assertEqual((result.status, result.reason), ("UNAVAILABLE", "AI_NOT_CONFIGURED"))

    def test_budget_default_and_legacy_decision(self):
        self.assertEqual(Settings.model_fields["OPENAI_MAX_OUTPUT_TOKENS"].default, 2048)
        self.assertEqual(TraderDecision(decision="NONE", confidence=0).status, "UNKNOWN")


class CycleDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = MarketStore(self.directory.name)
        self.journal = TradeJournal(self.directory.name)
        self.ai_gate = AICallGate(self.directory.name, interval_seconds=60)
        for name, value in [
            ("market_store", self.store),
            ("trade_journal", self.journal),
            ("ai_call_gate", self.ai_gate),
        ]:
            patcher = patch.object(routes, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.market = fixtures.market(account_id="observability")
        self.key = self.market.identity_key
        signal_store.clear(self.key)
        self.addCleanup(signal_store.clear, self.key)
        score = fixtures.ScoringEngine().calculate(self.market).model_copy(update={"score": 85, "qualified": True})
        patcher = patch.object(routes.scoring_engine, "calculate", return_value=score)
        self.calculate = patcher.start()
        self.addCleanup(patcher.stop)

    async def run_cycle(self):
        cycle = self.store.begin_cycle(self.key, self.market)
        return await routes.analyze_market_cycle(self.market, self.key, cycle)

    async def test_processing_snapshot_and_normal_completion(self):
        async def decide(**kwargs):
            snapshot = self.store.snapshot(self.key)
            self.assertEqual(snapshot["pipeline"]["status"], "PROCESSING")
            self.assertEqual(snapshot["pipeline"]["stage"], "AI")
            self.assertNotIn("decision", snapshot)
            return TraderDecision(decision="NONE", confidence=0, status="COMPLETED", reason="AI_NO_TRADE")
        with patch.object(routes.ai_trader, "decide", side_effect=decide):
            result = await self.run_cycle()
        snapshot = self.store.snapshot(self.key)
        self.assertEqual(result["pipeline"]["status"], "COMPLETED")
        self.assertIsNotNone(snapshot["pipeline"]["completed_at"])
        self.assertEqual(snapshot["journal"]["decision"]["reason"], "AI_NO_TRADE")
        self.assertFalse(result["execution"]["signal_created"])

    async def test_response_contains_flat_mt5_analysis_telemetry(self):
        decision = TraderDecision(
            decision="BUY", confidence=60, status="COMPLETED",
            reason="AI_DIRECTION_SELECTED_REDUCED_RISK",
        )
        with patch.object(routes.ai_trader, "decide", new=AsyncMock(return_value=decision)):
            result = await self.run_cycle()
        self.assertTrue(result["ai_called"])
        self.assertEqual(result["ai_decision"], "BUY")
        self.assertEqual(result["ai_confidence"], 60)
        self.assertEqual(result["ai_status"], "COMPLETED")
        self.assertEqual(result["ai_reason"], "AI_DIRECTION_SELECTED_REDUCED_RISK")
        self.assertTrue(result["risk_approved"])
        self.assertEqual(result["signal_lot"], 0.01)

    async def test_ai_error_has_terminal_error_not_normal_no_signal(self):
        with patch.object(routes.ai_trader, "decide", new=AsyncMock(return_value=TraderDecision(
            decision="NONE", confidence=0, status="ERROR", reason="AI_QUOTA_EXHAUSTED",
        ))):
            result = await self.run_cycle()
        self.assertEqual(result["pipeline"]["status"], "ERROR")
        self.assertEqual(self.journal.latest()[-1]["pipeline"]["reason"], "AI_QUOTA_EXHAUSTED")
        self.assertFalse(result["execution"]["signal_created"])

    async def test_score_skip_never_calls_ai(self):
        self.calculate.return_value = self.calculate.return_value.model_copy(update={"score": 60, "qualified": False})
        with patch.object(routes.ai_trader, "decide", new=AsyncMock()) as decide:
            result = await self.run_cycle()
        decide.assert_not_called()
        self.assertEqual(result["pipeline"]["status"], "SKIPPED")
        self.assertEqual(result["gate_reason"], "SCORE_BELOW_THRESHOLD")

    async def test_cooldown_skip_never_calls_ai(self):
        position = {
            "ticket": 1, "symbol": "XAUUSD", "type": "BUY", "lot": 0.01,
            "profit": 1.0, "open_time": int(time.time()), "open_price": 2300.0,
            "sl": 2270.0, "tp": 2310.0, "magic_number": 20260701,
        }
        self.market = fixtures.market(account_id="observability", positions=[position])
        with patch.object(routes.ai_trader, "decide", new=AsyncMock()) as decide:
            result = await self.run_cycle()
        decide.assert_not_called()
        self.assertEqual(result["pipeline"]["reason"], "MIN_ENTRY_INTERVAL")
        self.assertEqual(result["ai_gate"]["reason"], "AI_SKIPPED_NO_EXECUTABLE_DIRECTION")

    async def test_spread_still_blocks_a_valid_sell(self):
        self.market = fixtures.market(account_id="observability", ask=2310.31, spread=31)
        with patch.object(routes.ai_trader, "decide", new=AsyncMock()) as decide:
            result = await self.run_cycle()
        decide.assert_not_called()
        self.assertEqual(result["pipeline"]["status"], "SKIPPED")
        self.assertEqual(result["gate_reason"], "SPREAD_ABOVE_LIMIT")

    async def test_loss_position_with_no_legal_direction_skips_ai(self):
        position = {
            "ticket": 1, "symbol": "XAUUSD", "type": "BUY", "lot": 0.01,
            "profit": -1.0, "open_time": int(time.time()) - 3600, "open_price": 2300.0,
            "sl": 2270.0, "tp": 2310.0, "magic_number": 20260701,
        }
        self.market = fixtures.market(account_id="observability", positions=[position])
        with patch.object(routes.ai_trader, "decide", new=AsyncMock()) as decide:
            result = await self.run_cycle()
        decide.assert_not_called()
        self.assertEqual(result["gate_reason"], "NO_EXECUTABLE_DIRECTION")
        self.assertEqual(result["ai_gate"]["action_reasons"], {
            "BUY": "AVERAGING_FORBIDDEN", "SELL": "HEDGING_FORBIDDEN",
        })

    async def test_profitable_position_calls_ai_only_for_legal_direction(self):
        position = {
            "ticket": 1, "symbol": "XAUUSD", "type": "BUY", "lot": 0.01,
            "profit": 1.0, "open_time": int(time.time()) - 3600, "open_price": 2300.0,
            "sl": 2270.0, "tp": 2310.0, "magic_number": 20260701,
        }
        self.market = fixtures.market(account_id="observability", positions=[position])
        decide = AsyncMock(return_value=TraderDecision(
            decision="BUY", confidence=70, status="COMPLETED", reason="AI_DIRECTION_SELECTED",
        ))
        with patch.object(routes.ai_trader, "decide", new=decide):
            await self.run_cycle()
        self.assertEqual(decide.await_args.kwargs["allowed_actions"], ("BUY",))

    async def test_rate_limit_skips_second_qualified_snapshot(self):
        decide = AsyncMock(return_value=TraderDecision(
            decision="NONE", confidence=0, status="COMPLETED", reason="AI_NO_TRADE",
        ))
        with patch.object(routes.ai_trader, "decide", new=decide):
            first = await self.run_cycle()
            second = await self.run_cycle()
        self.assertTrue(first["ai_gate"]["call"])
        self.assertEqual(second["ai_gate"]["reason"], "AI_SKIPPED_RATE_LIMIT")
        self.assertEqual(decide.await_count, 1)

    async def test_old_cycle_cannot_overwrite_new_snapshot_or_execute(self):
        async def decide(**kwargs):
            self.store.begin_cycle(self.key, self.market)
            return TraderDecision(decision="BUY", confidence=90, status="COMPLETED")
        with patch.object(routes.ai_trader, "decide", side_effect=decide), \
             patch.object(routes.execution_service, "execute", new=AsyncMock()) as execute:
            with self.assertRaises(routes.HTTPException) as caught:
                await self.run_cycle()
        self.assertEqual(caught.exception.status_code, 409)
        execute.assert_not_called()
        self.assertNotIn("decision", self.store.snapshot(self.key))
        self.assertEqual(self.store.snapshot(self.key)["pipeline"]["stage"], "RESEARCH")

    async def test_same_identity_waits_for_inflight_analysis(self):
        first = fixtures.market(account_id="serialized", market_time=int(time.time()) - 1)
        second = first.model_copy(update={"market_time": int(time.time())})
        identity = MT5Identity(
            account_id=first.account_id,
            terminal_id=first.terminal_id,
            instance_id=first.instance_id,
        )
        started = asyncio.Event()
        release = asyncio.Event()
        observed = []

        async def analyze(data, key, _cycle_id):
            observed.append(data.market_time)
            if len(observed) == 1:
                started.set()
                await release.wait()
            return {"market_time": data.market_time}

        with patch.object(routes.snapshot_guard, "accept", return_value=True), \
             patch.object(routes, "analyze_market_cycle", side_effect=analyze):
            first_task = asyncio.create_task(routes.receive_market_data(first, identity))
            await started.wait()
            second_task = asyncio.create_task(routes.receive_market_data(second, identity))
            await asyncio.sleep(0)
            self.assertEqual(self.store.get_stage("market", first.identity_key)["market_time"], first.market_time)
            release.set()
            results = await asyncio.gather(first_task, second_task)

        self.assertEqual(observed, [first.market_time, second.market_time])
        self.assertEqual([result["market_time"] for result in results], observed)

    async def test_unexpected_pipeline_failure_is_recorded(self):
        identity = MT5Identity(account_id=self.market.account_id, terminal_id=self.market.terminal_id,
                               instance_id=self.market.instance_id)
        with patch.object(routes.snapshot_guard, "accept", return_value=True), \
             patch.object(routes.scoring_engine, "calculate", side_effect=RuntimeError("sensitive")):
            with self.assertRaises(routes.HTTPException) as caught:
                await routes.receive_market_data(self.market, identity)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(self.store.snapshot(self.key)["pipeline"]["reason"], "PIPELINE_ERROR")
        self.assertNotIn("sensitive", json.dumps(self.journal.latest()))

    async def test_cancelled_cycle_is_marked_interrupted(self):
        identity = MT5Identity(account_id=self.market.account_id, terminal_id=self.market.terminal_id,
                               instance_id=self.market.instance_id)
        with patch.object(routes.snapshot_guard, "accept", return_value=True), \
             patch.object(routes.ai_trader, "decide", new=AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):
                await routes.receive_market_data(self.market, identity)
        self.assertEqual(self.store.snapshot(self.key)["pipeline"]["reason"], "PIPELINE_INTERRUPTED")

    def test_guard_is_durable_across_store_instances(self):
        old = self.store.begin_cycle(self.key, self.market)
        second = MarketStore(self.directory.name)
        new = second.begin_cycle(self.key, self.market)
        self.assertFalse(self.store.update_stage(self.key, "pipeline", {"status": "ERROR"}, cycle_id=old))
        self.assertTrue(second.update_stage(self.key, "score", {"score": 85}, cycle_id=new))
        self.assertEqual(self.store.snapshot(self.key)["pipeline"]["cycle_id"], new)


class AICallGateTests(unittest.TestCase):
    def test_news_change_overrides_interval_but_not_every_clock_tick(self):
        with tempfile.TemporaryDirectory() as directory:
            gate = AICallGate(directory, interval_seconds=60)
            upcoming = {
                "high_impact_news": True, "event_id": 7, "event": "CPI",
                "currency": "USD", "impact": "HIGH", "phase": "UPCOMING",
                "actual": None, "forecast": 3.0, "previous": 3.1,
            }
            self.assertEqual(gate.claim("a", upcoming, now=100).reason, "AI_CALLED_INITIAL_QUALIFIED")
            self.assertEqual(gate.claim("a", upcoming, now=110).reason, "AI_SKIPPED_RATE_LIMIT")
            released = {**upcoming, "phase": "RELEASED", "actual": 3.4}
            self.assertEqual(gate.claim("a", released, now=111).reason, "AI_CALLED_NEWS_CHANGED")
            self.assertEqual(gate.claim("a", released, now=112).reason, "AI_SKIPPED_RATE_LIMIT")
            self.assertEqual(gate.claim("a", released, now=171).reason, "AI_CALLED_INTERVAL_ELAPSED")

    def test_eligibility_does_not_decide_direction(self):
        position = {
            "ticket": 1, "symbol": "XAUUSD", "type": "SELL", "lot": 0.01,
            "profit": 2.0, "open_time": int(time.time()) - 3600, "open_price": 2300.0,
            "sl": 2330.0, "tp": 2290.0, "magic_number": 20260701,
        }
        result = eligible_actions(fixtures.market(positions=[position]))
        self.assertEqual(result.allowed_actions, ("SELL",))
        self.assertEqual(result.action_reasons, {"BUY": "HEDGING_FORBIDDEN"})
