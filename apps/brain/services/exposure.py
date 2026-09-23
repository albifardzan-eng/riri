"""Gross exposure and remaining loss to active stops in account currency."""
from config.settings import settings
from config.trading_config import RIRI_MAGIC_NUMBER, SL_POINTS


def exposure(market, candidate_lot=0.0):
    positions = [p for p in market.positions if p.magic_number == RIRI_MAGIC_NUMBER]
    orders = [p for p in market.pending_orders if p.magic_number == RIRI_MAGIC_NUMBER]
    known = market.tick_value > 0 and market.tick_size > 0
    risk = candidate_lot * SL_POINTS * market.point / market.tick_size * market.tick_value
    for p in positions + orders:
        if p.sl <= 0:
            known = False
            continue
        price = (market.bid if p.type == "BUY" else market.ask) if p in positions else p.open_price
        distance = max(0, price - p.sl) if p.type == "BUY" else max(0, p.sl - price)
        risk += distance / market.tick_size * market.tick_value * p.lot
    percent = 100 * risk / market.equity if known and market.equity > 0 else None
    cap = settings.MAX_SL_RISK_EQUITY_PERCENT
    return dict(gross_lot=sum(p.lot for p in positions + orders),
                slots=len(positions) + len(orders), pending_orders=len(orders),
                sl_risk_money=round(risk, 2) if known else None,
                sl_risk_equity_percent=percent, risk_cap_percent=cap,
                risk_allowed=cap is None or (percent is not None and percent <= cap),
                currency=market.account_currency,
                limitation="Nominal loss from current quote to stops; excludes gap/slippage.")
