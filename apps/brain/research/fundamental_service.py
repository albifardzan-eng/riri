from datetime import datetime, timezone


class FundamentalService:

    async def analyze(
        self,
        market=None
    ):

        # ==================================================
        # CURRENT UTC TIME
        # ==================================================

        now = datetime.now(
            timezone.utc
        )

        utc_hour = now.hour

        # ==================================================
        # TRADING SESSION
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

        if overlap:
            session = "OVERLAP"

        elif newyork_session:
            session = "NEWYORK"

        elif london_session:
            session = "LONDON"

        else:
            session = "ASIA"

        # ==================================================
        # DEFAULT STATE
        # ==================================================

        market_sentiment = "NEUTRAL"

        gold_bias = "NEUTRAL"

        usd_bias = "NEUTRAL"

        fed_bias = "NEUTRAL"

        confidence = 50

        liquidity = "LOW"

        volatility = "LOW"

        risk_level = "NORMAL"

        high_impact_news = False
        available = False

        minutes_to_news = None

        event = None
        currency = "USD"
        impact = "NONE"
        phase = "NONE"

        actual = None
        forecast = None
        previous = None

        event_id = None
        news_time = None

        # ==================================================
        # SESSION CONTEXT
        # ==================================================

        if overlap:

            confidence = 80
            liquidity = "VERY_HIGH"
            volatility = "HIGH"

        elif (
            london_session
            or newyork_session
        ):

            confidence = 65
            liquidity = "HIGH"
            volatility = "MEDIUM"

        # ==================================================
        # READ MT5 FUNDAMENTAL
        #
        # routes.py passes:
        #
        # data.fundamental
        #
        # directly.
        # ==================================================

        mt5_fundamental = None

        if hasattr(market, "model_dump"):
            market = market.model_dump()

        if isinstance(
            market,
            dict
        ):

            mt5_fundamental = market

        # ==================================================
        # EXTRACT DATA
        # ==================================================

        if isinstance(
            mt5_fundamental,
            dict
        ):

            available = bool(
                mt5_fundamental.get(
                    "available",
                    False
                )
            )

            high_impact_news = bool(
                mt5_fundamental.get(
                    "high_impact_news",
                    False
                )
            )

            event = (
                mt5_fundamental.get(
                    "event"
                )
            )

            currency = (
                mt5_fundamental.get(
                    "currency",
                    "USD"
                )
            )

            impact = (
                mt5_fundamental.get(
                    "impact",
                    "NONE"
                )
            )

            phase = (
                mt5_fundamental.get(
                    "phase",
                    "NONE"
                )
            )

            minutes_to_news = (
                mt5_fundamental.get(
                    "minutes_to_news"
                )
            )

            actual = (
                mt5_fundamental.get(
                    "actual"
                )
            )

            forecast = (
                mt5_fundamental.get(
                    "forecast"
                )
            )

            previous = (
                mt5_fundamental.get(
                    "previous"
                )
            )

            event_id = (
                mt5_fundamental.get(
                    "event_id"
                )
            )

            news_time = (
                mt5_fundamental.get(
                    "news_time"
                )
            )

        # ==================================================
        # EVENT NORMALIZATION
        # ==================================================

        event_text = ""

        if event:

            event_text = str(
                event
            ).upper()

        # ==================================================
        # NEWS STATE
        # ==================================================

        news_state = "NONE"

        if high_impact_news:

            if phase == "UPCOMING":

                news_state = "UPCOMING"

            elif phase == "RECENT":

                news_state = "RECENT"

            else:

                news_state = "ACTIVE"

        # ==================================================
        # PRE NEWS
        # ==================================================

        pre_news_risk = False

        if (
            high_impact_news
            and
            phase == "UPCOMING"
            and
            minutes_to_news is not None
        ):

            try:

                minutes = float(
                    minutes_to_news
                )

                if 0 <= minutes <= 30:

                    pre_news_risk = True

            except (
                TypeError,
                ValueError
            ):

                pass

        # ==================================================
        # POST NEWS
        # ==================================================

        post_news_analysis = (
            high_impact_news
            and
            phase == "RECENT"
        )

        # ==================================================
        # EVENT CLASSIFICATION
        # ==================================================

        inflation_event = any(
            keyword in event_text
            for keyword in (
                "CPI",
                "INFLATION",
                "PCE",
                "CORE PCE"
            )
        )

        employment_event = any(
            keyword in event_text
            for keyword in (
                "NONFARM",
                "NON-FARM",
                "PAYROLL",
                "UNEMPLOYMENT",
                "JOBLESS",
                "ADP EMPLOYMENT",
                "INITIAL JOBLESS",
                "CONTINUING JOBLESS"
            )
        )

        central_bank_event = any(
            keyword in event_text
            for keyword in (
                "FOMC",
                "FEDERAL FUNDS",
                "FED INTEREST",
                "FEDERAL RESERVE",
                "POWELL",
                "INTEREST RATE DECISION",
                "FED RATE"
            )
        )

        growth_event = any(
            keyword in event_text
            for keyword in (
                "GDP",
                "RETAIL SALES",
                "ISM",
                "PMI"
            )
        )

        # ==================================================
        # RAW SURPRISE
        # ==================================================

        surprise_direction = "NONE"

        surprise_strength = 0

        forecast_difference = None

        previous_difference = None

        forecast_surprise_pct = None

        previous_change_pct = None

        if (
            actual is not None
            and
            forecast is not None
        ):

            try:

                actual_value = float(
                    actual
                )

                forecast_value = float(
                    forecast
                )

                forecast_difference = (
                    actual_value
                    -
                    forecast_value
                )

                if forecast_difference > 0:

                    surprise_direction = "POSITIVE"

                elif forecast_difference < 0:

                    surprise_direction = "NEGATIVE"

                else:

                    surprise_direction = "INLINE"

                if forecast_value != 0:

                    forecast_surprise_pct = (
                        abs(
                            forecast_difference
                        )
                        /
                        abs(
                            forecast_value
                        )
                    ) * 100

                    if forecast_surprise_pct >= 10:
                        surprise_strength = 100

                    elif forecast_surprise_pct >= 5:
                        surprise_strength = 75

                    elif forecast_surprise_pct >= 2:
                        surprise_strength = 50

                    else:
                        surprise_strength = 25

            except (
                TypeError,
                ValueError,
                ZeroDivisionError
            ):

                pass

        # ==================================================
        # ACTUAL VS PREVIOUS
        # ==================================================

        if (
            actual is not None
            and
            previous is not None
        ):

            try:

                actual_value = float(
                    actual
                )

                previous_value = float(
                    previous
                )

                previous_difference = (
                    actual_value
                    -
                    previous_value
                )

                if previous_value != 0:

                    previous_change_pct = (
                        previous_difference
                        /
                        abs(previous_value)
                    ) * 100

            except (
                TypeError,
                ValueError,
                ZeroDivisionError
            ):

                pass

        # ==================================================
        # PRE-NEWS
        #
        # No directional economic conclusion before
        # actual data is released.
        # ==================================================

        if pre_news_risk:

            market_sentiment = (
                "PRE_NEWS_RISK"
            )

            gold_bias = "NEUTRAL"

            usd_bias = "NEUTRAL"

            fed_bias = "NEUTRAL"

            risk_level = "HIGH"

        # ==================================================
        # POST-NEWS FUNDAMENTAL INTERPRETATION
        # ==================================================

        elif post_news_analysis:

            # ==================================================
            # INFLATION
            # ==================================================

            if inflation_event:

                if surprise_direction == "POSITIVE":

                    usd_bias = "BULLISH"

                    gold_bias = "BEARISH"

                    fed_bias = "HAWKISH"

                    market_sentiment = (
                        "USD_BULLISH"
                    )

                elif surprise_direction == "NEGATIVE":

                    usd_bias = "BEARISH"

                    gold_bias = "BULLISH"

                    fed_bias = "DOVISH"

                    market_sentiment = (
                        "USD_BEARISH"
                    )

                else:

                    market_sentiment = (
                        "INFLATION_INLINE"
                    )

            # ==================================================
            # EMPLOYMENT
            #
            # Special handling:
            #
            # Payroll / employment:
            # higher = USD bullish
            #
            # Unemployment:
            # higher = USD bearish
            #
            # Jobless claims:
            # higher = USD bearish
            # ==================================================

            elif employment_event:

                unemployment_event = (
                    "UNEMPLOYMENT"
                    in event_text
                )

                jobless_event = (
                    "JOBLESS"
                    in event_text
                )

                if (
                    unemployment_event
                    or
                    jobless_event
                ):

                    if surprise_direction == "POSITIVE":

                        usd_bias = "BEARISH"

                        gold_bias = "BULLISH"

                        fed_bias = "DOVISH"

                        market_sentiment = (
                            "USD_BEARISH"
                        )

                    elif surprise_direction == "NEGATIVE":

                        usd_bias = "BULLISH"

                        gold_bias = "BEARISH"

                        fed_bias = "HAWKISH"

                        market_sentiment = (
                            "USD_BULLISH"
                        )

                    else:

                        market_sentiment = (
                            "EMPLOYMENT_INLINE"
                        )

                else:

                    if surprise_direction == "POSITIVE":

                        usd_bias = "BULLISH"

                        gold_bias = "BEARISH"

                        fed_bias = "HAWKISH"

                        market_sentiment = (
                            "USD_BULLISH"
                        )

                    elif surprise_direction == "NEGATIVE":

                        usd_bias = "BEARISH"

                        gold_bias = "BULLISH"

                        fed_bias = "DOVISH"

                        market_sentiment = (
                            "USD_BEARISH"
                        )

                    else:

                        market_sentiment = (
                            "EMPLOYMENT_INLINE"
                        )

            # ==================================================
            # CENTRAL BANK
            # ==================================================

            elif central_bank_event:

                market_sentiment = (
                    "CENTRAL_BANK_EVENT"
                )

                risk_level = "HIGH"

            # ==================================================
            # GROWTH
            # ==================================================

            elif growth_event:

                if surprise_direction == "POSITIVE":

                    usd_bias = "BULLISH"

                    gold_bias = "BEARISH"

                    fed_bias = "HAWKISH"

                    market_sentiment = (
                        "USD_BULLISH"
                    )

                elif surprise_direction == "NEGATIVE":

                    usd_bias = "BEARISH"

                    gold_bias = "BULLISH"

                    fed_bias = "DOVISH"

                    market_sentiment = (
                        "USD_BEARISH"
                    )

                else:

                    market_sentiment = (
                        "GROWTH_INLINE"
                    )

            # ==================================================
            # UNKNOWN HIGH IMPACT EVENT
            # ==================================================

            elif high_impact_news:

                market_sentiment = (
                    "HIGH_IMPACT_EVENT"
                )

            risk_level = "HIGH"

        # ==================================================
        # HIGH IMPACT EVENT WITHOUT RELEASE
        # ==================================================

        elif high_impact_news:

            risk_level = "ELEVATED"

            market_sentiment = (
                "HIGH_IMPACT_EVENT"
            )

        # ==================================================
        # FUNDAMENTAL CONFIDENCE
        # ==================================================

        fundamental_confidence = 0

        if high_impact_news:

            fundamental_confidence = 40

        if post_news_analysis:

            fundamental_confidence += int(
                surprise_strength * 0.40
            )

        if (
            post_news_analysis
            and
            surprise_direction == "INLINE"
        ):

            fundamental_confidence = max(
                30,
                fundamental_confidence
            )

        fundamental_confidence = min(
            100,
            fundamental_confidence
        )

        # ==================================================
        # FUNDAMENTAL STRENGTH
        # ==================================================

        fundamental_strength = (
            fundamental_confidence
        )

        if (
            post_news_analysis
            and
            previous_change_pct is not None
        ):

            if (
                abs(
                    previous_change_pct
                ) >= 5
            ):

                fundamental_strength += 10

        fundamental_strength = min(
            100,
            fundamental_strength
        )

        # ==================================================
        # NEWS SCORE
        # ==================================================

        if pre_news_risk:

            news_score = 20

        elif post_news_analysis:

            news_score = 70

        elif high_impact_news:

            news_score = 50

        else:

            news_score = 70

        # ==================================================
        # FUNDAMENTAL REGIME
        # ==================================================

        if pre_news_risk:

            fundamental_regime = (
                "PRE_NEWS"
            )

        elif (
            post_news_analysis
            and
            gold_bias == "BULLISH"
        ):

            fundamental_regime = (
                "POST_NEWS_BULLISH_GOLD"
            )

        elif (
            post_news_analysis
            and
            gold_bias == "BEARISH"
        ):

            fundamental_regime = (
                "POST_NEWS_BEARISH_GOLD"
            )

        elif (
            post_news_analysis
            and
            gold_bias == "NEUTRAL"
        ):

            fundamental_regime = (
                "POST_NEWS_MIXED"
            )

        elif high_impact_news:

            fundamental_regime = (
                "HIGH_IMPACT_UNKNOWN"
            )

        else:

            fundamental_regime = (
                "NO_MAJOR_NEWS"
            )

        # ==================================================
        # FUNDAMENTAL SCORE
        # ==================================================

        if high_impact_news:

            score = (
                fundamental_strength
                +
                news_score
            ) / 2

        else:

            score = 50

        # ==================================================
        # FINAL RESULT
        # ==================================================

        return {

            "available":
            available,

            # ------------------------------------------
            # MARKET CONTEXT
            # ------------------------------------------

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

            "risk_level":
            risk_level,

            # ------------------------------------------
            # FUNDAMENTAL REGIME
            # ------------------------------------------

            "fundamental_regime":
            fundamental_regime,

            "fundamental_strength":
            fundamental_strength,

            # ------------------------------------------
            # NEWS
            # ------------------------------------------

            "high_impact_news":
            high_impact_news,

            "news_state":
            news_state,

            "pre_news_risk":
            pre_news_risk,

            "post_news_analysis":
            post_news_analysis,

            "minutes_to_news":
            minutes_to_news,

            "event":
            event,

            "event_id":
            event_id,

            "news_time":
            news_time,

            "currency":
            currency,

            "impact":
            impact,

            "phase":
            phase,

            # ------------------------------------------
            # ECONOMIC DATA
            # ------------------------------------------

            "actual":
            actual,

            "forecast":
            forecast,

            "previous":
            previous,

            "forecast_difference":
            forecast_difference,

            "previous_difference":
            previous_difference,

            "forecast_surprise_pct":
            (
                round(
                    forecast_surprise_pct,
                    2
                )
                if forecast_surprise_pct is not None
                else None
            ),

            "previous_change_pct":
            (
                round(
                    previous_change_pct,
                    2
                )
                if previous_change_pct is not None
                else None
            ),

            # ------------------------------------------
            # SURPRISE
            # ------------------------------------------

            "surprise_direction":
            surprise_direction,

            "surprise_strength":
            surprise_strength,

            # ------------------------------------------
            # EVENT TYPE
            # ------------------------------------------

            "inflation_event":
            inflation_event,

            "employment_event":
            employment_event,

            "central_bank_event":
            central_bank_event,

            "growth_event":
            growth_event,

            # ------------------------------------------
            # BIAS
            # ------------------------------------------

            "usd_bias":
            usd_bias,

            "gold_bias":
            gold_bias,

            "fed_bias":
            fed_bias,

            # ------------------------------------------
            # SCORES
            # ------------------------------------------

            "fundamental_confidence":
            fundamental_confidence,

            "news_score":
            news_score,

            "score":
            round(
                score,
                2
            )
        }
