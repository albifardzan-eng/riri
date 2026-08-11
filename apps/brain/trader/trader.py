import json

from openai import AsyncOpenAI

from config.ai_config import MODEL_NAME
from config.settings import settings

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

You are NOT allowed to guess.

Your job is ONLY to evaluate whether a trade has a statistical edge.

Use ALL supplied information.

====================================================

SCORING ENGINE

====================================================

{market}

====================================================

STATISTICS

====================================================

{statistics}

====================================================

FUNDAMENTAL

====================================================

{fundamental}

====================================================

PATTERN

====================================================

{pattern}

====================================================

RULES

====================================================

Decision MUST be one of:

BUY
SELL
NONE

BUY only if:

- Trend agrees
- Statistics agree
- Pattern probability supports BUY
- Fundamental does not contradict BUY

SELL only if:

- Trend agrees
- Statistics agree
- Pattern probability supports SELL
- Fundamental does not contradict SELL

Return NONE whenever evidence is weak or conflicting.

Never force a trade.

====================================================

CONFIDENCE

====================================================

Confidence must represent quality of setup.

0-59
Poor setup

60-69
Weak setup

70-79
Average setup

80-89
Strong setup

90-100
Exceptional setup

Never randomly choose confidence.

Confidence must match evidence.

====================================================

Return ONLY valid JSON.

{{
    "decision":"BUY",
    "confidence":84
}}

No explanation.
No markdown.
No text.
Only JSON.
"""

        try:

            response = await self.client.responses.create(
                model=MODEL_NAME,
                input=prompt,
            )

            content = response.output_text.strip()

            start = content.find("{")
            end = content.rfind("}")

            if start == -1 or end == -1:
                raise ValueError("Invalid JSON")

            content = content[start:end + 1]

            data = json.loads(content)

            decision = str(
                data.get(
                    "decision",
                    "NONE"
                )
            ).upper()

            confidence = int(
                data.get(
                    "confidence",
                    0
                )
            )

            if decision not in (
                "BUY",
                "SELL",
                "NONE"
            ):
                decision = "NONE"

            confidence = max(
                0,
                min(
                    confidence,
                    100
                )
            )

            if decision == "NONE":
                confidence = 0

            return TraderDecision(
                decision=decision,
                confidence=confidence
            )

        except Exception as e:

            print(
                "AITrader Error:",
                e
            )

            return TraderDecision(
                decision="NONE",
                confidence=0
            )