import pandas as pd


class StatisticsService:

    def analyze(self, market):

        if len(market.candles) < 100:
            return None

        df = pd.DataFrame([
            c.model_dump()
            for c in market.candles
        ])

        closes = df["close"]

        daily_range = (
            df["high"].max()
            - df["low"].min()
        )

        session_range = (
            df.tail(24)["high"].max()
            - df.tail(24)["low"].min()
        )

        atr_percentile = min(
            100,
            int(market.atr * 20)
        )

        ema5 = closes.ewm(
            span=5,
            adjust=False
        ).mean().iloc[-1]

        ema100 = closes.ewm(
            span=100,
            adjust=False
        ).mean().iloc[-1]

        trend_strength = min(
            100,
            int(
                abs(
                    (ema5 - ema100)
                    / ema100
                ) * 10000
            )
        )

        volatility_percentile = min(
            100,
            int(
                (
                    daily_range
                    / closes.iloc[-1]
                ) * 10000
            )
        )

        return {
            "daily_range": round(daily_range, 2),
            "session_range": round(session_range, 2),
            "atr_percentile": atr_percentile,
            "trend_strength": trend_strength,
            "volatility_percentile": volatility_percentile
        }