"""Offline behavioral checks. Never call OpenAI or a broker."""
import asyncio
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import test_rules as fixtures
from test_enhancement_part1 import position
from config.settings import settings
from models.trader_decision import TraderDecision
from models.risk_decision import RiskDecision
from services.capital_policy import validate_plan, risk_lot
from services.capital_ai import decide, review
from services.ai_budget import AIBudget
from services.entry_eligibility import eligible_actions, entry_rejection
from services.execution_service import ExecutionService
from services.signal_store import SignalStore


def market(**kwargs):
    defaults=dict(executor_policy_version=4,volume_min=.01,volume_step=.01,volume_max=100,equity=1000)
    defaults.update(kwargs)
    return fixtures.market(**defaults)


def plan(**kwargs):
    out=dict(tp_points=600,sl_points=200,trailing_start_points=300,
             trailing_distance_points=100,trailing_step_points=20,
             review_move_points=100,thesis='Close if confirmed support fails')
    out.update(kwargs)
    return out


class CapitalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for key,value in dict(AI_CAPITAL_PROFILE=True,RIRI_STATE_DIR=self.tmp.name).items():
            p=patch.object(settings,key,value);p.start();self.addCleanup(p.stop)

    def test_risk_rounds_down_and_does_not_force_minimum_lot(self):
        m=market(equity=1000)
        p=validate_plan(m,plan())
        self.assertEqual(risk_lot(m,p),.04)
        with self.assertRaisesRegex(ValueError,'MINIMUM_LOT'):
            risk_lot(market(equity=100),p)
        self.assertIn('MINIMUM_LOT_EXCEEDS_RISK_BUDGET',eligible_actions(market(equity=100),initial_score=99).diagnostics['common_blockers'])

    def test_cent_sized_contract_can_fit_100_equity(self):
        m=market(equity=100,tick_value=.1)
        self.assertEqual(risk_lot(m,validate_plan(m,plan())),.04)

    def test_invalid_or_too_tight_plan_is_rejected(self):
        for p in [None,plan(sl_points=True),plan(sl_points=10),plan(tp_points=250),
                  plan(trailing_start_points=700),plan(trailing_distance_points=301),
                  plan(trailing_step_points=200),plan(review_move_points=0)]:
            with self.subTest(p=p),self.assertRaises(ValueError): validate_plan(market(),p)

    def test_high_score_and_confidence_are_both_required(self):
        self.assertEqual(eligible_actions(market(),initial_score=84).allowed_actions,())
        self.assertEqual(eligible_actions(market(),initial_score=85).allowed_actions,('BUY','SELL'))
        for confidence in (89,90):
            d=TraderDecision(decision='BUY',confidence=confidence,status='COMPLETED',plan=plan())
            self.assertEqual(entry_rejection(market(),d,initial_score=85) is None,confidence==90)

    def test_old_executor_and_missing_broker_metadata_fail_closed(self):
        for change,reason in [({'executor_policy_version':3},'EXECUTOR_UPGRADE_REQUIRED'),
                              ({'volume_min':0},'BROKER_SIZING_UNAVAILABLE')]:
            self.assertIn(reason,eligible_actions(market(**change),initial_score=99).diagnostics['common_blockers'])

    def test_averaging_hedging_and_pending_orders_block_even_at_100(self):
        for kind in ('BUY','SELL'):
            gate=eligible_actions(market(positions=[position(type=kind)]),initial_score=100)
            self.assertEqual(gate.allowed_actions,())
            self.assertIn('CAPITAL_SINGLE_POSITION',gate.diagnostics['common_blockers'])
        pending=dict(ticket=55,symbol='XAUUSD',type='BUY',lot=.01,open_price=2300,sl=2290,magic_number=20260701)
        self.assertEqual(eligible_actions(market(pending_orders=[pending]),initial_score=100).allowed_actions,())

    def test_spread_experiment_cannot_override_capital_limit(self):
        with patch.object(settings,'EXPERIMENTAL_SPREAD',True):
            gate=eligible_actions(market(ask=2310.61,spread=61),initial_score=100)
            self.assertIn('SPREAD_ABOVE_LIMIT',gate.diagnostics['common_blockers'])

    def test_budget_persists_and_suppresses_unchanged_calls(self):
        budget=AIBudget(self.tmp.name)
        args=dict(account='a',prompt='p',schema='{}',key='a:review',price=1,event='',move=2,max_age=900)
        self.assertIsNone(budget.claim(**args,now=100000))
        self.assertEqual(AIBudget(self.tmp.name).claim(**args,now=100200),'AI_NO_MATERIAL_CHANGE')
        self.assertIsNone(budget.claim(**{**args,'price':4},now=100200))
        self.assertEqual(budget.claim(**{**args,'price':8},now=100201),'AI_MIN_INTERVAL')

    def test_budget_concurrency_and_daily_reset(self):
        b=AIBudget(self.tmp.name)
        def claim(i,now=100000):
            return b.claim('a','p','{}',key=str(i),price=1,event='',move=1,max_age=900,now=now)
        with ThreadPoolExecutor(max_workers=8) as pool:
            values=list(pool.map(claim,range(8)))
        self.assertEqual(values.count(None),1)
        with patch.object(settings,'CAPITAL_AI_CALLS_PER_DAY',1):
            self.assertEqual(claim(9,100200),'AI_DAILY_BUDGET_EXHAUSTED')
            self.assertIsNone(claim(10,200000))

    def test_token_budget_blocks_before_call(self):
        b=AIBudget(self.tmp.name)
        with patch.object(settings,'CAPITAL_AI_TOKENS_PER_DAY',4096):
            self.assertEqual(b.claim('a','x'*5000,'{}',key='review',price=1,event='',move=1,max_age=900),
                             'AI_DAILY_BUDGET_EXHAUSTED')

    def test_entry_budget_reserves_capacity_for_reviews(self):
        b=AIBudget(self.tmp.name)
        with patch.object(settings,'CAPITAL_AI_CALLS_PER_DAY',3):
            for i in range(2):
                self.assertIsNone(b.claim('a','p','{}',key='capital_entry',price=i,event='',move=.5,max_age=900,now=100000+i*120))
            self.assertEqual(b.claim('a','p','{}',key='capital_entry',price=5,event='',move=.5,max_age=900,now=100300),'AI_ENTRY_BUDGET_EXHAUSTED')
            self.assertIsNone(b.claim('a','p','{}',key='review',price=5,event='',move=.5,max_age=900,now=100300))

    def test_ai_entry_emits_plan_in_one_compact_request(self):
        response=NS(status='completed',output_text=json.dumps(dict(decision='BUY',confidence=95,reason='Supported',plan=plan())),usage=None)
        call=AsyncMock(return_value=response);client=NS(responses=NS(create=call))
        d=asyncio.run(decide(client,market().model_dump(),{}, {},{},('BUY','SELL')))
        self.assertEqual(d.decision,'BUY');self.assertEqual(d.plan['sl_points'],200)
        self.assertEqual(call.await_count,1)
        prompt=call.call_args.kwargs['input']
        self.assertLess(len(prompt),14000);self.assertNotIn('broker-demo',prompt)

    def test_malformed_ai_response_and_unavailable_client_never_trade(self):
        for output in ('{}','not json'):
            with tempfile.TemporaryDirectory() as state,patch.object(settings,'RIRI_STATE_DIR',state):
                client=NS(responses=NS(create=AsyncMock(return_value=NS(status='completed',output_text=output,usage=None))))
                d=asyncio.run(decide(client,market().model_dump(),{}, {},{},('BUY','SELL')))
                self.assertEqual(d.decision,'NONE')
        d=asyncio.run(decide(None,market().model_dump(),{}, {},{},('BUY','SELL')))
        self.assertEqual(d.decision,'NONE')

    def test_review_can_take_profit_early_without_entry_score(self):
        response=NS(status='completed',output_text=json.dumps(dict(decision='CLOSE',confidence=94,reason='Edge deteriorated',
            thesis_invalid=False,profit_protection=True,close_preferred_after_cost=True)),usage=None)
        client=NS(responses=NS(create=AsyncMock(return_value=response)))
        m=market(positions=[position(profit=3)])
        with patch.object(settings,'POSITION_REVIEW_EXECUTE',True):
            out=asyncio.run(review(client,m,{}, {},{}))
        self.assertTrue(out['reviews'][0]['execute_close'])
        self.assertEqual(out['reviews'][0]['active_sl'],2280)

    def test_review_cannot_close_on_weak_confidence(self):
        response=NS(status='completed',output_text=json.dumps(dict(decision='CLOSE',confidence=89,reason='Uncertain',
            thesis_invalid=True,profit_protection=False,close_preferred_after_cost=True)),usage=None)
        with patch.object(settings,'POSITION_REVIEW_EXECUTE',True):
            out=asyncio.run(review(NS(responses=NS(create=AsyncMock(return_value=response))),market(positions=[position()]),{},{},{}))
        self.assertFalse(out['reviews'][0]['execute_close'])

    def test_execution_uses_dynamic_protection_and_risk_lot(self):
        m=market();store=SignalStore(self.tmp.name)
        d=TraderDecision(decision='BUY',confidence=95,status='COMPLETED',plan=plan())
        with patch('services.execution_service.signal_store',store),patch('services.execution_service.ScoringEngine.calculate',return_value=NS(score=95)):
            result=asyncio.run(ExecutionService().execute(d,RiskDecision(approved=True,risk_score=100,reason='PASS'),m,initial_score=95))
        self.assertTrue(result.signal_created)
        signal=store.get_signal(m.identity_key)
        self.assertEqual((signal['tp_points'],signal['sl_points'],signal['entry_policy_version']),(600,200,4))
        self.assertEqual(signal['lot'],.04)
        self.assertTrue(signal['ai_capital_profile'])

    def test_stale_snapshot_does_not_spend_ai_budget(self):
        call=AsyncMock()
        d=asyncio.run(decide(NS(responses=NS(create=call)),market(market_time=int(time.time())-60).model_dump(),{},{},{},('BUY',)))
        self.assertEqual(d.decision,'NONE');call.assert_not_awaited()

    def test_review_failure_keeps_stops_and_never_closes(self):
        out=asyncio.run(review(NS(responses=NS(create=AsyncMock(side_effect=RuntimeError('offline')))),market(positions=[position()]),{},{},{}))
        self.assertEqual(out['reviews'],[])
        self.assertEqual(out['reason'],'AI_FAILED_OR_INVALID')

    def test_confirmed_plan_is_persisted_and_isolated(self):
        from services.capital_plans import plans
        m=market();store=SignalStore(self.tmp.name)
        d=TraderDecision(decision='BUY',confidence=95,status='COMPLETED',plan=plan())
        with patch('services.execution_service.signal_store',store),patch('services.execution_service.ScoringEngine.calculate',return_value=NS(score=95)):
            result=asyncio.run(ExecutionService().execute(d,RiskDecision(approved=True,risk_score=100,reason='PASS'),m,initial_score=95))
        self.assertTrue(result.signal_created)
        from models.market_data import Position
        p=Position(**position(open_time=m.server_time))
        self.assertIsNone(plans.for_position(m,p))
        stored=store.get_signal(m.identity_key)
        store.confirm(m.identity_key,result.signal_id,'BUY',stored['lot'],outcome='EXECUTED',entry_server_time=m.server_time)
        self.assertEqual(plans.for_position(m,p)['sl_points'],200)
        self.assertIsNone(plans.for_position(market(account_id='another'),p))

    def test_micro_lot_step_is_supported_without_rounding_up(self):
        m=market(equity=100,volume_min=.001,volume_step=.001)
        self.assertEqual(risk_lot(m,validate_plan(m,plan())),.004)
