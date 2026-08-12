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