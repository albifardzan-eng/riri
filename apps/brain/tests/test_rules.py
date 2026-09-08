import asyncio
import atexit
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

BRAIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BRAIN_DIR))

# Test collection imports the FastAPI routes, which construct AITrader at
# module load time. Override any operator/production .env before those imports
# so the suite is hermetic and cannot initialize or call a live OpenAI client.
os.environ["OPENAI_API_KEY"] = ""
_test_state = tempfile.TemporaryDirectory(prefix="riri-test-state-")
atexit.register(_test_state.cleanup)
os.environ["RIRI_STATE_DIR"] = _test_state.name

from models.market_data import FundamentalData, MarketData
from models.risk_decision import RiskDecision
from models.trader_decision import TraderDecision
from api import routes as api_routes
from research.fundamental_service import FundamentalService
from risk.risk import AIRisk
from scoring.scoring_engine import ScoringEngine
from services.signal_store import SignalStore
from services.execution_service import ExecutionService
from services.market_store import MarketStore
from services.signal_store import signal_store
from trader.trader import AITrader
from config.settings import settings
from fastapi.testclient import TestClient
from main import app


def candle_series():
    start = int(time.time()) - 100 * 3600
    return [
        {
            "time": start + index * 3600,
            "open": 2300 + index * 0.1,
            "high": 2301 + index * 0.1,
            "low": 2299 + index * 0.1,
            "close": 2300.5 + index * 0.1,
            "volume": 100 + index,
        }
        for index in range(100)
    ]


def market(**overrides):
    values = {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "market_time": int(time.time()),
        "account_id": "1001",
        "terminal_id": "broker-demo",
        "instance_id": "primary",
        "bid": 2310.0,
        "ask": 2310.2,
        "spread": 20.0,
        "point": 0.01,
        "digits": 2,
        "tick_size": 0.01,
        "tick_value": 1.0,
        "balance": 1000.0,
        "equity": 1000.0,
        "free_margin": 900.0,
        "tick_volume": 200.0,
        "atr": 2.0,
        "candles": candle_series(),
        "positions": [],
        "fundamental": {},
    }
    values.update(overrides)
    return MarketData(**values)


class RiskRuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_spread_atr_and_confidence_are_hard_gates(self):
        cases = [
            (market(ask=2310.31, spread=31), TraderDecision(decision="BUY", confidence=90), "SPREAD_ABOVE_LIMIT"),
            (market(atr=0.9), TraderDecision(decision="BUY", confidence=90), "ATR_BELOW_LIMIT"),
            (market(), TraderDecision(decision="BUY", confidence=69), "CONFIDENCE_BELOW_70"),
        ]
        for snapshot, decision, expected in cases:
            with self.subTest(expected=expected):
                result = await AIRisk().evaluate(snapshot, decision)
                self.assertFalse(result.approved)
                self.assertEqual(result.reason, expected)

    async def test_hedging_and_averaging_are_rejected(self):
        position = {
            "ticket": 1,
            "symbol": "XAUUSD",
            "type": "BUY",
            "lot": 0.01,
            "profit": 1.0,
            "open_time": int(time.time()) - 3600,
            "open_price": 2300.0,
            "sl": 2270.0,
            "tp": 2310.0,
            "magic_number": 20260701,
        }
        hedge = await AIRisk().evaluate(
            market(positions=[position]), TraderDecision(decision="SELL", confidence=90)
        )
        self.assertEqual(hedge.reason, "HEDGING_FORBIDDEN")
        position["profit"] = -1.0
        average = await AIRisk().evaluate(
            market(positions=[position]), TraderDecision(decision="BUY", confidence=90)
        )
        self.assertEqual(average.reason, "AVERAGING_FORBIDDEN")


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_fundamental_pydantic_payload_is_preserved(self):
        result = await FundamentalService().analyze(
            FundamentalData(available=True, high_impact_news=True, event="CPI", impact="HIGH")
        )
        self.assertTrue(result["available"])
        self.assertTrue(result["high_impact_news"])
        self.assertEqual(result["event"], "CPI")

    async def test_ai_confidence_below_threshold_becomes_none(self):
        class Responses:
            async def create(self, **_kwargs):
                return type(
                    "Response",
                    (),
                    {
                        "status": "completed",
                        "output_text": json.dumps({"decision": "BUY", "confidence": 69}),
                    },
                )()

        trader = AITrader()
        trader.client = type("Client", (), {"responses": Responses()})()
        result = await trader.decide({}, {}, {}, {})
        self.assertEqual(result.decision, "NONE")
        self.assertEqual(result.confidence, 0)

    async def test_ai_uses_strict_schema_and_all_live_context(self):
        class Responses:
            def __init__(self):
                self.kwargs = None

            async def create(self, **kwargs):
                self.kwargs = kwargs
                return type(
                    "Response",
                    (),
                    {
                        "status": "completed",
                        "output_text": json.dumps({"decision": "BUY", "confidence": 80}),
                    },
                )()

        responses = Responses()
        trader = AITrader()
        trader.client = type("Client", (), {"responses": responses})()
        result = await trader.decide(
            {"market_marker": "LIVE_MARKET"},
            {"statistics_marker": "LIVE_STATISTICS"},
            {"fundamental_marker": "LIVE_FUNDAMENTAL"},
            {"pattern_marker": "LIVE_PATTERN"},
        )

        self.assertEqual(result.decision, "BUY")
        self.assertEqual(result.confidence, 80)
        self.assertFalse(responses.kwargs["store"])
        self.assertEqual(
            responses.kwargs["max_output_tokens"],
            settings.OPENAI_MAX_OUTPUT_TOKENS,
        )
        output_format = responses.kwargs["text"]["format"]
        self.assertEqual(output_format["type"], "json_schema")
        self.assertTrue(output_format["strict"])
        self.assertFalse(output_format["schema"]["additionalProperties"])
        self.assertEqual(
            output_format["schema"]["properties"]["decision"]["enum"],
            ["BUY", "SELL", "NONE"],
        )
        for marker in (
            "LIVE_MARKET",
            "LIVE_STATISTICS",
            "LIVE_FUNDAMENTAL",
            "LIVE_PATTERN",
        ):
            self.assertIn(marker, responses.kwargs["input"])

    async def test_ai_incomplete_response_fails_closed(self):
        class Responses:
            async def create(self, **_kwargs):
                return type(
                    "Response",
                    (),
                    {
                        "status": "incomplete",
                        "incomplete_details": type(
                            "IncompleteDetails",
                            (),
                            {"reason": "max_output_tokens"},
                        )(),
                        "output_text": "",
                    },
                )()

        trader = AITrader()
        trader.client = type("Client", (), {"responses": Responses()})()
        result = await trader.decide({}, {}, {}, {})
        self.assertEqual((result.decision, result.confidence, result.status, result.reason),
                         ("NONE", 0, "ERROR", "AI_MAX_OUTPUT_TOKENS"))

    async def test_ai_malformed_output_fails_closed(self):
        class Responses:
            async def create(self, **_kwargs):
                return type(
                    "Response",
                    (),
                    {"status": "completed", "output_text": "not-json"},
                )()

        trader = AITrader()
        trader.client = type("Client", (), {"responses": Responses()})()
        result = await trader.decide({}, {}, {}, {})
        self.assertEqual((result.decision, result.confidence, result.status, result.reason),
                         ("NONE", 0, "ERROR", "AI_INVALID_OUTPUT"))

    async def test_ai_schema_violation_fails_closed(self):
        class Responses:
            async def create(self, **_kwargs):
                return type(
                    "Response",
                    (),
                    {
                        "status": "completed",
                        "output_text": json.dumps(
                            {
                                "decision": "BUY",
                                "confidence": "90",
                                "unexpected": True,
                            }
                        ),
                    },
                )()

        trader = AITrader()
        trader.client = type("Client", (), {"responses": Responses()})()
        result = await trader.decide({}, {}, {}, {})
        self.assertEqual((result.decision, result.confidence, result.status, result.reason),
                         ("NONE", 0, "ERROR", "AI_INVALID_OUTPUT"))

    def test_score_is_sum_of_the_six_declared_weights(self):
        result = ScoringEngine().calculate(market())
        component_sum = (
            result.trend_score + result.momentum_score + result.volume_score
            + result.volatility_score + result.session_score + result.spread_score
        )
        self.assertEqual(result.score, component_sum)

    async def test_execution_signal_contains_locked_rules_and_identity(self):
        snapshot = market(equity=1000.0)
        result = await ExecutionService().execute(
            TraderDecision(decision="BUY", confidence=90),
            RiskDecision(approved=True, risk_score=100, reason="PASS"),
            snapshot,
        )
        try:
            self.assertTrue(result.signal_created)
            signal = signal_store.get_signal(snapshot.identity_key)
            self.assertEqual(signal["lot"], 0.03)
            self.assertEqual(signal["tp_points"], 1000)
            self.assertEqual(signal["sl_points"], 3000)
            self.assertEqual(signal["account_id"], snapshot.account_id)
        finally:
            signal_store.clear(snapshot.identity_key)

    async def test_execution_rechecks_market_even_if_risk_object_is_forged(self):
        snapshot = market(ask=2310.31, spread=31)
        result = await ExecutionService().execute(
            TraderDecision(decision="BUY", confidence=90),
            RiskDecision(approved=True, risk_score=100, reason="PASS"),
            snapshot,
        )
        self.assertFalse(result.signal_created)
        self.assertEqual(result.reason, "SPREAD_ABOVE_LIMIT")

    def test_non_xauusd_and_unknown_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            market(symbol="EURUSD")
        with self.assertRaises(ValueError):
            market(unexpected=True)


