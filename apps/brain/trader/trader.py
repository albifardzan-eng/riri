import json

from openai import AsyncOpenAI

from config.settings import settings
from config.trading_config import (
    MIN_CONFIDENCE,
    TP_POINTS,
    SL_POINTS
)

from models.trader_decision import TraderDecision
from utils.logger import logger


DECISION_TEXT_CONFIG = {
    "format": {
        "type": "json_schema",
        "name": "riri_trade_decision",
        "description": "RIRI's final XAUUSD trade direction and confidence.",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": ["BUY", "SELL", "NONE"],
                },
                "confidence": {
                    "type": "integer",
                },
            },
            "required": ["decision", "confidence"],
            "additionalProperties": False,
        },
    }
}


class AITrader:

    def __init__(self):

        self.client = (
            AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.OPENAI_TIMEOUT_SECONDS,
                max_retries=0,
            )
            if settings.OPENAI_API_KEY
            else None
        )

    def _serialize_data(
        self,
        value
    ) -> str:

        if value is None:
            return "null"

        if hasattr(
            value,
            "model_dump"
        ):
            value = value.model_dump()

        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
            indent=2
        )

    async def decide(
        self,
        market,
        statistics,
        fundamental,
        pattern
    ) -> TraderDecision:

        if self.client is None:
            return TraderDecision(
                decision="NONE",
                confidence=0
            )

        market_json = (
            self._serialize_data(
                market
            )
        )

        statistics_json = (
            self._serialize_data(
                statistics
            )
        )

        fundamental_json = (
            self._serialize_data(
                fundamental
            )
        )

        pattern_json = (
            self._serialize_data(
                pattern
            )
        )

        prompt = f"""
You are RIRI, an institutional XAUUSD short-term trading AI.

You are the PRIMARY directional decision maker.

The Scoring Engine is ONLY a qualification filter.
Do not follow its score blindly.

Your objective is to determine whether the current market
offers a credible opportunity to capture:

TP = {TP_POINTS} points
SL = {SL_POINTS} points

Analyze the supplied MARKET, STATISTICS, PATTERN and
FUNDAMENTAL data.

Do not invent information or use external information.

==================================================
LIVE MARKET DATA
==================================================

{market_json}

==================================================
LIVE STATISTICS
==================================================

{statistics_json}

==================================================
LIVE FUNDAMENTAL DATA
==================================================

{fundamental_json}

==================================================
LIVE PATTERN DATA
==================================================

{pattern_json}

==================================================
CORE ANALYSIS
==================================================

Evaluate both possible scenarios:

1. CONTINUATION
2. REVERSAL

Choose BUY, SELL or NONE based on the stronger setup.

Consider:

- market structure
- trend
- momentum
- candle sequence
- volatility
- support/resistance
- rejection
- breakout / failed breakout
- exhaustion
- continuation evidence
- reversal evidence
- target feasibility

Do not assume that a strong move must continue.
Do not assume that an extreme move must reverse.

==================================================
SNR
==================================================

Use only support/resistance evidence present in the
supplied market and candle data.

Look for:

- swing highs/lows
- repeated rejection
- reaction zones
- consolidation boundaries
- breakout / failed breakout
- support or resistance near current price

Do not invent price levels.

==================================================
FUNDAMENTAL
==================================================

Fundamental data is contextual evidence.

Use only the supplied FUNDAMENTAL section.

Evaluate:

- high-impact news
- event type
- event timing
- recent vs upcoming
- actual vs forecast
- previous
- size of economic surprise
- relevance to USD and gold

Do not automatically trade because news is bullish or
bearish.

Infer the fundamental implication from the supplied facts,
but do not invent missing information.

==================================================
FUNDAMENTAL SHOCK
==================================================

Treat a recent high-impact event with a meaningful surprise
as a potential fundamental shock.

After a shock:

- reassess the previous market structure
- do not assume continuation
- do not assume reversal
- evaluate candle expansion and momentum
- evaluate rejection and failed breakout/breakdown
- wait for confirmation

If price structure and fundamental evidence materially
conflict after a major event, prefer NONE.

==================================================
PRE-NEWS
==================================================

If a high-impact event is approaching:

be conservative.

Do not enter immediately before major news unless the
market setup is exceptionally clear and the target remains
realistically achievable.

When uncertain, choose NONE.

==================================================
FUNDAMENTAL + TECHNICAL
==================================================

Classify the relationship internally as:

ALIGNED
CONFLICTED
NEUTRAL
UNKNOWN

ALIGNED:
Increase confidence when technical structure also supports
the same direction.

CONFLICTED:
Reduce confidence significantly.

NEUTRAL / UNKNOWN:
Allow market structure and price behavior to dominate.

Fundamental information does not automatically override
strong technical evidence.

Technical evidence does not automatically override a major
fundamental shock.

The decision must come from the combined evidence.

==================================================
TARGET FEASIBILITY
==================================================

The target is fixed at {TP_POINTS} points.

Do not predict the entire daily move.

Evaluate whether the CURRENT structure provides a realistic
path toward the target.

Prefer setups with:

- clear directional pressure
- sufficient room to target
- favorable SNR location
- confirmation
- coherent fundamental/technical interaction

==================================================
DECISION
==================================================

BUY:
Credible bullish opportunity toward TP.

SELL:
Credible bearish opportunity toward TP.

NONE:
No sufficiently strong edge, unclear structure, conflicting
evidence, unstable post-news condition, poor SNR, or
insufficient target feasibility.

Do not force a trade.

The objective is quality, not trade frequency.

==================================================
CONFIDENCE
==================================================

Confidence = quality of the specific setup.

Use the full 0-100 range.

Higher confidence requires stronger evidence and clearer
target feasibility.

If decision = NONE, confidence MUST be 0.

==================================================
OUTPUT
==================================================

Return ONLY valid JSON:

{{
    "decision": "BUY",
    "confidence": 0
}}

Allowed decision values:

BUY
SELL
NONE

No explanation.
No markdown.
No additional fields.
Only JSON.
"""

        try:

            response = await self.client.responses.create(
                model=settings.OPENAI_MODEL,
                input=prompt,
                max_output_tokens=settings.OPENAI_MAX_OUTPUT_TOKENS,
                text=DECISION_TEXT_CONFIG,
                store=False,
            )

            response_status = getattr(
                response,
                "status",
                None,
            )

            if response_status not in (None, "completed"):
                incomplete_details = getattr(
                    response,
                    "incomplete_details",
                    None,
                )
                incomplete_reason = getattr(
                    incomplete_details,
                    "reason",
                    "unknown",
                )
                logger.warning(
                    "AITrader response not completed: "
                    f"status={response_status} "
                    f"reason={incomplete_reason}"
                )
                return TraderDecision(
                    decision="NONE",
                    confidence=0,
                )

            content = str(
                getattr(
                    response,
                    "output_text",
                    "",
                )
                or ""
            ).strip()

            if not content:
                logger.warning(
                    "AITrader returned no structured output; "
                    "decision defaults to NONE"
                )
                return TraderDecision(
                    decision="NONE",
                    confidence=0,
                )

            data = json.loads(
                content
            )

            if (
                not isinstance(data, dict)
                or set(data) != {"decision", "confidence"}
            ):
                raise ValueError(
                    "AI Trader response has unexpected fields"
                )

            decision = data["decision"]
            confidence = data["confidence"]

            if (
                not isinstance(decision, str)
                or decision not in (
                    "BUY",
                    "SELL",
                    "NONE"
                )
            ):
                raise ValueError(
                    "AI Trader response has invalid decision"
                )

            if (
                not isinstance(confidence, int)
                or isinstance(confidence, bool)
                or not 0 <= confidence <= 100
            ):
                raise ValueError(
                    "AI Trader response has invalid confidence"
                )

            if (
                decision == "NONE"
                or confidence < MIN_CONFIDENCE
            ):

                decision = "NONE"
                confidence = 0

            result = TraderDecision(
                decision=decision,
                confidence=confidence
            )

            logger.info(
                f"AITrader Decision="
                f"{result.decision} "
                f"Confidence="
                f"{result.confidence}"
            )

            return result

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as e:

            logger.warning(
                "AITrader rejected malformed structured output: "
                f"{type(e).__name__}"
            )

            return TraderDecision(
                decision="NONE",
                confidence=0
            )

        except Exception as e:

            logger.exception(f"AITrader failed: {type(e).__name__}")

            return TraderDecision(
                decision="NONE",
                confidence=0
            )
