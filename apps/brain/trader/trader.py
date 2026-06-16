import json

from openai import AsyncOpenAI

from config.settings import settings
from config.ai_config import MODEL_NAME

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
You are an XAUUSD trading AI.

Analyze the supplied data.

Return JSON only.

Allowed decisions:

BUY
SELL
NONE

Market:
{market}

Statistics:
{statistics}

Fundamental:
{fundamental}

Pattern:
{pattern}

Required JSON format:

{{
    "decision":"BUY",
    "confidence":80
}}
"""

        try:

            response = await self.client.responses.create(
                model=MODEL_NAME,
                input=prompt
            )

            content = response.output_text

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

            if decision not in [
                "BUY",
                "SELL",
                "NONE"
            ]:
                decision = "NONE"

            confidence = max(
                0,
                min(
                    100,
                    confidence
                )
            )

            return TraderDecision(
                decision=decision,
                confidence=confidence
            )

        except Exception:

            return TraderDecision(
                decision="NONE",
                confidence=0
            )