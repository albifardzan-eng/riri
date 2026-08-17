from __future__ import annotations

import math

import pandas as pd


class StatisticsService:
    """
    Calculates deterministic market statistics for RIRI.

    This service does not make trading decisions.

    It provides:
        - trend
        - momentum
        - volatility
        - support / resistance
        - market location
        - overextension
        - candle rejection
        - volume conditions
        - reversal evidence

    AI Trader remains responsible for the final
    BUY / SELL / NONE decision.
    """

    MIN_CANDLES = 100

    EMA_FAST = 5
    EMA_MID = 10
    EMA_SLOW = 100

    MOMENTUM_FAST_LOOKBACK = 5
    MOMENTUM_SLOW_LOOKBACK = 10

    RECENT_RANGE_LOOKBACK = 20
    SNR_LOOKBACK = 50
    VOLUME_LOOKBACK = 20

    SNR_ATR_MULTIPLIER = 1.5
    SNR_MIN_DISTANCE = 1.0

    OVEREXTENSION_ATR_MULTIPLIER = 2.0
    OVEREXTENSION_MIN_DISTANCE = 2.0

    SHARP_MOVE_MULTIPLIER = 2.0

    VOLUME_SPIKE_RATIO = 1.30

    REJECTION_WICK_BODY_RATIO = 1.5
    REJECTION_RANGE_RATIO = 0.30

    def analyze(
        self,
        market
    ) -> dict | None:

        # ==================================================
        # VALIDATION
        # ==================================================

        if market is None:
            return None

        if len(market.candles) < self.MIN_CANDLES:
            return None

        # ==================================================
        # DATAFRAME
        # ==================================================

        df = pd.DataFrame(
            [
                candle.model_dump()
                for candle in market.candles
            ]
        )

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        if not required_columns.issubset(
            df.columns
        ):
            return None

        # Remove invalid rows.

        df = df[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ].copy()

        df = df.replace(
            [
                float("inf"),
                float("-inf"),
            ],
            float("nan")
        )

        df = df.dropna()

        if len(df) < self.MIN_CANDLES:
            return None

        # ==================================================
        # PRICE SERIES
        # ==================================================

        opens = df["open"].astype(float)
        highs = df["high"].astype(float)
        lows = df["low"].astype(float)
        closes = df["close"].astype(float)
        volumes = df["volume"].astype(float)

        last_open = float(
            opens.iloc[-1]
        )

        last_close = float(
            closes.iloc[-1]
        )

        last_high = float(
            highs.iloc[-1]
        )

        last_low = float(
            lows.iloc[-1]
        )

        # ==================================================
        # BASIC VALIDATION
        # ==================================================

        if last_close <= 0:
            return None

        # ==================================================
        # EMA
        # ==================================================

        ema5_series = closes.ewm(
            span=self.EMA_FAST,
            adjust=False
        ).mean()

        ema10_series = closes.ewm(
            span=self.EMA_MID,
            adjust=False
        ).mean()

        ema100_series = closes.ewm(
            span=self.EMA_SLOW,
            adjust=False
        ).mean()

        ema5 = float(
            ema5_series.iloc[-1]
        )

        ema10 = float(
            ema10_series.iloc[-1]
        )

        ema100 = float(
            ema100_series.iloc[-1]
        )

        # ==================================================
        # TREND
        # ==================================================

        if ema5 > ema10 > ema100:

            trend = "BULLISH"

        elif ema5 < ema10 < ema100:

            trend = "BEARISH"

        else:

            trend = "SIDEWAYS"

        # ==================================================
        # TREND STRENGTH
        # ==================================================

        trend_strength = 0

        if ema100 != 0:

            trend_strength = min(
                100,
                max(
                    0,
                    int(
                        abs(
                            (
                                ema5
                                -
                                ema100
                            )
                            /
                            ema100
                        )
                        * 10000
                    )
                )
            )

        # ==================================================
        # CANDLE RANGE SERIES
        # ==================================================

        candle_ranges = (
            highs
            -
            lows
        ).clip(
            lower=0
        )

        average_range = float(
            candle_ranges
            .tail(
                self.VOLUME_LOOKBACK
            )
            .mean()
        )

        if (
            not math.isfinite(
                average_range
            )
            or average_range <= 0
        ):

            average_range = 0.01

        # ==================================================
        # ATR
        # ==================================================

        atr = float(
            market.atr
        )

        if (
            not math.isfinite(
                atr
            )
            or atr < 0
        ):

            atr = 0.0

        # ==================================================
        # DAILY / SESSION / RECENT RANGE
        # ==================================================

        daily_range = float(
            highs.max()
            -
            lows.min()
        )

        session_window = min(
            24,
            len(df)
        )

        session_range = float(
            highs.tail(
                session_window
            ).max()
            -
            lows.tail(
                session_window
            ).min()
        )

        recent_window = min(
            self.RECENT_RANGE_LOOKBACK,
            len(df)
        )

        recent_high = float(
            highs.tail(
                recent_window
            ).max()
        )

        recent_low = float(
            lows.tail(
                recent_window
            ).min()
        )

        recent_range = (
            recent_high
            -
            recent_low
        )

        # ==================================================
        # ATR PERCENTILE PROXY
        # ==================================================

        atr_percentile = min(
            100,
            max(
                0,
                int(
                    atr * 20
                )
            )
        )

        # ==================================================
        # VOLATILITY PERCENTILE PROXY
        # ==================================================

        volatility_percentile = 0

        if last_close > 0:

            volatility_percentile = min(
                100,
                max(
                    0,
                    int(
                        (
                            daily_range
                            /
                            last_close
                        )
                        * 10000
                    )
                )
            )

        # ==================================================
        # MOMENTUM
        # ==================================================

        momentum_5 = 0.0

        momentum_10 = 0.0

        if len(closes) > self.MOMENTUM_FAST_LOOKBACK:

            momentum_5 = (
                last_close
                -
                float(
                    closes.iloc[
                        -self.MOMENTUM_FAST_LOOKBACK
                    ]
                )
            )

        if len(closes) > self.MOMENTUM_SLOW_LOOKBACK:

            momentum_10 = (
                last_close
                -
                float(
                    closes.iloc[
                        -self.MOMENTUM_SLOW_LOOKBACK
                    ]
                )
            )

        if momentum_5 > 0:

            momentum_direction = "BULLISH"

        elif momentum_5 < 0:

            momentum_direction = "BEARISH"

        else:

            momentum_direction = "NEUTRAL"

        # ==================================================
        # SUPPORT / RESISTANCE
        #
        # Current candle is excluded from the calculation.
        # This prevents the current price spike from
        # redefining its own support / resistance.
        # ==================================================

        snr_window = min(
            self.SNR_LOOKBACK,
            len(df) - 1
        )

        historical_highs = highs.iloc[
            -snr_window - 1:-1
        ]

        historical_lows = lows.iloc[
            -snr_window - 1:-1
        ]

        resistance = float(
            historical_highs.max()
        )

        support = float(
            historical_lows.min()
        )

        # ==================================================
        # DISTANCE TO SNR
        # ==================================================

        distance_to_support = max(
            0.0,
            last_close
            -
            support
        )

        distance_to_resistance = max(
            0.0,
            resistance
            -
            last_close
        )

        # ==================================================
        # SNR PROXIMITY
        # ==================================================

        snr_threshold = max(
            atr * self.SNR_ATR_MULTIPLIER,
            self.SNR_MIN_DISTANCE
        )

        near_support = (
            distance_to_support
            <= snr_threshold
        )

        near_resistance = (
            distance_to_resistance
            <= snr_threshold
        )

        # ==================================================
        # RANGE POSITION
        #
        # 0   = support
        # 100 = resistance
        # ==================================================

        range_position = 50.0

        if recent_range > 0:

            range_position = (
                (
                    last_close
                    -
                    recent_low
                )
                /
                recent_range
            ) * 100

        range_position = max(
            0.0,
            min(
                100.0,
                range_position
            )
        )

        if range_position <= 20:

            market_location = "NEAR_SUPPORT"

        elif range_position >= 80:

            market_location = "NEAR_RESISTANCE"

        else:

            market_location = "MID_RANGE"

        # ==================================================
        # OVEREXTENSION
        # ==================================================

        distance_from_ema100 = (
            last_close
            -
            ema100
        )

        distance_from_ema100_abs = abs(
            distance_from_ema100
        )

        overextension_threshold = max(
            atr * self.OVEREXTENSION_ATR_MULTIPLIER,
            self.OVEREXTENSION_MIN_DISTANCE
        )

        overextended = (
            distance_from_ema100_abs
            >= overextension_threshold
        )

        if not overextended:

            overextended_direction = "NONE"

        elif distance_from_ema100 > 0:

            overextended_direction = "UP"

        else:

            overextended_direction = "DOWN"

        # ==================================================
        # CURRENT CANDLE
        # ==================================================

        candle_body = abs(
            last_close
            -
            last_open
        )

        candle_range = max(
            0.0,
            last_high
            -
            last_low
        )

        upper_wick = max(
            0.0,
            last_high
            -
            max(
                last_open,
                last_close
            )
        )

        lower_wick = max(
            0.0,
            min(
                last_open,
                last_close
            )
            -
            last_low
        )

        # ==================================================
        # REJECTION
        # ==================================================

        bullish_rejection = False

        bearish_rejection = False

        if candle_range > 0:

            bullish_rejection = (
                lower_wick
                >=
                max(
                    candle_body
                    *
                    self.REJECTION_WICK_BODY_RATIO,
                    candle_range
                    *
                    self.REJECTION_RANGE_RATIO
                )
            )

            bearish_rejection = (
                upper_wick
                >=
                max(
                    candle_body
                    *
                    self.REJECTION_WICK_BODY_RATIO,
                    candle_range
                    *
                    self.REJECTION_RANGE_RATIO
                )
            )

        # ==================================================
        # VOLUME
        # ==================================================

        current_volume = float(
            volumes.iloc[-1]
        )

        average_volume = float(
            volumes.tail(
                self.VOLUME_LOOKBACK
            ).mean()
        )

        volume_ratio = 0.0

        if average_volume > 0:

            volume_ratio = (
                current_volume
                /
                average_volume
            )

        volume_spike = (
            volume_ratio
            >= self.VOLUME_SPIKE_RATIO
        )

        # ==================================================
        # RECENT PRICE MOVEMENT
        # ==================================================

        movement_lookback = min(
            10,
            len(df) - 1
        )

        previous_close = float(
            closes.iloc[
                -1 - movement_lookback
            ]
        )

        recent_move = (
            last_close
            -
            previous_close
        )

        recent_move_abs = abs(
            recent_move
        )

        movement_strength = (
            recent_move_abs
            /
            average_range
        )

        sharp_up_move = (
            recent_move > 0
            and
            movement_strength
            >= self.SHARP_MOVE_MULTIPLIER
        )

        sharp_down_move = (
            recent_move < 0
            and
            movement_strength
            >= self.SHARP_MOVE_MULTIPLIER
        )

        # ==================================================
        # REVERSAL EVIDENCE
        #
        # A reversal requires:
        #
        # BUY:
        #   1. Sharp downward expansion
        #   2. Price near support OR overextended down
        #   3. Bullish rejection
        #
        # SELL:
        #   1. Sharp upward expansion
        #   2. Price near resistance OR overextended up
        #   3. Bearish rejection
        #
        # Volume strengthens the setup but does not create
        # a reversal by itself.
        # ==================================================

        bullish_reversal_evidence = 0

        bearish_reversal_evidence = 0

        if sharp_down_move:

            bullish_reversal_evidence += 30

        if near_support:

            bullish_reversal_evidence += 25

        if overextended_direction == "DOWN":

            bullish_reversal_evidence += 20

        if bullish_rejection:

            bullish_reversal_evidence += 25

        if volume_spike:

            bullish_reversal_evidence += 10

        if sharp_up_move:

            bearish_reversal_evidence += 30

        if near_resistance:

            bearish_reversal_evidence += 25

        if overextended_direction == "UP":

            bearish_reversal_evidence += 20

        if bearish_rejection:

            bearish_reversal_evidence += 25

        if volume_spike:

            bearish_reversal_evidence += 10

        bullish_reversal_evidence = min(
            100,
            bullish_reversal_evidence
        )

        bearish_reversal_evidence = min(
            100,
            bearish_reversal_evidence
        )

        # ==================================================
        # REVERSAL VALIDATION
        #
        # Do not classify a candle as reversal merely
        # because it is large.
        #
        # Minimum structure:
        #   sharp move
        #   + rejection
        #   + location / extension
        # ==================================================

        bullish_reversal = (
            (
                sharp_down_move
                and
                bullish_rejection
                and
                (
                    near_support
                    or
                    overextended_direction == "DOWN"
                )
            )
        )

        bearish_reversal = (
            (
                sharp_up_move
                and
                bearish_rejection
                and
                (
                    near_resistance
                    or
                    overextended_direction == "UP"
                )
            )
        )

        # ==================================================
        # REVERSAL DIRECTION
        # ==================================================

        if (
            bullish_reversal
            and
            not bearish_reversal
        ):

            reversal_direction = "BUY"

            reversal_strength = (
                bullish_reversal_evidence
            )

        elif (
            bearish_reversal
            and
            not bullish_reversal
        ):

            reversal_direction = "SELL"

            reversal_strength = (
                bearish_reversal_evidence
            )

        elif (
            bullish_reversal
            and
            bearish_reversal
        ):

            # Conflicting reversal evidence.
            # Do not force a direction.

            reversal_direction = "NONE"

            reversal_strength = 0

        else:

            reversal_direction = "NONE"

            reversal_strength = 0

        # ==================================================
        # TREND / REVERSAL CONTEXT
        # ==================================================

        trend_alignment = (
            trend != "SIDEWAYS"
        )

        # ==================================================
        # TARGET ANALYTICS
        #
        # The execution layer remains the source of truth
        # for actual TP/SL distances.
        #
        # These fields represent available room toward
        # the current structural S/R levels only.
        # ==================================================

        buy_room = max(
            0.0,
            resistance
            -
            last_close
        )

        sell_room = max(
            0.0,
            last_close
            -
            support
        )

        # ==================================================
        # FINAL RESULT
        # ==================================================

        return {

            # ----------------------------------------------
            # RANGE / VOLATILITY
            # ----------------------------------------------

            "daily_range": round(
                daily_range,
                2
            ),

            "session_range": round(
                session_range,
                2
            ),

            "recent_range": round(
                recent_range,
                2
            ),

            "atr": round(
                atr,
                5
            ),

            "atr_percentile": (
                atr_percentile
            ),

            "volatility_percentile": (
                volatility_percentile
            ),

            # ----------------------------------------------
            # EMA / TREND
            # ----------------------------------------------

            "ema5": round(
                ema5,
                2
            ),

            "ema10": round(
                ema10,
                2
            ),

            "ema100": round(
                ema100,
                2
            ),

            "trend": trend,

            "trend_strength": (
                trend_strength
            ),

            "trend_alignment": (
                trend_alignment
            ),

            # ----------------------------------------------
            # MOMENTUM
            # ----------------------------------------------

            "momentum": round(
                momentum_5,
                2
            ),

            "momentum_5": round(
                momentum_5,
                2
            ),

            "momentum_10": round(
                momentum_10,
                2
            ),

            "momentum_direction": (
                momentum_direction
            ),

            # ----------------------------------------------
            # SUPPORT / RESISTANCE
            # ----------------------------------------------

            "support": round(
                support,
                2
            ),

            "resistance": round(
                resistance,
                2
            ),

            "distance_to_support": round(
                distance_to_support,
                2
            ),

            "distance_to_resistance": round(
                distance_to_resistance,
                2
            ),

            "near_support": (
                near_support
            ),

            "near_resistance": (
                near_resistance
            ),

            "range_position": round(
                range_position,
                2
            ),

            "market_location": (
                market_location
            ),

            # ----------------------------------------------
            # OVEREXTENSION
            # ----------------------------------------------

            "distance_from_ema100": round(
                distance_from_ema100,
                2
            ),

            "overextended": (
                overextended
            ),

            "overextended_direction": (
                overextended_direction
            ),

            "extension_ratio": round(
                (
                    distance_from_ema100_abs
                    /
                    average_range
                ),
                2
            ),

            # ----------------------------------------------
            # CANDLE
            # ----------------------------------------------

            "candle_body": round(
                candle_body,
                2
            ),

            "upper_wick": round(
                upper_wick,
                2
            ),

            "lower_wick": round(
                lower_wick,
                2
            ),

            "candle_range": round(
                candle_range,
                2
            ),

            "bullish_rejection": (
                bullish_rejection
            ),

            "bearish_rejection": (
                bearish_rejection
            ),

            # ----------------------------------------------
            # VOLUME
            # ----------------------------------------------

            "current_volume": round(
                current_volume,
                2
            ),

            "average_volume": round(
                average_volume,
                2
            ),

            "volume_ratio": round(
                volume_ratio,
                2
            ),

            "volume_spike": (
                volume_spike
            ),

            # ----------------------------------------------
            # MOVEMENT
            # ----------------------------------------------

            "recent_move": round(
                recent_move,
                2
            ),

            "movement_strength": round(
                movement_strength,
                2
            ),

            "sharp_up_move": (
                sharp_up_move
            ),

            "sharp_down_move": (
                sharp_down_move
            ),

            # ----------------------------------------------
            # REVERSAL
            # ----------------------------------------------

            "bullish_reversal": (
                bullish_reversal
            ),

            "bearish_reversal": (
                bearish_reversal
            ),

            "reversal_direction": (
                reversal_direction
            ),

            "reversal_strength": (
                reversal_strength
            ),

            "bullish_reversal_evidence": (
                bullish_reversal_evidence
            ),

            "bearish_reversal_evidence": (
                bearish_reversal_evidence
            ),

            # ----------------------------------------------
            # STRUCTURAL ROOM
            # ----------------------------------------------

            "buy_room": round(
                buy_room,
                2
            ),

            "sell_room": round(
                sell_room,
                2
            ),

            # ----------------------------------------------
            # CURRENT PRICE
            # ----------------------------------------------

            "last_close": round(
                last_close,
                2
            )
        }