class SignalStoreTests(unittest.TestCase):
    def test_signals_are_isolated_by_identity_and_leased(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SignalStore(directory)
            now = int(time.time())
            signal = {
                "signal_id": "one",
                "expires_at_epoch": now + 60,
                "action": "BUY",
            }
            store.set_signal("account-a", signal)
            self.assertIsNone(store.get_signal("account-b"))
            self.assertEqual(store.claim_signal("account-a")["signal_id"], "one")
            self.assertIsNone(store.claim_signal("account-a"))
            self.assertIsNone(store.confirm("account-b", "one"))
            self.assertIsNone(store.confirm("account-a", "one", "SELL"))
            self.assertIsNotNone(store.get_signal("account-a"))
            self.assertEqual(store.confirm("account-a", "one")["signal_id"], "one")

    def test_market_state_is_durable_and_account_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            first = MarketStore(directory)
            first.begin_cycle("account-a", market())
            first.update_stage("account-a", "decision", {"decision": "BUY"})
            second = MarketStore(directory)
            self.assertEqual(second.get_stage("decision", "account-a")["decision"], "BUY")
            self.assertIsNone(second.get_stage("decision", "account-b"))


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.previous_mt5 = settings.RIRI_MT5_API_KEY
        self.previous_dashboard = settings.RIRI_DASHBOARD_API_KEY
        self.previous_ai_client = api_routes.ai_trader.client
        settings.RIRI_MT5_API_KEY = "m" * 32
        settings.RIRI_DASHBOARD_API_KEY = "d" * 32
        # Never let an API integration test call the live model merely because
        # the operator's local or production .env contains OPENAI_API_KEY.
        api_routes.ai_trader.client = None
        self.client = TestClient(app)

    def tearDown(self):
        settings.RIRI_MT5_API_KEY = self.previous_mt5
        settings.RIRI_DASHBOARD_API_KEY = self.previous_dashboard
        api_routes.ai_trader.client = self.previous_ai_client

    def test_dashboard_and_mt5_routes_reject_missing_credentials(self):
        self.assertEqual(self.client.get("/status").status_code, 401)
        self.assertEqual(self.client.get("/execution/pending").status_code, 401)

    def test_dashboard_accepts_server_bearer(self):
        response = self.client.get(
            "/status",
            headers={"Authorization": f"Bearer {settings.RIRI_DASHBOARD_API_KEY}"},
        )
        self.assertEqual(response.status_code, 200)

    def test_market_snapshot_is_identity_bound_and_replay_safe(self):
        account = f"test-{time.time_ns()}"
        snapshot = market(account_id=account)
        headers = {
            "X-RIRI-API-Key": settings.RIRI_MT5_API_KEY,
            "X-RIRI-Account-ID": account,
            "X-RIRI-Terminal-ID": snapshot.terminal_id,
            "X-RIRI-Instance-ID": snapshot.instance_id,
        }
        response = self.client.post("/mt5/market", headers=headers, json=snapshot.model_dump())
        self.assertEqual(response.status_code, 200, response.text)
        replay = self.client.post("/mt5/market", headers=headers, json=snapshot.model_dump())
        self.assertEqual(replay.status_code, 409)

        bad_headers = dict(headers)
        bad_headers["X-RIRI-Account-ID"] = "different"
        mismatch = self.client.post(
            "/mt5/market",
            headers=bad_headers,
            json=market(account_id=account, market_time=int(time.time()) + 1).model_dump(),
        )
        self.assertEqual(mismatch.status_code, 403)


class CrossRuntimeContractTests(unittest.TestCase):
    def test_mt5_immutable_rules_match_backend(self):
        config = (BRAIN_DIR.parents[1] / "mt5" / "Config.mqh").read_text(encoding="utf-8")
        self.assertIn('const string RIRI_SYMBOL = "XAUUSD";', config)
        self.assertIn("const int RIRI_MIN_CONFIDENCE = 70;", config)
        self.assertIn("const int RIRI_TP_POINTS = 1000;", config)
        self.assertIn("const int RIRI_SL_POINTS = 3000;", config)
        self.assertIn("const int RIRI_MAX_ACTIVE_TRADES = 3;", config)
        self.assertIn("const double RIRI_MAX_TOTAL_LOT = 0.50;", config)
        self.assertIn("const double RIRI_EQUITY_STEP = 500.0;", config)
        self.assertIn("const double RIRI_LOT_STEP = 0.01;", config)

    def test_mt5_contract_has_auth_and_detailed_ack(self):
        http = (BRAIN_DIR.parents[1] / "mt5" / "Http.mqh").read_text(encoding="utf-8")
        self.assertIn("X-RIRI-API-Key", http)
        self.assertIn("X-RIRI-Account-ID", http)
        self.assertIn('"EXECUTED"', (BRAIN_DIR.parents[1] / "mt5" / "Trading.mqh").read_text())
        self.assertIn('"REJECTED"', (BRAIN_DIR.parents[1] / "mt5" / "Trading.mqh").read_text())


if __name__ == "__main__":
    unittest.main()
