"""Entry policy v2 regression matrix. All AI calls are mocks; all DBs temporary."""
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import test_rules as fixtures
from api import routes
from config.trading_config import ENTRY_POLICY_VERSION, RIRI_MAGIC_NUMBER
from models.risk_decision import RiskDecision
from models.trader_decision import TraderDecision
from risk.risk import AIRisk
from scoring.scoring_engine import ScoringEngine
from services.ai_call_gate import AICallGate
from services.entry_eligibility import eligible_actions
from services.execution_service import ExecutionService
from services.signal_store import signal_store
from trader.trader import AITrader
import test_observability as diagnostics


def position(**changes):
    p = dict(ticket=1, symbol="XAUUSD", type="BUY", lot=0.01, profit=-1.0,
             open_time=int(time.time()) - 1800, open_price=2300.0,
             sl=2270.0, tp=2310.0, magic_number=RIRI_MAGIC_NUMBER)
    p.update(changes)
    return p


class CooldownTests(unittest.TestCase):
    def test_broker_offsets_and_exact_15_minute_boundary(self):
        utc = int(time.time())
        for offset in (-5 * 3600, 0, 2 * 3600, 3 * 3600, 7 * 3600):
            for age in (0, 899, 900, 901, 1801):
                with self.subTest(offset=offset, age=age):
                    snapshot = fixtures.market(market_time=utc, server_time=utc + offset,
                        positions=[position(profit=1, open_time=utc + offset - age)])
                    gate = eligible_actions(snapshot, now=utc, initial_score=85)
                    self.assertEqual(gate.diagnostics["latest_entry_age_seconds"], age)
                    self.assertEqual(gate.diagnostics["cooldown_remaining_seconds"], max(0, 900 - age))
                    self.assertEqual(bool(gate.allowed_actions), age >= 900)

    def test_only_newest_own_position_restarts_cooldown(self):
        now = int(time.time())
        snapshot = fixtures.market(server_time=now, positions=[
            position(open_time=now - 4000), position(ticket=2, open_time=now - 300),
            position(ticket=3, magic_number=7, open_time=now - 1),
        ])
        gate = eligible_actions(snapshot, initial_score=99)
        self.assertEqual(gate.diagnostics["cooldown_remaining_seconds"], 600)
        self.assertEqual(gate.diagnostics["riri_positions"], 2)
        self.assertEqual(gate.diagnostics["foreign_positions"], 1)

    def test_invalid_time_fails_closed_instead_of_infinite_cooldown(self):
        now = int(time.time())
        for opened in (0, now + 1, now + 7200):
            gate = eligible_actions(fixtures.market(server_time=now,
                positions=[position(open_time=opened)]), initial_score=100)
            self.assertEqual(gate.reason, "POSITION_TIME_INVALID")
            self.assertIsNone(gate.diagnostics["cooldown_remaining_seconds"])

    def test_one_missing_timestamp_cannot_hide_behind_another_valid_position(self):
        gate = eligible_actions(fixtures.market(positions=[position(open_time=0), position(ticket=2)]), initial_score=100)
        self.assertEqual(gate.reason, "POSITION_TIME_INVALID")

    def test_no_position_does_not_invent_a_cooldown(self):
        gate = eligible_actions(fixtures.market(), initial_score=85)
        self.assertEqual(gate.diagnostics["cooldown_remaining_seconds"], 0)
        self.assertEqual(gate.allowed_actions, ("BUY", "SELL"))

    def test_foreign_positions_do_not_change_direction_cooldown_or_riri_caps(self):
        foreign = [position(ticket=i+1, magic_number=99, lot=0.4,
                            open_time=int(time.time()), type="SELL") for i in range(4)]
        gate = eligible_actions(fixtures.market(positions=foreign), initial_score=75)
        self.assertEqual(gate.allowed_actions, ("BUY", "SELL"))
        self.assertEqual(gate.required_confidence, {"BUY": 60, "SELL": 60})
        self.assertEqual(gate.diagnostics["riri_lot"], 0)
        self.assertEqual(gate.diagnostics["account_xauusd_gross_lot"], 1.6)

    def test_all_blockers_exposed_during_cooldown(self):
        gate = eligible_actions(fixtures.market(positions=[position(open_time=int(time.time()))],
            spread=31, ask=2310.31), initial_score=80)
        self.assertEqual(gate.reason, "MIN_ENTRY_INTERVAL")
        self.assertEqual(gate.diagnostics["action_blockers"]["BUY"],
                         ["MIN_ENTRY_INTERVAL", "SPREAD_ABOVE_LIMIT", "AVERAGING_REQUIRES_SCORE_ABOVE_80"])

    def test_legacy_paused_and_netting_executors_do_not_call_ai(self):
        for overrides, reason in [
            ({"executor_policy_version": 0}, "EXECUTOR_UPGRADE_REQUIRED"),
            ({"trade_allowed": False}, "TRADING_NOT_ALLOWED"),
            ({"hedging_account": False}, "HEDGING_ACCOUNT_REQUIRED"),
        ]:
            gate = eligible_actions(fixtures.market(**overrides), initial_score=100)
            self.assertEqual(gate.reason, reason)
            self.assertEqual(gate.allowed_actions, ())


class ExceptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_score_and_confidence_boundary_matrix_in_risk_and_execution(self):
        snapshot = fixtures.market(positions=[position()])
        for action in ("BUY", "SELL"):
            for score in (70, 80, 81, 100):
                for confidence in (60, 80, 81, 100):
                    with self.subTest(action=action, score=score, confidence=confidence):
                        signal_store.clear(snapshot.identity_key)
                        calculated = NS(score=score)
                        decision = TraderDecision(decision=action, confidence=confidence)
                        with patch.object(ScoringEngine, "calculate", return_value=calculated):
                            risk = await AIRisk().evaluate(snapshot, decision)
                            execution = await ExecutionService().execute(decision,
                                RiskDecision(approved=True, risk_score=100, reason="FORGED"), snapshot)
                        expected = score > 80 and confidence > 80
                        self.assertEqual(risk.approved, expected)
                        self.assertEqual(execution.signal_created, expected)
                        if expected:
                            signal = signal_store.get_signal(snapshot.identity_key)
                            self.assertEqual(signal["initial_score"], score)
                            self.assertEqual(signal["entry_policy_version"], ENTRY_POLICY_VERSION)
                            self.assertEqual(signal["magic_number"], RIRI_MAGIC_NUMBER)
                            self.assertEqual(signal["tp_points"], 1000)
                            self.assertEqual(signal["sl_points"], 3000)
                            self.assertEqual(signal["lot"], 0.03)
                        signal_store.clear(snapshot.identity_key)

    async def test_initial_score_cannot_be_upgraded_by_later_recalculation(self):
        snapshot = fixtures.market(positions=[position()])
        decision = TraderDecision(decision="BUY", confidence=90)
        for initial, recalculated in ((80, 85), (85, 80)):
            with self.subTest(initial=initial, recalculated=recalculated), \
                 patch.object(ScoringEngine, "calculate", return_value=NS(score=recalculated)):
                risk = await AIRisk().evaluate(snapshot, decision, initial_score=initial)
                execution = await ExecutionService().execute(decision,
                    RiskDecision(approved=True, risk_score=100, reason="FORGED"), snapshot,
                    initial_score=initial)
                self.assertFalse(risk.approved)
                self.assertEqual(execution.reason, "AVERAGING_REQUIRES_SCORE_ABOVE_80")

    async def test_no_martingale_and_gross_exposure_is_not_netted(self):
        snapshot = fixtures.market(equity=3000, positions=[
            position(lot=0.25, profit=-100),
            position(ticket=2, lot=0.24, type="SELL", profit=-100),
        ])
        with patch.object(ScoringEngine, "calculate", return_value=NS(score=85)):
            execution = await ExecutionService().execute(TraderDecision(decision="BUY", confidence=85),
                RiskDecision(approved=True, risk_score=100, reason="PASS"), snapshot)
        self.assertTrue(execution.signal_created)
        self.assertEqual(execution.lot, 0.01)
        signal_store.clear(snapshot.identity_key)

    async def test_high_confidence_cannot_bypass_hard_gates(self):
        cases = [
            ({"positions": [position(open_time=int(time.time()))]}, "MIN_ENTRY_INTERVAL"),
            ({"positions": [position(ticket=i+1) for i in range(3)]}, "MAX_ACTIVE_TRADES"),
            ({"positions": [position(lot=0.50)]}, "MAX_TOTAL_LOT"),
            ({"spread": 31, "ask": 2310.31}, "SPREAD_ABOVE_LIMIT"),
            ({"atr": 0.5}, "ATR_BELOW_LIMIT"),
            ({"free_margin": 0}, "INSUFFICIENT_FREE_MARGIN"),
            ({"market_time": int(time.time()) - 60}, "STALE_MARKET_DATA"),
            ({"trade_allowed": False}, "TRADING_NOT_ALLOWED"),
        ]
        for changes, expected in cases:
            with self.subTest(expected=expected), patch.object(ScoringEngine, "calculate", return_value=NS(score=100)):
                snapshot = fixtures.market(**changes)
                decision = TraderDecision(decision="BUY", confidence=100)
                risk = await AIRisk().evaluate(snapshot, decision)
                execution = await ExecutionService().execute(decision,
                    RiskDecision(approved=True, risk_score=100, reason="FORGED"), snapshot)
                self.assertEqual(risk.reason, expected)
                self.assertEqual(execution.reason, expected)
                self.assertFalse(execution.signal_created)

    async def test_signal_pending_does_not_mint_second_entry(self):
        snapshot = fixtures.market(positions=[position()])
        with patch.object(ScoringEngine, "calculate", return_value=NS(score=90)):
            decision = TraderDecision(decision="BUY", confidence=90)
            risk = RiskDecision(approved=True, risk_score=100, reason="PASS")
            try:
                first = await ExecutionService().execute(decision, risk, snapshot)
                second = await ExecutionService().execute(decision, risk, snapshot)
                self.assertTrue(first.signal_created)
                self.assertEqual(second.reason, "SIGNAL_PENDING")
            finally:
                signal_store.clear(snapshot.identity_key)

    async def test_profitable_scale_in_retains_normal_threshold(self):
        snapshot = fixtures.market(positions=[position(profit=1)])
        with patch.object(ScoringEngine, "calculate", return_value=NS(score=70)):
            risk = await AIRisk().evaluate(snapshot, TraderDecision(decision="BUY", confidence=60))
        self.assertTrue(risk.approved)


class OpportunityGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.gate = AICallGate(self.directory.name, interval_seconds=60, event_interval_seconds=30)
        self.context = dict(candle_time=1000, mid=2300.0, atr=2.0, point=0.01,
                            required_confidence={"BUY": 60})

    def test_repeated_ticks_do_not_reset_interval(self):
        self.gate.claim("a", {}, opportunity=self.context, now=100)
        for now in (110, 120, 130, 140, 150):
            result = self.gate.claim("a", {}, opportunity=self.context, now=now)
            self.assertFalse(result.call)
            self.assertEqual(result.retry_after_seconds, 160 - now)
        self.assertTrue(self.gate.claim("a", {}, opportunity=self.context, now=160).call)

    def test_material_price_change_is_once_per_new_baseline_and_respects_floor(self):
        self.gate.claim("a", {}, opportunity=self.context, now=100)
        changed = {**self.context, "mid": 2300.5}
        self.assertFalse(self.gate.claim("a", {}, opportunity=changed, now=120).call)
        self.assertEqual(self.gate.claim("a", {}, opportunity=changed, now=130).reason, "AI_CALLED_OPPORTUNITY_CHANGED")
        self.assertFalse(self.gate.claim("a", {}, opportunity=changed, now=160).call)
        self.assertTrue(self.gate.claim("a", {}, opportunity=changed, now=190).call)

    def test_candle_or_new_legal_direction_can_trigger_early(self):
        for change in ({"candle_time": 4600}, {"required_confidence": {"BUY": 60, "SELL": 81}}):
            key = str(change)
            self.gate.claim(key, {}, opportunity=self.context, now=100)
            self.assertTrue(self.gate.claim(key, {}, opportunity={**self.context, **change}, now=130).call)

    def test_small_price_moves_do_not_trigger(self):
        self.gate.claim("a", {}, opportunity=self.context, now=100)
        self.assertFalse(self.gate.claim("a", {}, opportunity={**self.context, "mid": 2300.49}, now=130).call)

    def test_restart_preserves_call_and_opportunity_baseline(self):
        self.gate.claim("a", {}, opportunity=self.context, now=100)
        restarted = AICallGate(self.directory.name, interval_seconds=60, event_interval_seconds=30)
        self.assertFalse(restarted.claim("a", {}, opportunity=self.context, now=140).call)
        self.assertTrue(restarted.claim("a", {}, opportunity={**self.context, "mid": 2301}, now=140).call)

    def test_additive_migration_preserves_legacy_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ai_call_state.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE ai_call_state (identity_key TEXT PRIMARY KEY, last_call_epoch INTEGER NOT NULL, news_fingerprint TEXT)")
                db.execute("INSERT INTO ai_call_state VALUES ('old', 100, NULL)")
            gate = AICallGate(directory, interval_seconds=60)
            self.assertFalse(gate.claim("old", {}, opportunity=self.context, now=110).call)
            self.assertTrue(gate.claim("old", {}, opportunity=self.context, now=160).call)


class PromptPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_model_output_checked_against_direction_and_threshold(self):
        for action, conf, expected in (("BUY", 80, "NONE"), ("BUY", 81, "BUY"),
                                      ("SELL", 99, "NONE"), ("NONE", 0, "NONE")):
            trader = AITrader()
            call = AsyncMock(return_value=NS(status="completed", output_text=json.dumps({"decision": action, "confidence": conf})))
            trader.client = NS(responses=NS(create=call))
            result = await trader.decide({"live": "market"}, {"live": "statistics"},
                {"live": "fundamental"}, {"live": "pattern"}, allowed_actions=("BUY",),
                required_confidence={"BUY": 81})
            self.assertEqual(result.decision, expected)
            prompt = call.await_args.kwargs["input"]
            self.assertIn('"BUY": 81', prompt)
            self.assertIn("Do not inflate confidence", prompt)
            self.assertEqual(call.await_count, 1)


class NewPipelineTests(unittest.IsolatedAsyncioTestCase):
    setUp = diagnostics.CycleDiagnosticsTests.setUp
    run_cycle = diagnostics.CycleDiagnosticsTests.run_cycle

    async def test_averaging_and_hedging_are_considered_only_with_required_confidence(self):
        self.market = fixtures.market(account_id="observability", positions=[position()])
        call = AsyncMock(return_value=TraderDecision(decision="NONE", confidence=0, status="COMPLETED"))
        with patch.object(routes.ai_trader, "decide", new=call):
            result = await self.run_cycle()
        self.assertTrue(result["ai_called"])
        self.assertEqual(call.await_args.kwargs["allowed_actions"], ("BUY", "SELL"))
        self.assertEqual(call.await_args.kwargs["required_confidence"], {"BUY": 81, "SELL": 81})
        self.assertEqual(result["cooldown_remaining_seconds"], 0)

    async def test_paused_terminal_skips_billable_calls(self):
        self.market = fixtures.market(account_id="observability", trade_allowed=False)
        call = AsyncMock()
        with patch.object(routes.ai_trader, "decide", new=call):
            result = await self.run_cycle()
        call.assert_not_called()
        self.assertEqual(result["ai_gate_reason"], "AI_SKIPPED_TRADING_NOT_ALLOWED")

    async def test_confidence_80_still_blocked_if_model_bypasses_its_filter(self):
        self.market = fixtures.market(account_id="observability", positions=[position()])
        with patch.object(routes.ai_trader, "decide", new=AsyncMock(return_value=TraderDecision(decision="BUY", confidence=80))):
            result = await self.run_cycle()
        self.assertFalse(result["execution"]["signal_created"])
        self.assertEqual(result["risk_reason"], "POSITION_EXCEPTION_REQUIRES_CONFIDENCE_ABOVE_80")


class MT5ContractTests(unittest.TestCase):
    def test_mt5_contract_includes_policy_score_and_separate_broker_clock(self):
        root = Path(__file__).resolve().parents[3] / "mt5"
        trading = (root / "Trading.mqh").read_text()
        market = (root / "Market.mqh").read_text()
        http = (root / "Http.mqh").read_text()
        config = (root / "Config.mqh").read_text()
        self.assertIn("RIRI_MIN_ENTRY_INTERVAL_SECONDS = 15 * 60", config)
        self.assertIn("RIRI_EXCEPTION_THRESHOLD = 80", config)
        self.assertIn("RIRI_ENTRY_POLICY_VERSION = 2", config)
        self.assertIn("PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER", trading)
        self.assertEqual(trading.count("if(!RIRI_SelectedPosition())"), 3)
        self.assertIn("signal.initial_score <= RIRI_EXCEPTION_THRESHOLD", trading)
        self.assertIn("signal.confidence <= RIRI_EXCEPTION_THRESHOLD", trading)
        self.assertIn("signal.entry_policy_version != RIRI_ENTRY_POLICY_VERSION", trading)
        self.assertIn("TimeCurrent() - latest_open < RIRI_MIN_ENTRY_INTERVAL_SECONDS", trading)
        self.assertIn('server_time', market)
        self.assertIn('(long)TimeCurrent()', market)
        self.assertIn('signal.initial_score = (int)RIRI_JsonNumber(response, "initial_score")', http)
        for field in ("cooldown_remaining_seconds", "buy_blockers", "sell_blockers", "ai_retry_after_seconds"):
            self.assertIn(field, http)
