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

        bullish = (
            ema5.iloc[-1]
            >
            ema10.iloc[-1]
            >
            ema100.iloc[-1]
        )

        bearish = (
            ema5.iloc[-1]
            <
            ema10.iloc[-1]
            <
            ema100.iloc[-1]
        )

        current_range = (
            high.iloc[-1]
            -
            low.iloc[-1]
        )

        average_range = (
            (
                high
                -
                low
            )
            .tail(20)
            .mean()
        )

        breakout = (
            current_range
            >
            average_range
            * 1.5
        )

        current_volume = (
            volume.iloc[-1]
        )

        average_volume = (
            volume
            .tail(20)
            .mean()
        )

        volume_spike = (
            current_volume
            >
            average_volume
            * 1.3
        )

        strength = 50

        if bullish or bearish:
            strength += 15

        if breakout:
            strength += 20

        if volume_spike:
            strength += 15

        strength = min(
            100,
            strength
        )

        if bullish:

            direction = "BUY"

        elif bearish:

            direction = "SELL"

        else:

            direction = "NONE"

        tp_probability = min(
            95,
            strength
        )

        sl_probability = max(
            5,
            100 - tp_probability
        )

        return {

            "direction":
            direction,

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

            "tp_first_probability":
            tp_probability,

            "sl_first_probability":
            sl_probability
        }