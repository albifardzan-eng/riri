import statistics
from datetime import datetime, timezone


class FundamentalService:

    async def analyze(self):

        utc_hour = (
            datetime.now(
                timezone.utc
            ).hour
        )

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

        market_sentiment = "NEUTRAL"

        confidence = 50

        if overlap:
            confidence = 80

        elif (
            london_session
            or newyork_session
        ):
            confidence = 65

        session = "ASIA"

        if london_session:
            session = "LONDON"

        if newyork_session:
            session = "NEWYORK"

        if overlap:
            session = "OVERLAP"

        liquidity = "LOW"

        if overlap:
            liquidity = "VERY_HIGH"

        elif (
            london_session
            or newyork_session
        ):
            liquidity = "HIGH"

        volatility = "LOW"

        if overlap:
            volatility = "HIGH"

        elif (
            london_session
            or newyork_session
        ):
            volatility = "MEDIUM"

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
            False,

            "minutes_to_news":
            None,

            "gold_bias":
            "NEUTRAL",

            "usd_bias":
            "NEUTRAL",

            "risk_level":
            "NORMAL",

            "score":
            statistics.fmean(
                [
                    confidence,
                    70 if overlap else 50,
                    70 if liquidity == "VERY_HIGH"
                    else 55
                ]
            )
        }