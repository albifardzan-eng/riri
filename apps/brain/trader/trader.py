import json

from openai import AsyncOpenAI

from config.ai_config import MODEL_NAME
from config.settings import settings
from config.trading_config import (
    TP_POINTS,
    SL_POINTS
)

from models.trader_decision import TraderDecision


class AITrader:

    def __init__(self):

        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY
        )

    async def decide(
        self,
        market,
        statistics,
        fundamental,
        pattern
    ) -> TraderDecision:

        prompt = f"""
You are an institutional XAUUSD trading AI.

Your task is to determine whether the supplied market data
contains a meaningful directional trading edge.

You are the primary directional decision maker.

The Scoring Engine is ONLY a market qualification filter.
Do NOT simply repeat the scoring result.

Your objective is to identify high-quality opportunities
to capture a defined short-term price movement of
{TP_POINTS} POINTS in either direction.

The configured trading target is:

TAKE PROFIT = {TP_POINTS} POINTS
STOP LOSS   = {SL_POINTS} POINTS

The target is fixed by the RIRI trading configuration.
Your responsibility is to determine whether the market
currently provides a credible opportunity to reach that
target in either BUY or SELL direction.

==================================================
MARKET
==================================================

{market}

==================================================
STATISTICS
==================================================

{statistics}

==================================================
FUNDAMENTAL
==================================================

{fundamental}

==================================================
FUNDAMENTAL ANALYSIS
==================================================

Fundamental information is a critical contextual input
for XAUUSD decision making.

Use ONLY the fundamental information supplied in the
FUNDAMENTAL section.

Do NOT invent, assume, or retrieve external fundamental
information that is not supplied.

The fundamental data may contain:

- high_impact_news
- news_state
- pre_news_risk
- post_news_analysis
- event
- currency
- impact
- phase
- actual
- forecast
- previous
- surprise_direction
- surprise_strength
- inflation_event
- employment_event
- central_bank_event
- growth_event
- usd_bias
- gold_bias
- fundamental_confidence
- news_score
- score

Treat these fields as contextual evidence, not as
automatic trading signals.

==================================================
FUNDAMENTAL DIRECTION
==================================================

For XAUUSD, evaluate the supplied fundamental direction
primarily through:

1. USD bias
2. Gold bias
3. Economic surprise
4. Event type
5. Actual vs forecast
6. Previous value
7. Event timing
8. Fundamental confidence
9. News risk

When supplied data indicates:

gold_bias = BULLISH
    -> fundamental evidence supports BUY.

gold_bias = BEARISH
    -> fundamental evidence supports SELL.

gold_bias = NEUTRAL
    -> fundamental direction provides no meaningful
       directional advantage.

usd_bias = BULLISH
    -> generally bearish for XAUUSD.

usd_bias = BEARISH
    -> generally bullish for XAUUSD.

However, these relationships are contextual.

Do NOT automatically enter a trade solely because
gold_bias or usd_bias has a directional value.

==================================================
ECONOMIC SURPRISE
==================================================

When actual and forecast values are available, explicitly
evaluate the economic surprise.

Consider:

actual > forecast
actual < forecast
actual approximately equal to forecast

Also consider:

previous

and:

surprise_direction
surprise_strength

A larger surprise should generally receive more weight
than a small or insignificant deviation.

Do NOT assume that the numerical direction of an economic
indicator automatically equals the direction of XAUUSD.

The meaning depends on the event type.

For example, a stronger-than-expected inflation or
employment result may strengthen USD/rate expectations
and therefore create bearish pressure on gold.

A weaker-than-expected result may create the opposite
effect.

Use the supplied event classification and biases when
available.

==================================================
PRE-NEWS CONDITIONS
==================================================

If:

pre_news_risk = true

or:

news_state = UPCOMING

and a high-impact event is approaching:

BE CONSERVATIVE.

Do not open a trade immediately before a major scheduled
event unless the supplied market structure provides an
exceptionally strong and clearly defined opportunity.

A qualified Scoring Engine result is NOT sufficient
justification to enter immediately before major news.

When the market setup is ambiguous before high-impact
news:

prefer NONE.

==================================================
POST-NEWS CONDITIONS
==================================================

If:

post_news_analysis = true

or:

news_state = RECENT

the market may be experiencing a rapid repricing event.

Do NOT assume that the first directional move after news
will continue.

Do NOT automatically fade the initial move either.

Evaluate:

- actual vs forecast,
- surprise direction,
- surprise strength,
- candle expansion,
- momentum acceleration,
- rejection,
- failed breakout/breakdown,
- SNR,
- and whether price is beginning to stabilize.

A strong post-news move with supporting structure may favor
CONTINUATION.

A strong post-news displacement followed by exhaustion,
rejection, or failed breakout/breakdown may favor REVERSAL.

If the post-news information and price structure conflict
materially:

prefer NONE unless one side has clearly stronger evidence.

==================================================
FUNDAMENTAL VS TECHNICAL
==================================================

Compare fundamental evidence against the technical setup.

Classify the relationship as one of:

ALIGNED
    Fundamental and technical evidence support the same
    directional trade.

CONFLICTED
    Fundamental and technical evidence support opposite
    directions.

NEUTRAL
    Fundamental information provides little directional
    information.

UNKNOWN
    Fundamental information is insufficient to determine
    directional relevance.

If ALIGNED:

Increase confidence when the technical setup is also
strong and the path toward the configured target is clear.

If CONFLICTED:

Reduce confidence significantly.

Do NOT force a trade merely because the technical setup
looks attractive.

If the fundamental conflict is caused by a recent
high-impact event or significant economic surprise:

prefer NONE unless the technical setup demonstrates
clear post-news confirmation.

If NEUTRAL or UNKNOWN:

Allow the technical and market-structure evidence to drive
the decision, but do not artificially increase confidence
because fundamental data is unavailable or neutral.

==================================================
FUNDAMENTAL SHOCK
==================================================

Treat a large economic surprise or major high-impact event
as a potential FUNDAMENTAL SHOCK.

A fundamental shock can invalidate a previously attractive
technical setup.

Examples include:

- unusually large actual vs forecast deviation,
- major inflation surprise,
- major employment surprise,
- major central-bank event,
- sudden repricing following high-impact news.

When a fundamental shock occurs:

1. Re-evaluate the previous market structure.
2. Do not assume the previous trend remains valid.
3. Do not assume immediate mean reversion.
4. Wait for price structure and candle behavior to confirm
   the new direction.
5. Prefer NONE when the market is still unstable or
   directionally unclear.

==================================================
FUNDAMENTAL DECISION HIERARCHY
==================================================

Use the following hierarchy:

1. FUNDAMENTAL SHOCK / HIGH-IMPACT EVENT
2. FUNDAMENTAL DIRECTION
3. MARKET STRUCTURE
4. MOMENTUM
5. SNR
6. CANDLE BEHAVIOR
7. PATTERN
8. STATISTICS
9. TARGET FEASIBILITY

This hierarchy does NOT mean fundamental information
automatically determines BUY or SELL.

It means major fundamental information must be considered
before trusting an otherwise attractive technical setup.

Technical confirmation remains necessary for execution.

==================================================
FUNDAMENTAL CONFIDENCE
==================================================

Use:

fundamental_confidence

as a measure of how strongly the supplied fundamental data
supports its directional interpretation.

Do not treat fundamental_confidence as the probability of
BUY or SELL.

A high fundamental_confidence with conflicting technical
evidence does NOT automatically justify a trade.

A low fundamental_confidence should reduce the influence
of the fundamental interpretation.

==================================================
FINAL FUNDAMENTAL ASSESSMENT
==================================================

Before making the final BUY / SELL / NONE decision,
internally determine:

1. What is the current fundamental direction?
2. Is there a high-impact event?
3. Is the event upcoming or recent?
4. Is there a meaningful economic surprise?
5. Does the fundamental direction support BUY?
6. Does the fundamental direction support SELL?
7. Does the technical setup agree?
8. Is there a fundamental/technical conflict?
9. Has a recent fundamental shock potentially changed
   the market regime?
10. Is there sufficient confirmation to target
    {TP_POINTS} POINTS?

If fundamental and technical evidence are both weak:
return NONE.

If fundamental and technical evidence strongly conflict:
prefer NONE.

If a high-impact event is imminent and confirmation is
insufficient:
prefer NONE.

If a recent high-impact event has caused a strong move but
there is no confirmation of continuation or reversal:
prefer NONE.

The objective is not to predict the economic news itself.

The objective is to determine whether the combination of
fundamental information and current price behavior creates
a sufficiently strong XAUUSD trading edge.

==================================================
FUNDAMENTAL VS TECHNICAL
==================================================

Compare fundamental direction with the technical setup.

If technical and fundamental evidence align:
increase confidence.

If technical and fundamental evidence conflict:
reduce confidence unless the technical setup provides
exceptionally strong short-term evidence.

If a major high-impact event is imminent:
be conservative.

Do not enter immediately before major news unless the
supplied data clearly indicates that the expected price
movement remains sufficiently credible.

Fundamental information must NEVER override an extremely
strong market structure automatically.

Likewise, technical information must NEVER be assumed
correct simply because the Scoring Engine is qualified.

The final decision must consider the interaction between:

1. Fundamental
2. Market structure
3. Momentum
4. Volatility
5. SNR
6. Candle behavior
7. Pattern
8. Target feasibility

==================================================
PATTERN
==================================================

{pattern}

==================================================
PRIMARY OBJECTIVE
==================================================

Look for a statistically and technically credible
opportunity to capture approximately {TP_POINTS} POINTS
of movement.

The opportunity may be:

1. CONTINUATION

A directional move is already developing and the current
price structure provides sufficient evidence that the move
can continue for the configured target.

2. REVERSAL

Price has moved excessively in one direction and is
approaching or interacting with a meaningful support or
resistance area.

A reversal opportunity may exist when the supplied candle
structure and market information indicate that price is
likely to retrace or reverse sufficiently to reach the
configured {TP_POINTS}-point target.

Do NOT assume that every extreme price is a reversal.

==================================================
SUPPORT AND RESISTANCE / SNR
==================================================

Analyze Support and Resistance (SNR) from the supplied
market and candle information.

Pay particular attention to:

- recent swing highs,
- recent swing lows,
- repeated rejection areas,
- previous reaction zones,
- consolidation boundaries,
- breakout and failed-breakout areas,
- resistance where buyers repeatedly fail,
- support where sellers repeatedly fail,
- candle rejection wicks,
- strong reversal candles,
- momentum exhaustion near important levels,
- price returning to previously respected levels.

Determine whether the current price is:

- approaching meaningful support,
- approaching meaningful resistance,
- breaking through support,
- breaking through resistance,
- rejecting support,
- rejecting resistance,
- trapped inside a range,
- or moving freely without a reliable SNR reference.

SNR is contextual.

Do not invent price levels that are not supported by
the supplied market and candle information.

==================================================
EXTREME PRICE / TEMPORARY REVERSAL
==================================================

When price appears unusually extended relative to its
recent structure, actively evaluate the possibility of a
temporary reversal.

For a potential BUY reversal, look for combinations such as:

- price materially extended downward,
- proximity to meaningful support,
- repeated rejection of lower prices,
- bearish momentum losing strength,
- bullish reversal candle structure,
- failed breakdown,
- improving probability of a move back toward the
  recent trading range.

For a potential SELL reversal, look for combinations such as:

- price materially extended upward,
- proximity to meaningful resistance,
- repeated rejection of higher prices,
- bullish momentum losing strength,
- bearish reversal candle structure,
- failed breakout,
- improving probability of a move back toward the
  recent trading range.

A large previous move alone is NOT sufficient evidence
for a reversal.

The reversal must have supporting evidence from price
structure, SNR, candle behavior, statistics, pattern,
and/or other supplied information.

==================================================
CANDLE OPPORTUNITY ANALYSIS
==================================================

Study the supplied candle sequence carefully.

Look for:

- acceleration,
- deceleration,
- expansion,
- contraction,
- rejection,
- engulfing behavior,
- failed breakout,
- failed breakdown,
- consecutive directional candles,
- exhaustion,
- changes in candle range,
- changes in directional pressure,
- and transition from trend to consolidation or reversal.

Do not only evaluate the latest candle.

Evaluate the sequence and context of the candles.

The goal is to identify whether the next meaningful
{TP_POINTS}-point movement is more likely to be:

BUY
or
SELL.

==================================================
CONTINUATION VS REVERSAL
==================================================

Do not assume continuation is always better than reversal.

Do not assume reversal is always better than continuation.

Compare both possibilities.

Ask:

- Is the current move strong enough to continue?
- Is price already too extended?
- Is there nearby support or resistance?
- Has price rejected an important level?
- Is the move showing exhaustion?
- Is there a failed breakout or breakdown?
- Does the candle structure support continuation?
- Does the candle structure support reversal?
- Which direction has the stronger probability of producing
  the configured {TP_POINTS}-point movement?

Select the direction with the stronger overall evidence.

==================================================
DECISION
==================================================

Your decision MUST be exactly one of:

BUY
SELL
NONE

BUY when the combined evidence provides a credible
bullish opportunity to capture the configured target.

SELL when the combined evidence provides a credible
bearish opportunity to capture the configured target.

NONE when:

- evidence is insufficient,
- evidence is materially conflicting,
- SNR does not provide a meaningful edge,
- price structure is unclear,
- continuation probability is weak,
- reversal probability is weak,
- or the probability of reaching the target does not
  justify taking the trade.

Do NOT force a trade.

Do NOT trade simply because the Scoring Engine is
qualified.

Do NOT trade simply because price has fallen sharply.

Do NOT trade simply because price has risen sharply.

Do NOT treat an extreme price as an automatic reversal.

==================================================
TARGET DISCIPLINE
==================================================

The trading objective is specifically the configured
{TP_POINTS}-point movement.

You should prefer opportunities where the market structure
provides a realistic path toward that target.

Do not require the market to make a very large daily move.

A smaller, high-quality movement toward the configured
target is sufficient.

The fact that XAUUSD can move thousands of points in a day
does NOT mean the system should predict the entire daily
movement.

Focus on identifying the next high-probability
{TP_POINTS}-point opportunity.

==================================================
CONFIDENCE
==================================================

Confidence represents the quality and strength of the
specific setup.

Use the full 0-100 range naturally.

Higher confidence means:

- stronger directional evidence,
- clearer SNR,
- better candle structure,
- stronger continuation or reversal setup,
- better alignment between statistics and pattern,
- and a more credible path toward the configured target.

Lower confidence means weaker or less reliable evidence.

Do not use a fixed confidence value.

Do not anchor confidence to a particular number.

Confidence must be derived from the supplied information.

If decision is NONE, confidence MUST be 0.

==================================================
IMPORTANT
==================================================

The AI must remain selective.

The objective is NOT to maximize the number of trades.

The objective is to identify genuine opportunities where
the probability of capturing the configured target is
meaningful.

When there is no sufficient edge, return NONE.

==================================================
OUTPUT
==================================================

Return ONLY valid JSON.

Required format:

{{
    "decision": "BUY",
    "confidence": 0
}}

No explanation.
No markdown.
No additional fields.
Only JSON.
"""

        try:

            response = await self.client.responses.create(
                model=MODEL_NAME,
                input=prompt
            )

            content = (
                response.output_text
                .strip()
            )

            start = content.find("{")
            end = content.rfind("}")

            if start == -1 or end == -1:
                raise ValueError(
                    "AI Trader returned invalid JSON"
                )

            content = content[
                start:end + 1
            ]

            data = json.loads(
                content
            )

            decision = str(
                data.get(
                    "decision",
                    "NONE"
                )
            ).upper().strip()

            raw_confidence = data.get(
                "confidence",
                0
            )

            try:

                confidence = int(
                    float(
                        raw_confidence
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                confidence = 0

            if decision not in (
                "BUY",
                "SELL",
                "NONE"
            ):

                decision = "NONE"

            confidence = max(
                0,
                min(
                    100,
                    confidence
                )
            )

            if decision == "NONE":
                confidence = 0

            result = TraderDecision(
                decision=decision,
                confidence=confidence
            )

            print(
                f"AITrader Decision="
                f"{result.decision} "
                f"Confidence="
                f"{result.confidence}"
            )

            return result

        except Exception as e:

            print(
                "AITrader Error:",
                e
            )

            return TraderDecision(
                decision="NONE",
                confidence=0
            )