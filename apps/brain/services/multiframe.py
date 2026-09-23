"""Deterministic context from closed candles; no invented higher-timeframe data."""
def context(market):
    result={}
    for frame,candles in {market.timeframe:market.candles,**market.timeframes}.items():
        ema=None; previous=None; ranges=[]
        for c in candles:
            ema=c.close if ema is None else c.close*(2/21)+ema*(19/21)
            ranges.append(max(c.high-c.low,abs(c.high-previous),abs(c.low-previous)) if previous else c.high-c.low)
            previous=c.close
        atr=sum(ranges[-14:])/min(14,len(ranges))
        recent=candles[-20:]
        result[frame]={"ema20":ema,"atr14":atr,"last_closed_time":candles[-1].time,
            "distance_ema_atr":((market.bid+market.ask)/2-ema)/atr if atr>0 else None,
            "range_high20":max(c.high for c in recent),"range_low20":min(c.low for c in recent),
            "change5_atr":(candles[-1].close-candles[-6].close)/atr if atr>0 and len(candles)>5 else None,
            "upper_wick":candles[-1].high-max(candles[-1].open,candles[-1].close),
            "lower_wick":min(candles[-1].open,candles[-1].close)-candles[-1].low}
    return result
