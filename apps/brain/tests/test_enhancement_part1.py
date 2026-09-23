"""Part 1 invariants: isolated databases and mocked AI; no broker/network calls."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import tempfile
import time
import unittest
import uuid
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import test_rules as fixtures
from config.settings import settings
from config.trading_config import ENTRY_POLICY_VERSION
from models.execution_signal import ExecutionSignal
from models.trader_decision import TraderDecision
from services.entry_eligibility import eligible_actions, entry_rejection
from services.exposure import exposure
from services.signal_store import SignalStore
from services.position_review import PositionReview
from services.multiframe import context


def position(**overrides):
    row=dict(ticket=5,symbol='XAUUSD',type='BUY',lot=.01,profit=-2,
             open_time=int(time.time())-2700,open_price=2310,sl=2280,tp=2320,magic_number=20260701)
    row.update(overrides)
    return row


def signal(market):
    now=datetime.now(timezone.utc)
    return ExecutionSignal(signal_id=str(uuid.uuid4()),symbol='XAUUSD',action='BUY',lot=.03,
        tp_points=1000,sl_points=3000,confidence=90,initial_score=85,entry_policy_version=ENTRY_POLICY_VERSION,
        magic_number=20260701,account_id=market.account_id,terminal_id=market.terminal_id,
        instance_id=market.instance_id,market_time=market.market_time,created_at=now,
        expires_at=now+timedelta(seconds=60),created_at_epoch=int(now.timestamp()),expires_at_epoch=int(now.timestamp())+60)


class EntryPart1Tests(unittest.TestCase):
    def test_small_equity_uses_strict_greater_than_85_and_boundary_500(self):
        for equity in (499.99,500,500.01):
            for confidence in (60,85,86,100):
                m=fixtures.market(equity=equity)
                rejected=entry_rejection(m,TraderDecision(decision='BUY',confidence=confidence),initial_score=90)
                self.assertEqual(rejected is None,equity>500 or confidence>85)

    def test_spread_exception_strict_boundaries_and_pre_ai_gate(self):
        with patch.object(settings,'EXPERIMENTAL_SPREAD',True):
            for spread in (60,61,150,151):
                for score in (80,81):
                    for confidence in (95,96):
                        m=fixtures.market(ask=2310+spread*.01,spread=spread)
                        allowed=entry_rejection(m,TraderDecision(decision='BUY',confidence=confidence),initial_score=score) is None
                        self.assertEqual(allowed,spread<=60 or (spread<=150 and score>80 and confidence>95))
            gate=eligible_actions(fixtures.market(ask=2311.5,spread=150),initial_score=81)
            self.assertEqual(gate.allowed_actions,('BUY','SELL'))
            self.assertEqual(gate.required_confidence['BUY'],96)

    def test_closed_latest_position_cannot_erase_snapshot_cooldown(self):
        now=int(time.time())
        for positions in ([],[position(open_time=now-4000)]):
            gate=eligible_actions(fixtures.market(positions=positions,last_entry_server_time=now-300),initial_score=90)
            self.assertEqual(gate.diagnostics['cooldown_remaining_seconds'],600)

    def test_pending_orders_count_gross_and_slots(self):
        pending=dict(ticket=44,symbol='XAUUSD',type='SELL',lot=.25,open_price=2300,sl=2330,magic_number=20260701)
        m=fixtures.market(positions=[position(lot=.25)],pending_orders=[pending])
        self.assertAlmostEqual(exposure(m)['gross_lot'],.5)
        self.assertIn('MAX_TOTAL_LOT',eligible_actions(m,initial_score=90).diagnostics['common_blockers'])
        m=fixtures.market(positions=[position(),position(ticket=6)],pending_orders=[pending])
        self.assertIn('MAX_ACTIVE_TRADES',eligible_actions(m,initial_score=90).diagnostics['common_blockers'])

    def test_active_stop_risk_and_candidate_in_account_money(self):
        m=fixtures.market(positions=[position(lot=.1,sl=2300)])
        self.assertEqual(exposure(m)['sl_risk_money'],100)
        self.assertEqual(exposure(m,.01)['sl_risk_money'],130)
        with patch.object(settings,'MAX_SL_RISK_EQUITY_PERCENT',12):
            self.assertTrue(exposure(m)['risk_allowed'])
            self.assertFalse(exposure(m,.01)['risk_allowed'])
            self.assertFalse(exposure(fixtures.market(positions=[position(sl=0)]))['risk_allowed'])
        self.assertIsNone(exposure(m)['risk_cap_percent'])

    def test_stale_tick_and_missing_history_fail_closed(self):
        for changes,reason in [({'tick_age_seconds':11},'STALE_TICK'),({'history_ready':False},'ENTRY_HISTORY_UNAVAILABLE'),({'account_currency':'EUR'},'USD_ACCOUNT_REQUIRED')]:
            self.assertIn(reason,eligible_actions(fixtures.market(**changes),initial_score=99).diagnostics['common_blockers'])

    def test_preclose_blocks_entry_from_broker_clock(self):
        now=int(time.time())+7*3600
        with patch.object(settings,'PRECLOSE_ENABLED',True):
            for weekly,seconds,blocked in [(False,1800,True),(False,1801,False),(True,3600,True),(True,3601,False)]:
                m=fixtures.market(server_time=now,broker_session=dict(valid=True,close_time=now+seconds,next_open_time=now+seconds+172800,weekly=weekly))
                self.assertEqual('PRECLOSE_ENTRY_BLOCKED' in eligible_actions(m,initial_score=90).diagnostics['common_blockers'],blocked)

    def test_nan_and_duplicate_tickets_are_rejected(self):
        for changes in ({'equity':float('nan')},{'free_margin':float('inf')},{'positions':[position(),position()]}):
            with self.assertRaises(ValueError): fixtures.market(**changes)

    def test_multiframe_context_includes_overextension(self):
        m=fixtures.market(timeframes={'M15':fixtures.candle_series()})
        result=context(m)
        self.assertEqual(set(result),{'H1','M15'})
        self.assertGreater(result['M15']['atr14'],0)
        self.assertIsNotNone(result['M15']['distance_ema_atr'])


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.store=SignalStore(self.directory.name)
        self.market=fixtures.market()

    def test_only_one_concurrent_instance_can_reserve_same_account(self):
        def attempt(i):
            db=SignalStore(self.directory.name)
            m=self.market.model_copy(update={'instance_id':f'instance-{i}'})
            return db.reserve(m,signal(m))
        with ThreadPoolExecutor(max_workers=6) as pool: outcomes=list(pool.map(attempt,range(6)))
        self.assertEqual(outcomes.count(None),1)
        self.assertEqual(outcomes.count('ACCOUNT_ENTRY_PENDING'),5)

    def test_broker_accounts_are_isolated(self):
        self.assertIsNone(self.store.reserve(self.market,signal(self.market)))
        m=fixtures.market(account_id='2002')
        self.assertIsNone(self.store.reserve(m,signal(m)))

    def test_fill_confirmation_persists_across_restart_and_flat_snapshot(self):
        m=self.market;s=signal(m);self.store.reserve(m,s)
        self.store.claim_signal(m.identity_key)
        self.assertTrue(self.store.authorize(m.identity_key,s.signal_id,'token-1234567890123'))
        self.store.confirm(m.identity_key,s.signal_id,'BUY',s.lot,outcome='EXECUTED',entry_server_time=m.server_time,execution_token='token-1234567890123')
        restarted=SignalStore(self.directory.name)
        flat=restarted.reconcile_market(m)
        self.assertEqual(flat.last_entry_server_time,m.server_time)
        self.assertEqual(restarted.reserve(m,signal(m)),'MIN_ENTRY_INTERVAL')

    def test_rejection_does_not_start_cooldown(self):
        m=self.market;s=signal(m);self.store.reserve(m,s)
        self.store.confirm(m.identity_key,s.signal_id,'BUY',s.lot)
        self.assertEqual(self.store.reconcile_market(m).last_entry_server_time,0)
        self.assertIsNone(self.store.reserve(m,signal(m)))

    def test_authorization_is_once_only_and_cannot_be_cleared_by_other_delivery(self):
        m=self.market;s=signal(m);self.store.reserve(m,s)
        self.assertFalse(self.store.authorize(m.identity_key,s.signal_id,'before-delivery'))
        self.store.claim_signal(m.identity_key)
        self.assertTrue(self.store.authorize(m.identity_key,s.signal_id,'correct-token'))
        self.assertFalse(self.store.authorize(m.identity_key,s.signal_id,'wrong-token'))
        self.assertIsNone(self.store.confirm(m.identity_key,s.signal_id,outcome='REJECTED',execution_token='wrong-token'))
        self.assertEqual(self.store.reserve(m,signal(m)),'ACCOUNT_ENTRY_PENDING')

    def test_delivered_expiry_keeps_uncertain_reservation_and_allows_late_ack(self):
        m=self.market;s=signal(m);self.store.reserve(m,s);self.store.claim_signal(m.identity_key)
        with self.store._connect() as db:
            db.execute('UPDATE pending_signals SET expires_at=1')
            db.execute('UPDATE account_entry_state SET expires=1')
        self.assertIsNone(self.store.get_signal(m.identity_key))
        self.assertEqual(self.store.reserve(m,signal(m)),'ACCOUNT_ENTRY_PENDING')
        self.assertIsNotNone(self.store.confirm(m.identity_key,s.signal_id,'BUY',s.lot,outcome='EXECUTED',entry_server_time=m.server_time))
        self.assertEqual(self.store.reserve(m,signal(m)),'MIN_ENTRY_INTERVAL')

    def test_undelivered_expiry_releases_reservation_without_cooldown(self):
        m=self.market;s=signal(m);self.store.reserve(m,s)
        with self.store._connect() as db: db.execute('UPDATE account_entry_state SET expires=1')
        self.assertIsNone(self.store.reserve(m,signal(m)))

    def test_history_reconciles_lost_fill_ack_without_double_counting(self):
        m=self.market;s=signal(m);self.store.reserve(m,s);self.store.claim_signal(m.identity_key)
        filled=m.model_copy(update={'last_entry_server_time':m.server_time})
        self.store.reconcile_market(filled)
        self.assertIsNone(self.store.get_signal(m.identity_key))
        with self.store._connect() as db:
            self.assertIsNone(db.execute('SELECT reservation FROM account_entry_state').fetchone()[0])
        self.assertEqual(self.store.reserve(filled,signal(filled)),'MIN_ENTRY_INTERVAL')


class ReviewTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.service=PositionReview(self.directory.name)
        self.call=AsyncMock(return_value=NS(status='completed',output_text=json.dumps(self.output())))
        self.trader=NS(client=NS(responses=NS(create=self.call)))

    @staticmethod
    def output(**overrides):
        out=dict(decision='CLOSE',confidence=90,reason='Thesis failed at confirmed resistance',thesis_invalid=True,sl_risk_high=True,close_preferred_after_cost=True)
        return {**out,**overrides}

    async def review(self,m): return await self.service.analyze(m,self.trader,{'marker':'statistics'},{'marker':'fundamental'},{'marker':'pattern'})

    async def test_45_minutes_reviews_and_repeats_are_deduplicated(self):
        now=int(time.time())
        early=fixtures.market(positions=[position(open_time=now-2699)])
        self.assertEqual((await self.review(early))['reviews'],[])
        due=fixtures.market(positions=[position(open_time=now-2700)])
        result=(await self.review(due))['reviews'][0]
        self.assertEqual(result['decision'],'CLOSE');self.assertFalse(result['execute_close'])
        self.assertEqual((await self.review(due))['reviews'],[])
        restarted=PositionReview(self.directory.name)
        self.assertEqual((await restarted.analyze(due,self.trader,{},{},{}))['reviews'],[])
        self.assertEqual(self.call.await_count,1)

    async def test_review_ignores_all_entry_gates_and_targets_ticket(self):
        m=fixtures.market(equity=300,free_margin=0,trade_allowed=False,spread=200,ask=2312,atr=.1,
            last_entry_server_time=int(time.time()),positions=[position(ticket=i) for i in (5,6,7)])
        with patch.object(settings,'POSITION_REVIEW_EXECUTE',True): result=(await self.review(m))['reviews'][0]
        self.assertTrue(result['execute_close']);self.assertEqual(result['ticket'],5)
        self.assertEqual(self.call.await_count,1)
        prompt=self.call.await_args.kwargs['input']
        for marker in ('statistics','fundamental','pattern','active','observed_journey'):
            self.assertIn(marker.lower(),prompt.lower())

    async def test_ai_failure_never_closes_a_45_minute_position(self):
        self.call.side_effect=RuntimeError('network')
        with patch.object(settings,'POSITION_REVIEW_EXECUTE',True):
            result=(await self.review(fixtures.market(positions=[position()])) )['reviews'][0]
        self.assertEqual(result['status'],'ERROR');self.assertFalse(result['execute_close'])

    async def test_close_needs_invalid_thesis_or_high_sl_risk_and_cost_comparison(self):
        self.call.return_value.output_text=json.dumps(self.output(thesis_invalid=False,sl_risk_high=False))
        with patch.object(settings,'POSITION_REVIEW_EXECUTE',True): result=(await self.review(fixtures.market(positions=[position()])))['reviews'][0]
        self.assertFalse(result['execute_close'])

    async def test_stale_quote_never_calls_ai(self):
        result=await self.review(fixtures.market(tick_age_seconds=20,positions=[position()]))
        self.assertEqual(result['reason'],'INVALID_OR_STALE_SNAPSHOT');self.call.assert_not_awaited()

    async def test_preclose_takes_priority_and_has_separate_t10_bucket(self):
        now=int(time.time());m=fixtures.market(positions=[position(open_time=now-60)],broker_session=dict(valid=True,close_time=now+1800,next_open_time=now+3600))
        with patch.object(settings,'PRECLOSE_ENABLED',True):
            first=(await self.review(m))['reviews'][0]
            later=m.model_copy(update={'server_time':now+1200})
            second=(await self.review(later))['reviews'][0]
        self.assertTrue(first['trigger'].endswith(':30'));self.assertTrue(second['trigger'].endswith(':10'))
        self.assertEqual(self.call.await_count,2)

    async def test_daily_hold_needs_configured_threshold_and_weekend_never_holds(self):
        self.call.return_value.output_text=json.dumps(self.output(decision='HOLD',thesis_invalid=False,sl_risk_high=False,close_preferred_after_cost=False))
        now=int(time.time())
        with patch.object(settings,'PRECLOSE_ENABLED',True),patch.object(settings,'POSITION_REVIEW_EXECUTE',True):
            for index,(threshold,weekly,valid) in enumerate([(None,False,False),(91,False,False),(90,False,True),(90,True,False)]):
                m=fixtures.market(account_id=str(index),positions=[position()],broker_session=dict(valid=True,close_time=now+600,next_open_time=now+172800,weekly=weekly))
                with patch.object(settings,'PRECLOSE_HOLD_MIN_CONFIDENCE',threshold): result=(await self.review(m))['reviews'][0]
                self.assertEqual(result['hold_session_close']>0,valid)

    async def test_invalid_boolean_and_stale_after_ai_fail_closed(self):
        self.call.return_value.output_text=json.dumps(self.output(thesis_invalid='yes'))
        result=(await self.review(fixtures.market(positions=[position()])))['reviews'][0]
        self.assertEqual(result['status'],'ERROR');self.assertFalse(result['execute_close'])


class APIIntegrationTests(unittest.TestCase):
    def test_market_signal_single_permit_fill_and_restart_via_http(self):
        from api import routes
        from fastapi.testclient import TestClient
        from main import app
        from services.signal_store import signal_store
        market=fixtures.market(account_id="part1-http-account")
        headers={"X-RIRI-API-Key":"m"*32,"X-RIRI-Account-ID":market.account_id,
                 "X-RIRI-Terminal-ID":market.terminal_id,"X-RIRI-Instance-ID":market.instance_id}
        score=fixtures.ScoringEngine().calculate(market).model_copy(update={"score":90,"qualified":True})
        client=TestClient(app)
        with patch.object(settings,"RIRI_MT5_API_KEY","m"*32), patch.object(routes.scoring_engine,"calculate",return_value=score), patch.object(routes.ai_trader,"decide",new=AsyncMock(return_value=TraderDecision(decision="BUY",confidence=90))):
            received=client.post('/mt5/market',headers=headers,json=market.model_dump(mode='json'))
            self.assertEqual(received.status_code,200,received.text)
            item=client.get('/execution/pending',headers=headers).json()['signal']
            self.assertIsNotNone(item)
            token='once-only-http-token'
            permit=dict(signal_id=item['signal_id'],execution_token=token)
            self.assertEqual(client.post('/execution/authorize',headers=headers,json=permit).status_code,200)
            self.assertEqual(client.post('/execution/authorize',headers=headers,json=permit).status_code,409)
            ack=dict(**permit,status='EXECUTED',action='BUY',requested_lot=item['lot'],filled_lot=item['lot'],entry_server_time=market.server_time,deal_id=44)
            self.assertEqual(client.post('/execution/confirm',headers=headers,json=ack).status_code,200)
            self.assertIsNone(signal_store.get_signal(market.identity_key))
            self.assertEqual(signal_store.reconcile_market(market).last_entry_server_time,market.server_time)

    def test_new_management_and_permit_endpoints_require_authentication(self):
        from fastapi.testclient import TestClient
        from main import app
        client=TestClient(app)
        self.assertEqual(client.post('/positions/review',json=fixtures.market().model_dump(mode='json')).status_code,401)
        self.assertEqual(client.post('/execution/authorize',json={'signal_id':'some-signal','execution_token':'abcdefghijklmnop'}).status_code,401)


if __name__=='__main__': unittest.main()
