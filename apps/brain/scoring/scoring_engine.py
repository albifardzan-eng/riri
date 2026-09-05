from datetime import datetime, timezone

import pandas as pd

from config.trading_config import MIN_SCORE
from models.market_data import MarketData
from models.scoring import ScoringResult


class ScoringEngine:

    def calculate(
        self,
        market: MarketData
    ) -> ScoringResult:

        if (
            market is None
            or len(market.candles) < 100
        ):
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
            [
                c.model_dump()
                for c in market.candles
            ]
        )

        close = df["close"]

        # ==================================================
        # EMA
        # ==================================================

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

        # ==================================================
        # STANDARD SCORING
        # ==================================================

        trend_score = self._trend(
            ema5,
            ema10,
            ema100
        )

        rsi = self._rsi(df)

        momentum_score = self._momentum(rsi)

        volume_score = self._volume(
            df
        )

        volatility_score = self._volatility(
            market.atr
        )

        session_score = self._session()

        spread_score = self._spread(
            market.spread
        )

        # ==================================================
        # REVERSAL DETECTION
        #
        # Additional opportunity detector.
        #
        # Purpose:
        # Detect an abnormal price expansion where price
        # may temporarily reverse toward its recent range.
        #
        # AI Trader remains the final decision maker.
        # ==================================================

        reversal_score = self._reversal(
            df,
            market.atr
        )

        # ==================================================
        # BASE SCORE
        #
        # Existing six components remain unchanged.
        # Reversal is used as an additional qualification
        # signal without changing the ScoringResult model.
        # ==================================================

        total_score = (
            trend_score +
            momentum_score +
            volume_score +
            volatility_score +
            session_score +
            spread_score
        )

        # Reversal is context for AI Trader, not a seventh scoring weight.
        total_score = min(100, total_score)

        return ScoringResult(
            score=total_score,
            qualified=(
                total_score >= MIN_SCORE
            ),
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            volatility_score=volatility_score,
            session_score=session_score,
            spread_score=spread_score,
            rsi=round(rsi, 2),
            reversal_score=reversal_score
        )

    # ==================================================
    # TREND
    # ==================================================

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

    # ==================================================
    # MOMENTUM
    # ==================================================

    def _rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        delta = df["close"].diff()
        gains = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
        losses = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
        average_loss = float(losses.iloc[-1])
        if average_loss == 0:
            return 100.0
        rs = float(gains.iloc[-1]) / average_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _momentum(self, rsi: float) -> int:
        if rsi >= 60 or rsi <= 40:
            return 15
        if rsi >= 55 or rsi <= 45:
            return 10
        return 5

    # ==================================================
    # VOLUME
    # ==================================================

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

        if (
            current_volume
            > average_volume * 1.3
        ):

            return 20

        if (
            current_volume
            > average_volume
        ):

            return 15

        return 5

    # ==================================================
    # VOLATILITY
    # ==================================================

    def _volatility(
        self,
        atr: float
    ) -> int:

        if atr > 3:

            return 15

        if atr > 1.5:

            return 10

        return 5

    # ==================================================
    # SESSION
    # ==================================================

    def _session(
        self
    ) -> int:

        hour = (
            datetime.now(timezone.utc).hour
        )

        if 12 <= hour <= 17:

            return 15

        if 6 <= hour <= 21:

            return 10

        return 5

    # ==================================================
    # SPREAD
    # ==================================================

    def _spread(
        self,
        spread: float
    ) -> int:

        if spread <= 20:

            return 15

        if spread <= 35:

            return 10

        return 5

    # ==================================================
    # REVERSAL DETECTION
    # ==================================================

    def _reversal(
        self,
        df: pd.DataFrame,
        atr: float
    ) -> int:

        if len(df) < 20:

            return 0

        # --------------------------------------------------
        # Recent candles
        # --------------------------------------------------

        recent = df.tail(20)

        last = df.iloc[-1]

        last_close = float(
            last["close"]
        )

        last_high = float(
            last["high"]
        )

        last_low = float(
            last["low"]
        )

        # --------------------------------------------------
        # Recent support / resistance
        # --------------------------------------------------

        resistance = float(
            recent["high"]
            .iloc[:-1]
            .max()
        )

        support = float(
            recent["low"]
            .iloc[:-1]
            .min()
        )

        # --------------------------------------------------
        # Recent range
        # --------------------------------------------------

        recent_range = (
            float(recent["high"].max())
            -
            float(recent["low"].min())
        )

        if recent_range <= 0:

            return 0

        # --------------------------------------------------
        # Current candle range
        # --------------------------------------------------

        candle_range = (
            last_high -
            last_low
        )

        if candle_range <= 0:

            return 0

        # --------------------------------------------------
        # Expansion
        #
        # Detect unusually large candle relative to
        # recent market range.
        # --------------------------------------------------

        average_range = (
            (
                df["high"]
                -
                df["low"]
            )
            .tail(20)
            .mean()
        )

        expansion = (
            candle_range
            >
            average_range * 1.5
        )

        # --------------------------------------------------
        # ATR expansion
        # --------------------------------------------------

        atr_expansion = False

        if atr > 0:

            atr_expansion = (
                candle_range
                >
                atr * 1.5
            )

        # --------------------------------------------------
        # Position inside recent range
        # --------------------------------------------------

        distance_from_high = (
            recent["high"].max()
            -
            last_close
        )

        distance_from_low = (
            last_close
            -
            recent["low"].min()
        )

        near_resistance = (
            distance_from_high
            <=
            recent_range * 0.15
        )

        near_support = (
            distance_from_low
            <=
            recent_range * 0.15
        )

        # --------------------------------------------------
        # Wick rejection
        # --------------------------------------------------

        upper_wick = (
            last_high
            -
            max(
                last["open"],
                last["close"]
            )
        )

        lower_wick = (
            min(
                last["open"],
                last["close"]
            )
            -
            last_low
        )

        upper_rejection = (
            upper_wick
            >
            candle_range * 0.30
        )

        lower_rejection = (
            lower_wick
            >
            candle_range * 0.30
        )

        # --------------------------------------------------
        # Volume confirmation
        # --------------------------------------------------

        current_volume = float(
            last["volume"]
        )

        average_volume = float(
            df["volume"]
            .tail(20)
            .mean()
        )

        volume_spike = (
            current_volume
            >
            average_volume * 1.3
        )

        # --------------------------------------------------
        # Calculate reversal score
        # --------------------------------------------------

        score = 0

        if expansion:

            score += 25

        if atr_expansion:

            score += 20

        if near_resistance:

            score += 15

        if near_support:

            score += 15

        if upper_rejection:

            score += 10

        if lower_rejection:

            score += 10

        if volume_spike:

            score += 10

        # --------------------------------------------------
        # Avoid false reversal signal when price is simply
        # trending normally.
        # --------------------------------------------------

        if (
            not expansion
            and
            not atr_expansion
        ):

            score -= 15

        return max(
            0,
            min(
                100,
                score
            )
        )
