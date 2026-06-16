from datetime import datetime

import pandas as pd

from config.trading_config import MIN_SCORE
from models.market_data import MarketData
from models.scoring import ScoringResult


class ScoringEngine:

    def calculate(
        self,
        market: MarketData
    ) -> ScoringResult:

        if len(market.candles) < 100:
            return ScoringResult(
                score=0,
                qualified=False,
                trend_score=0,
                momentum_score=0,
                volume_score=0,
                volatility_score=0,
                session_score=0,
                spread_score=0
            )

        df = pd.DataFrame(
            [c.model_dump() for c in market.candles]
        )

        close = df["close"]

        ema5 = close.ewm(
            span=5,
            adjust=False
        ).mean().iloc[-1]

        ema10 = close.ewm(
            span=10,
            adjust=False
        ).mean().iloc[-1]

        ema100 = close.ewm(
            span=100,
            adjust=False
        ).mean().iloc[-1]

        trend_score = self._trend(
            ema5,
            ema10,
            ema100
        )

        momentum_score = self._momentum(df)

        volume_score = self._volume(df)

        volatility_score = self._volatility(
            market.atr
        )

        session_score = self._session()

        spread_score = self._spread(
            market.spread
        )

        total_score = (
            trend_score +
            momentum_score +
            volume_score +
            volatility_score +
            session_score +
            spread_score
        )

        return ScoringResult(
            score=total_score,
            qualified=total_score >= MIN_SCORE,
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            volatility_score=volatility_score,
            session_score=session_score,
            spread_score=spread_score
        )

    def _trend(
        self,
        ema5: float,
        ema10: float,
        ema100: float
    ) -> int:

        if ema5 > ema10 > ema100:
            return 20

        if ema5 < ema10 < ema100:
            return 20

        return 5

    def _momentum(
        self,
        df: pd.DataFrame
    ) -> int:

        last_close = df["close"].iloc[-1]
        previous_close = df["close"].iloc[-5]

        move = abs(
            last_close - previous_close
        )

        if move > 3:
            return 15

        if move > 1:
            return 10

        return 5

    def _volume(
        self,
        df: pd.DataFrame
    ) -> int:

        current_volume = (
            df["volume"].iloc[-1]
        )

        average_volume = (
            df["volume"]
            .tail(20)
            .mean()
        )

        if current_volume > average_volume * 1.3:
            return 20

        if current_volume > average_volume:
            return 15

        return 5

    def _volatility(
        self,
        atr: float
    ) -> int:

        if atr > 3:
            return 15

        if atr > 1.5:
            return 10

        return 5

    def _session(
        self
    ) -> int:

        hour = datetime.utcnow().hour

        if 12 <= hour <= 17:
            return 15

        if 6 <= hour <= 21:
            return 10

        return 5

    def _spread(
        self,
        spread: float
    ) -> int:

        if spread <= 20:
            return 15

        if spread <= 35:
            return 10

        return 5