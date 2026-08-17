from datetime import datetime, timezone


class FundamentalService:

    async def analyze(
        self,
        market
    ):

        if market is None:

            return self._default()

        fundamental = (
            market.fundamental
        )

        if fundamental is None:

            return self._default()

        high_impact_news = (
            fundamental.high_impact_news
        )

        minutes_to_news = (
            fundamental.minutes_to_news
        )

        phase = (
            fundamental.phase
        )

        risk_level = "NORMAL"

        if high_impact_news:

            # ------------------------------------------
            # UPCOMING HIGH IMPACT NEWS
            # ------------------------------------------

            if (
                phase == "UPCOMING"
                and
                minutes_to_news is not None
            ):

                if minutes_to_news <= 5:

                    risk_level = "EXTREME"

                elif minutes_to_news <= 15:

                    risk_level = "HIGH"

                else:

                    risk_level = "ELEVATED"

            # ------------------------------------------
            # RECENT HIGH IMPACT NEWS
            # ------------------------------------------

            elif phase == "RECENT":

                # Recent release means market can still
                # be experiencing displacement,
                # spread expansion and price discovery.

                if (
                    minutes_to_news is not None
                    and
                    abs(minutes_to_news) <= 5
                ):

                    risk_level = "EXTREME"

                else:

                    risk_level = "HIGH"

        # ----------------------------------------------
        # GOLD / USD BIAS
        #
        # We intentionally DO NOT infer directional bias
        # simply from event name.
        #
        # AI Trader should evaluate actual vs forecast
        # together with price action.
        # ----------------------------------------------

        gold_bias = "NEUTRAL"

        usd_bias = "NEUTRAL"

        actual = fundamental.actual

        forecast = fundamental.forecast

        if (
            actual is not None
            and
            forecast is not None
        ):

            if actual > forecast:

                usd_bias = "POTENTIALLY_STRONGER"

            elif actual < forecast:

                usd_bias = "POTENTIALLY_WEAKER"

        # ----------------------------------------------
        # SCORE
        # ----------------------------------------------

        if risk_level == "EXTREME":

            score = 20

        elif risk_level == "HIGH":

            score = 35

        elif risk_level == "ELEVATED":

            score = 50

        else:

            score = 70

        return {

            "available":
            fundamental.available,

            "market_sentiment":
            "NEWS_DRIVEN"
            if high_impact_news
            else "NEUTRAL",

            "high_impact_news":
            high_impact_news,

            "event":
            fundamental.event,

            "currency":
            fundamental.currency,

            "impact":
            fundamental.impact,

            "phase":
            phase,

            "minutes_to_news":
            minutes_to_news,

            "news_time":
            fundamental.news_time,

            "actual":
            actual,

            "forecast":
            forecast,

            "previous":
            fundamental.previous,

            "gold_bias":
            gold_bias,

            "usd_bias":
            usd_bias,

            "risk_level":
            risk_level,

            "score":
            score
        }

    def _default(self):

        return {

            "available":
            False,

            "market_sentiment":
            "NEUTRAL",

            "high_impact_news":
            False,

            "event":
            None,

            "currency":
            "USD",

            "impact":
            "NONE",

            "phase":
            None,

            "minutes_to_news":
            None,

            "news_time":
            None,

            "actual":
            None,

            "forecast":
            None,

            "previous":
            None,

            "gold_bias":
            "NEUTRAL",

            "usd_bias":
            "NEUTRAL",

            "risk_level":
            "UNKNOWN",

            "score":
            50
        }