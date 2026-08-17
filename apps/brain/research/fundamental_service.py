import statistics

from datetime import datetime, timezone


class FundamentalService:

    async def analyze(self):

        # ==================================================
        # CURRENT UTC TIME
        # ==================================================

        now = datetime.now(
            timezone.utc
        )

        utc_hour = now.hour

        # ==================================================
        # TRADING SESSIONS
        # ==================================================

        london_session = (
            7 <= utc_hour <= 16
        )

        newyork_session = (
            12 <= utc_hour <= 21
        )

        overlap = (
            london_session
            and newyork_session
        )

        # ==================================================
        # SESSION
        # ==================================================

        if overlap:

            session = "OVERLAP"

        elif newyork_session:

            session = "NEWYORK"

        elif london_session:

            session = "LONDON"

        else:

            session = "ASIA"

        # ==================================================
        # MARKET SENTIMENT
        #
        # No external fundamental/news feed yet.
        # Therefore sentiment remains neutral.
        # ==================================================

        market_sentiment = "NEUTRAL"

        gold_bias = "NEUTRAL"

        usd_bias = "NEUTRAL"

        # ==================================================
        # CONFIDENCE
        #
        # Session/liquidity confidence only.
        # ==================================================

        if overlap:

            confidence = 80

        elif (
            london_session
            or newyork_session
        ):

            confidence = 65

        else:

            confidence = 50

        # ==================================================
        # LIQUIDITY
        # ==================================================

        if overlap:

            liquidity = "VERY_HIGH"

        elif (
            london_session
            or newyork_session
        ):

            liquidity = "HIGH"

        else:

            liquidity = "LOW"

        # ==================================================
        # VOLATILITY
        # ==================================================

        if overlap:

            volatility = "HIGH"

        elif (
            london_session
            or newyork_session
        ):

            volatility = "MEDIUM"

        else:

            volatility = "LOW"

        # ==================================================
        # NEWS
        #
        # No external economic calendar connected yet.
        # ==================================================

        high_impact_news = False

        minutes_to_news = None

        # ==================================================
        # RISK LEVEL
        # ==================================================

        risk_level = "NORMAL"

        # ==================================================
        # SCORE
        # ==================================================

        session_score = (
            70
            if overlap
            else 50
        )

        liquidity_score = (
            70
            if liquidity == "VERY_HIGH"
            else 55
        )

        score = statistics.fmean(
            [
                confidence,
                session_score,
                liquidity_score
            ]
        )

        # ==================================================
        # RESULT
        # ==================================================

        return {

            "market_sentiment":
            market_sentiment,

            "confidence":
            confidence,

            "session":
            session,

            "liquidity":
            liquidity,

            "volatility":
            volatility,

            "high_impact_news":
            high_impact_news,

            "minutes_to_news":
            minutes_to_news,

            "gold_bias":
            gold_bias,

            "usd_bias":
            usd_bias,

            "risk_level":
            risk_level,

            "score":
            round(
                score,
                2
            )
        }