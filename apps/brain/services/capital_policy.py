"""AI chooses protection; deterministic limits decide whether it is affordable.

No empirical probability calibration is claimed by these defaults.
"""
from decimal import Decimal, ROUND_FLOOR
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from config.settings import settings


class ProtectionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    tp_points: int = Field(gt=0, le=100000)
    sl_points: int = Field(gt=0, le=100000)
    trailing_start_points: int = Field(gt=0, le=100000)
    trailing_distance_points: int = Field(gt=0, le=100000)
    trailing_step_points: int = Field(gt=0, le=100000)
    review_move_points: int = Field(gt=0, le=100000)
    thesis: str = Field(min_length=1, max_length=240)


def validate_plan(market, raw):
    try:
        plan = ProtectionPlan.model_validate(raw)
    except (ValidationError, TypeError):
        raise ValueError("AI_PROTECTION_PLAN_INVALID") from None
    cost = settings.CAPITAL_COST_BUFFER_POINTS
    # Spread and costs must fit within a sensible structural stop, not force
    # an artificially tight stop merely to make the broker's minimum lot fit.
    floor = max(market.stops_level_points + market.spread + 1,
                market.atr / market.point * .5, market.spread * 3, cost)
    if min(plan.sl_points, plan.tp_points) < floor:
        raise ValueError("AI_STOP_TOO_TIGHT")
    if (plan.tp_points - cost) / (plan.sl_points + cost) < settings.CAPITAL_MIN_REWARD_RISK:
        raise ValueError("AI_REWARD_RISK_TOO_LOW")
    if not cost < plan.trailing_start_points < plan.tp_points:
        raise ValueError("AI_TRAILING_START_INVALID")
    if not 0 < plan.trailing_step_points <= plan.trailing_distance_points < plan.trailing_start_points:
        raise ValueError("AI_TRAILING_DISTANCE_INVALID")
    if plan.trailing_distance_points <= market.stops_level_points + market.spread:
        raise ValueError("AI_TRAILING_BROKER_DISTANCE")
    return plan


def risk_lot(market, plan):
    if min(market.volume_min, market.volume_max, market.volume_step,
           market.tick_value, market.tick_size, market.equity) <= 0:
        raise ValueError("BROKER_SIZING_UNAVAILABLE")
    budget = market.equity * settings.CAPITAL_RISK_PERCENT / 100
    per_lot = (plan.sl_points + settings.CAPITAL_COST_BUFFER_POINTS) * market.point / market.tick_size * market.tick_value
    raw = min(budget / per_lot, market.volume_max, .50)
    step = Decimal(str(market.volume_step))
    lot = float((Decimal(str(raw)) / step).to_integral_value(rounding=ROUND_FLOOR) * step)
    if lot < market.volume_min or lot * per_lot > budget + 1e-8:
        raise ValueError("MINIMUM_LOT_EXCEEDS_RISK_BUDGET")
    return lot
