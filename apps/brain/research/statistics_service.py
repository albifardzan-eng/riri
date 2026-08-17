import pandas as pd


class StatisticsService:

    def analyze(
        self,
        market
    ):

        # ==================================================
        # VALIDATION
        # ==================================================

        if (
            market is None
            or len(market.candles) < 100
        ):
            return None

        df = pd.DataFrame(
            [
                candle.model_dump()
                for candle in market.candles
            ]
        )

        # ==================================================
        # PRICE DATA
        # ==================================================

        closes = df["close"]
        highs = df["high"]
        lows = df["low"]
        volumes = df["volume"]

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
        # EMA
        # ==================================================

        ema5 = (
            closes
            .ewm(
                span=5,
                adjust=False
            )
            .mean()
            .iloc[-1]
        )

        ema10 = (
            closes
            .ewm(
                span=10,
                adjust=False
            )
            .mean()
            .iloc[-1]
        )

        ema100 = (
            closes
            .ewm(
                span=100,
                adjust=False
            )
            .mean()
            .iloc[-1]
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

        trend_strength = min(
            100,
            int(
                abs(
                    (ema5 - ema100)
                    / ema100
                ) * 10000
            )
        )

        # ==================================================
        # DAILY / SESSION RANGE
        # ==================================================

        daily_range = (
            highs.max()
            - lows.min()
        )

        session_range = (
            highs.tail(24).max()
            - lows.tail(24).min()
        )

        # ==================================================
        # ATR
        # ==================================================

        atr_percentile = min(
            100,
            max(
                0,
                int(
                    market.atr * 20
                )
            )
        )

        # ==================================================
        # VOLATILITY
        # ==================================================

        volatility_percentile = min(
            100,
            max(
                0,
                int(
                    (
                        daily_range
                        / last_close
                    ) * 10000
                )
            )
        )

        # ==================================================
        # MOMENTUM
        # ==================================================

        momentum_5 = (
            last_close
            - closes.iloc[-5]
        )

        momentum_10 = (
            last_close
            - closes.iloc[-10]
        )

        momentum_direction = "NEUTRAL"

        if momentum_5 > 0:
            momentum_direction = "BULLISH"

        elif momentum_5 < 0:
            momentum_direction = "BEARISH"

        # ==================================================
        # RECENT RANGE
        # ==================================================

        recent_high = (
            highs.tail(20).max()
        )

        recent_low = (
            lows.tail(20).min()
        )

        recent_range = (
            recent_high
            - recent_low
        )

        # ==================================================
        # SUPPORT / RESISTANCE
        #
        # Use recent market structure as dynamic SNR.
        # ==================================================

        support = float(
            lows.tail(50).min()
        )

        resistance = float(
            highs.tail(50).max()
        )

        # ==================================================
        # DISTANCE TO SUPPORT / RESISTANCE
        # ==================================================

        distance_to_support = (
            last_close
            - support
        )

        distance_to_resistance = (
            resistance
            - last_close
        )

        # ==================================================
        # SNR PROXIMITY
        #
        # Determines whether price is close enough to
        # support/resistance to consider reversal.
        # ==================================================

        snr_threshold = max(
            market.atr * 1.5,
            1.0
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
        # POSITION INSIDE RECENT RANGE
        #
        # 0   = near support
        # 100 = near resistance
        # ==================================================

        range_position = 50.0

        if recent_range > 0:

            range_position = (
                (
                    last_close
                    - recent_low
                )
                / recent_range
            ) * 100

        range_position = max(
            0,
            min(
                100,
                range_position
            )
        )

        # ==================================================
        # OVEREXTENSION
        #
        # Detect whether price has moved unusually far
        # from EMA100.
        # ==================================================

        distance_from_ema100 = (
            last_close
            - ema100
        )

        distance_from_ema100_abs = abs(
            distance_from_ema100
        )

        overextended = (
            distance_from_ema100_abs
            >= max(
                market.atr * 2.0,
                2.0
            )
        )

        overextended_direction = "NONE"

        if overextended:

            if distance_from_ema100 > 0:

                overextended_direction = "UP"

            elif distance_from_ema100 < 0:

                overextended_direction = "DOWN"

        # ==================================================
        # CANDLE ANALYSIS
        # ==================================================

        candle_open = float(
            df["open"].iloc[-1]
        )

        candle_body = abs(
            last_close
            - candle_open
        )

        upper_wick = (
            last_high
            - max(
                candle_open,
                last_close
            )
        )

        lower_wick = (
            min(
                candle_open,
                last_close
            )
            - last_low
        )

        candle_range = (
            last_high
            - last_low
        )

        bullish_rejection = False
        bearish_rejection = False

        if candle_range > 0:

            bullish_rejection = (
                lower_wick
                >= candle_body * 1.5
                and lower_wick
                >= candle_range * 0.30
            )

            bearish_rejection = (
                upper_wick
                >= candle_body * 1.5
                and upper_wick
                >= candle_range * 0.30
            )

        # ==================================================
        # VOLUME ANALYSIS
        # ==================================================

        current_volume = float(
            volumes.iloc[-1]
        )

        average_volume = float(
            volumes.tail(20).mean()
        )

        volume_ratio = 0.0

        if average_volume > 0:

            volume_ratio = (
                current_volume
                / average_volume
            )

        volume_spike = (
            volume_ratio >= 1.30
        )

        # ==================================================
        # REVERSAL SIGNAL
        #
        # This does NOT automatically generate BUY/SELL.
        # It only gives AI Trader evidence.
        # ==================================================

        reversal_direction = "NONE"

        reversal_strength = 0

        # ----------------------------------------------
        # Bullish reversal
        # ----------------------------------------------

        if (
            near_support
            and bullish_rejection
        ):

            reversal_direction = "BUY"

            reversal_strength += 40

        if (
            near_support
            and momentum_5 > 0
        ):

            reversal_direction = "BUY"

            reversal_strength += 20

        if (
            overextended_direction == "DOWN"
            and bullish_rejection
        ):

            reversal_direction = "BUY"

            reversal_strength += 25

        # ----------------------------------------------
        # Bearish reversal
        # ----------------------------------------------

        if (
            near_resistance
            and bearish_rejection
        ):

            reversal_direction = "SELL"

            reversal_strength += 40

        if (
            near_resistance
            and momentum_5 < 0
        ):

            reversal_direction = "SELL"

            reversal_strength += 20

        if (
            overextended_direction == "UP"
            and bearish_rejection
        ):

            reversal_direction = "SELL"

            reversal_strength += 25

        # Volume confirmation

        if (
            reversal_direction != "NONE"
            and volume_spike
        ):

            reversal_strength += 15

        reversal_strength = min(
            100,
            reversal_strength
        )

        # ==================================================
        # POTENTIAL 1000 POINT MOVE
        #
        # XAUUSD point conversion is deliberately kept
        # simple here. AI Trader receives the raw price
        # movement and can evaluate the opportunity.
        # ==================================================

        target_distance = 1.0

        buy_target = (
            last_close
            + target_distance
        )

        sell_target = (
            last_close
            - target_distance
        )

        buy_target_possible = (
            resistance
            - last_close
            >= target_distance
        )

        sell_target_possible = (
            last_close
            - support
            >= target_distance
        )

        # ==================================================
        # MARKET LOCATION
        # ==================================================

        market_location = "MID_RANGE"

        if range_position <= 20:

            market_location = "NEAR_SUPPORT"

        elif range_position >= 80:

            market_location = "NEAR_RESISTANCE"

        # ==================================================
        # FINAL STATISTICS
        # ==================================================

        return {

            # ------------------------------------------
            # RANGE / VOLATILITY
            # ------------------------------------------

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
                market.atr,
                5
            ),

            "atr_percentile": (
                atr_percentile
            ),

            "volatility_percentile": (
                volatility_percentile
            ),

            # ------------------------------------------
            # EMA / TREND
            # ------------------------------------------

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

            # ------------------------------------------
            # MOMENTUM
            # ------------------------------------------

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

            # ------------------------------------------
            # SNR
            # ------------------------------------------

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

            # ------------------------------------------
            # OVEREXTENSION
            # ------------------------------------------

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

            # ------------------------------------------
            # CANDLE
            # ------------------------------------------

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

            # ------------------------------------------
            # VOLUME
            # ------------------------------------------

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

            # ------------------------------------------
            # REVERSAL
            # ------------------------------------------

            "reversal_direction": (
                reversal_direction
            ),

            "reversal_strength": (
                reversal_strength
            ),

            # ------------------------------------------
            # 1000 POINT OPPORTUNITY
            # ------------------------------------------

            "target_distance": (
                target_distance
            ),

            "buy_target": round(
                buy_target,
                2
            ),

            "sell_target": round(
                sell_target,
                2
            ),

            "buy_target_possible": (
                buy_target_possible
            ),

            "sell_target_possible": (
                sell_target_possible
            ),

            # ------------------------------------------
            # CURRENT PRICE
            # ------------------------------------------

            "last_close": round(
                last_close,
                2
            )
        }