import json
import time

from openai import (
    AsyncOpenAI, APIConnectionError, APITimeoutError,
    AuthenticationError, PermissionDeniedError, RateLimitError,
)

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
        pattern,
        allowed_actions=("BUY", "SELL"),
    ) -> TraderDecision:

        started = time.monotonic()
        response = None

        def finish(status, reason, decision="NONE", confidence=0):
            usage = getattr(response, "usage", None)
            details = getattr(usage, "output_tokens_details", None)

            def tokens(source, name):
                value = getattr(source, name, None)
                return value if type(value) is int and value >= 0 else None

            result = TraderDecision(
                decision=decision, confidence=confidence, status=status,
                reason=reason, latency_ms=int((time.monotonic() - started) * 1000),
                input_tokens=tokens(usage, "input_tokens"),
                output_tokens=tokens(usage, "output_tokens"),
                reasoning_tokens=tokens(details, "reasoning_tokens"),
            )
            # No response text, exception body, credentials or account context.
            log = logger.warning if status in {"ERROR", "UNAVAILABLE"} else logger.info
            log(
                f"AITrader Decision={result.decision} Confidence={result.confidence} "
                f"Status={status} Reason={reason} LatencyMs={result.latency_ms} "
                f"OutputTokens={result.output_tokens} ReasoningTokens={result.reasoning_tokens}"
            )
            return result

        if self.client is None:
            return finish("UNAVAILABLE", "AI_NOT_CONFIGURED")

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
        allowed_actions = tuple(action for action in allowed_actions if action in {"BUY", "SELL"})
        if not allowed_actions:
            raise ValueError("AITrader requires at least one executable action")
        executable_actions = ", ".join(allowed_actions)

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
EXECUTABLE DIRECTIONS
==================================================

The deterministic risk rules permit new entries only for:

{executable_actions}

Do not choose any other direction. Choose NONE when the
permitted direction has no sufficiently strong edge.

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

            if response_status != "completed":
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
                reason = (
                    "AI_MAX_OUTPUT_TOKENS"
                    if response_status == "incomplete" and incomplete_reason == "max_output_tokens"
                    else "AI_RESPONSE_NOT_COMPLETED"
                )
                return finish("ERROR", reason)

            if any(
                getattr(part, "type", None) == "refusal"
                for item in (getattr(response, "output", None) or [])
                for part in (getattr(item, "content", None) or [])
            ):
                return finish("ERROR", "AI_REFUSAL")

            content = str(
                getattr(
                    response,
                    "output_text",
                    "",
                )
                or ""
            ).strip()

            if not content:
                return finish("ERROR", "AI_EMPTY_OUTPUT")

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

            if decision == "NONE":
                return finish("COMPLETED", "AI_NO_TRADE")
            if confidence < MIN_CONFIDENCE:
                return finish("FILTERED", "CONFIDENCE_BELOW_70")
            return finish("COMPLETED", "AI_DIRECTION_SELECTED", decision, confidence)

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            return finish("ERROR", "AI_INVALID_OUTPUT")
        except APITimeoutError:
            return finish("ERROR", "AI_TIMEOUT")
        except APIConnectionError:
            return finish("ERROR", "AI_CONNECTION_ERROR")
        except (AuthenticationError, PermissionDeniedError):
            return finish("ERROR", "AI_ACCESS_DENIED")
        except RateLimitError as exc:
            body = exc.body if isinstance(exc.body, dict) else {}
            error = body.get("error", body)
            error = error if isinstance(error, dict) else {}
            quota = error.get("code") in {"insufficient_quota", "credit_balance_exhausted"} or error.get("type") == "insufficient_quota"
            return finish("ERROR", "AI_QUOTA_EXHAUSTED" if quota else "AI_RATE_LIMITED")
        except Exception:
            return finish("ERROR", "AI_API_ERROR")
