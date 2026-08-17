import pandas as pd


class PatternService:

    def analyze(
        self,
        market
    ):

        if (
            market is None
            or len(market.candles) < 100
        ):
            return None

        # ==================================================
        # BUILD DATAFRAME
        # ==================================================

        df = pd.DataFrame(
            [
                candle.model_dump()
                for candle in market.candles
            ]
        )

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        current_close = float(
            close.iloc[-1]
        )

        # ==================================================
        # EMA
        # ==================================================

        ema5 = close.ewm(
            span=5,
            adjust=False
        ).mean()

        ema10 = close.ewm(
            span=10,
            adjust=False
        ).mean()

        ema100 = close.ewm(
            span=100,
            adjust=False
        ).mean()

        current_ema5 = float(
            ema5.iloc[-1]
        )

        current_ema10 = float(
            ema10.iloc[-1]
        )

        current_ema100 = float(
            ema100.iloc[-1]
        )

        bullish = (
            current_ema5
            >
            current_ema10
            >
            current_ema100
        )

        bearish = (
            current_ema5
            <
            current_ema10
            <
            current_ema100
        )

        # ==================================================
        # CURRENT CANDLE
        # ==================================================

        current_high = float(
            high.iloc[-1]
        )

        current_low = float(
            low.iloc[-1]
        )

        current_range = (
            current_high
            -
            current_low
        )

        # ==================================================
        # AVERAGE RANGE
        # ==================================================

        average_range = float(
            (
                high
                -
                low
            )
            .tail(20)
            .mean()
        )

        if average_range <= 0:
            average_range = 0.01

        breakout = (
            current_range
            >
            average_range * 1.5
        )

        # ==================================================
        # VOLUME
        # ==================================================

        current_volume = float(
            volume.iloc[-1]
        )

        average_volume = float(
            volume
            .tail(20)
            .mean()
        )

        if average_volume <= 0:
            average_volume = 1.0

        volume_spike = (
            current_volume
            >
            average_volume * 1.3
        )

        # ==================================================
        # RECENT PRICE MOVEMENT
        #
        # Used to detect sharp upward/downward movement
        # before a possible reversal.
        # ==================================================

        lookback = min(
            10,
            len(df) - 1
        )

        previous_close = float(
            close.iloc[-1 - lookback]
        )

        recent_move = (
            current_close
            -
            previous_close
        )

        recent_move_abs = abs(
            recent_move
        )

        # Number of average candle ranges moved.
        movement_strength = (
            recent_move_abs
            /
            average_range
        )

        sharp_up_move = (
            recent_move > 0
            and
            movement_strength >= 2.0
        )

        sharp_down_move = (
            recent_move < 0
            and
            movement_strength >= 2.0
        )

        # ==================================================
        # SUPPORT / RESISTANCE
        #
        # Use recent historical range rather than current
        # candle to avoid using the current candle itself
        # when defining the SNR level.
        # ==================================================

        snr_lookback = min(
            50,
            len(df) - 1
        )

        historical_high = float(
            high.iloc[-1 - snr_lookback:-1].max()
        )

        historical_low = float(
            low.iloc[-1 - snr_lookback:-1].min()
        )

        resistance = historical_high
        support = historical_low

        # ==================================================
        # DISTANCE TO SNR
        # ==================================================

        distance_to_support = (
            current_close
            -
            support
        )

        distance_to_resistance = (
            resistance
            -
            current_close
        )

        # SNR proximity is measured using average candle
        # range instead of a fixed price distance.
        snr_buffer = (
            average_range * 0.50
        )

        near_support = (
            distance_to_support >= 0
            and
            distance_to_support <= snr_buffer
        )

        near_resistance = (
            distance_to_resistance >= 0
            and
            distance_to_resistance <= snr_buffer
        )

        # ==================================================
        # EXTREME / OVEREXTENSION
        #
        # Price is considered overextended when it has moved
        # significantly away from EMA100.
        # ==================================================

        distance_from_ema100 = (
            current_close
            -
            current_ema100
        )

        extension_ratio = (
            abs(distance_from_ema100)
            /
            average_range
        )

        overextended_up = (
            distance_from_ema100 > 0
            and
            extension_ratio >= 3.0
        )

        overextended_down = (
            distance_from_ema100 < 0
            and
            extension_ratio >= 3.0
        )

        # ==================================================
        # REVERSAL CANDLE
        #
        # Detect rejection from extreme area.
        # ==================================================

        candle_body = abs(
            current_close
            -
            float(
                df["open"].iloc[-1]
            )
        )

        upper_wick = (
            current_high
            -
            max(
                current_close,
                float(
                    df["open"].iloc[-1]
                )
            )
        )

        lower_wick = (
            min(
                current_close,
                float(
                    df["open"].iloc[-1]
                )
            )
            -
            current_low
        )

        bullish_rejection = (
            lower_wick
            >
            candle_body
            and
            lower_wick
            >
            average_range * 0.30
        )

        bearish_rejection = (
            upper_wick
            >
            candle_body
            and
            upper_wick
            >
            average_range * 0.30
        )

        # ==================================================
        # REVERSAL CONDITIONS
        #
        # BUY reversal:
        # sharp decline + near support + rejection
        #
        # SELL reversal:
        # sharp rise + near resistance + rejection
        # ==================================================

        reversal_buy = (
            sharp_down_move
            and
            near_support
            and
            bullish_rejection
        )

        reversal_sell = (
            sharp_up_move
            and
            near_resistance
            and
            bearish_rejection
        )

        # Stronger reversal setup when price is also
        # significantly overextended from EMA100.

        strong_reversal_buy = (
            reversal_buy
            and
            overextended_down
        )

        strong_reversal_sell = (
            reversal_sell
            and
            overextended_up
        )

        # ==================================================
        # PRIMARY DIRECTION
        #
        # Reversal takes priority when a clear reversal
        # structure exists.
        # Otherwise follow EMA trend.
        # ==================================================

        if strong_reversal_buy:
            direction = "BUY_REVERSAL"

        elif strong_reversal_sell:
            direction = "SELL_REVERSAL"

        elif reversal_buy:
            direction = "BUY_REVERSAL"

        elif reversal_sell:
            direction = "SELL_REVERSAL"

        elif bullish:
            direction = "BUY"

        elif bearish:
            direction = "SELL"

        else:
            direction = "NONE"

        # ==================================================
        # PATTERN STRENGTH
        # ==================================================

        strength = 50

        if bullish or bearish:
            strength += 15

        if breakout:
            strength += 10

        if volume_spike:
            strength += 10

        if reversal_buy or reversal_sell:
            strength += 15

        if strong_reversal_buy or strong_reversal_sell:
            strength += 10

        strength = min(
            100,
            strength
        )

        # ==================================================
        # REVERSAL CONFIDENCE
        # ==================================================

        reversal_strength = 0

        if reversal_buy:
            reversal_strength = 60

        elif reversal_sell:
            reversal_strength = 60

        if strong_reversal_buy:
            reversal_strength = 85

        elif strong_reversal_sell:
            reversal_strength = 85

        if volume_spike and (
            reversal_buy
            or
            reversal_sell
        ):
            reversal_strength += 10

        reversal_strength = min(
            100,
            reversal_strength
        )

        # ==================================================
        # TP / SL PROBABILITY
        #
        # This is only an analytical estimate.
        # Final decision remains with AI Trader.
        # ==================================================

        tp_probability = min(
            95,
            strength
        )

        sl_probability = max(
            5,
            100 - tp_probability
        )

        # Reversal setup has separate probability because
        # it is a different trading thesis from trend-following.
        reversal_tp_probability = min(
            95,
            reversal_strength
        )

        reversal_sl_probability = max(
            5,
            100 - reversal_tp_probability
        )

        # ==================================================
        # RETURN
        # ==================================================

        return {

            # ----------------------------------------------
            # Direction
            # ----------------------------------------------

            "direction":
            direction,

            # ----------------------------------------------
            # EMA
            # ----------------------------------------------

            "ema5":
            round(
                current_ema5,
                2
            ),

            "ema10":
            round(
                current_ema10,
                2
            ),

            "ema100":
            round(
                current_ema100,
                2
            ),

            "trend":
            (
                "BULLISH"
                if bullish
                else
                "BEARISH"
                if bearish
                else
                "SIDEWAYS"
            ),

            # ----------------------------------------------
            # Pattern
            # ----------------------------------------------

            "pattern_strength":
            strength,

            "breakout":
            breakout,

            "volume_spike":
            volume_spike,

            "trend_alignment":
            bullish
            or
            bearish,

            # ----------------------------------------------
            # Movement
            # ----------------------------------------------

            "recent_move":
            round(
                recent_move,
                2
            ),

            "movement_strength":
            round(
                movement_strength,
                2
            ),

            "sharp_up_move":
            sharp_up_move,

            "sharp_down_move":
            sharp_down_move,

            # ----------------------------------------------
            # Support / Resistance
            # ----------------------------------------------

            "support":
            round(
                support,
                2
            ),

            "resistance":
            round(
                resistance,
                2
            ),

            "distance_to_support":
            round(
                distance_to_support,
                2
            ),

            "distance_to_resistance":
            round(
                distance_to_resistance,
                2
            ),

            "near_support":
            near_support,

            "near_resistance":
            near_resistance,

            # ----------------------------------------------
            # Overextension
            # ----------------------------------------------

            "distance_from_ema100":
            round(
                distance_from_ema100,
                2
            ),

            "extension_ratio":
            round(
                extension_ratio,
                2
            ),

            "overextended_up":
            overextended_up,

            "overextended_down":
            overextended_down,

            # ----------------------------------------------
            # Reversal
            # ----------------------------------------------

            "bullish_rejection":
            bullish_rejection,

            "bearish_rejection":
            bearish_rejection,

            "reversal_buy":
            reversal_buy,

            "reversal_sell":
            reversal_sell,

            "strong_reversal_buy":
            strong_reversal_buy,

            "strong_reversal_sell":
            strong_reversal_sell,

            "reversal_strength":
            reversal_strength,

            # ----------------------------------------------
            # Probability
            # ----------------------------------------------

            "tp_first_probability":
            tp_probability,

            "sl_first_probability":
            sl_probability,

            "reversal_tp_first_probability":
            reversal_tp_probability,

            "reversal_sl_first_probability":
            reversal_sl_probability,

            # ----------------------------------------------
            # Current market
            # ----------------------------------------------

            "last_close":
            round(
                current_close,
                2
            ),

            "average_range":
            round(
                average_range,
                2
            )
        }