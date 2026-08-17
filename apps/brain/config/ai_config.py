# ==================================================
# RIRI AI CONFIGURATION
# ==================================================

# OpenAI model used by AI Trader.
MODEL_NAME = "gpt-5-mini"


# Maximum output tokens allowed for a single
# AI Trader decision.
MAX_TOKENS = 200


# ==================================================
# AI DECISION THRESHOLDS
# ==================================================

# Minimum confidence required for BUY / SELL.
#
# This is intentionally separate from MIN_SCORE.
#
# MIN_SCORE:
#   Market is good enough to ask AI Trader.
#
# MIN_CONFIDENCE:
#   AI Trader is confident enough to propose a trade.
#
MIN_CONFIDENCE = 70


# ==================================================
# REVERSAL DECISION
# ==================================================

# Reversal trades require stronger confidence than
# normal trend-following trades because they attempt
# to trade against the immediate price expansion.
#
# This is a second-stage filter.
MIN_REVERSAL_CONFIDENCE = 75


# Minimum reversal strength from the market
# intelligence layer before AI Trader may select
# the REVERSAL strategy.
MIN_REVERSAL_STRENGTH = 65


# ==================================================
# AI BEHAVIOR
# ==================================================

# AI Trader must return exactly one directional
# decision:
#
# BUY
# SELL
# NONE
#
# Strategy is represented separately:
#
# TREND
# REVERSAL
# NONE
#
# The execution layer must never receive
# BUY_REVERSAL or SELL_REVERSAL as an action.
ALLOWED_DECISIONS = (
    "BUY",
    "SELL",
    "NONE",
)

ALLOWED_STRATEGIES = (
    "TREND",
    "REVERSAL",
    "NONE",
)