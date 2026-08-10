# ADD / HOLD / DO NOT ADD / THESIS REVIEW
# 决策函数

import portfolio


def get_signal(
    current_weight,
    target_weight,
    max_weight,
    fundamental_status,
    valuation_status,
):
    if fundamental_status == "deteriorating":
        return "THESIS REVIEW"

    if current_weight >= max_weight:
        return "DO NOT ADD"

    if current_weight >= target_weight:
        return "HOLD"

    if valuation_status == "attractive":
        return "ADD"

    if valuation_status == "fair":
        return "ADD ALLOWED"

    if valuation_status == "expensive":
        return "HOLD"

    return "REVIEW"

signals = []


def get_drawdown_action(
    drawdown,
    fundamental_status,
    add_style,
):
    if fundamental_status == "deteriorating":
        return "THESIS REVIEW"

    if add_style == "RIGHT":
        return "WAIT FOR CONFIRMATION"

    if drawdown <= -0.20:
        return "FULL FUNDAMENTAL REVIEW"

    if drawdown <= -0.15:
        return "REVIEW THEN ADD"

    if drawdown <= -0.10:
        return "ADD ALLOWED"

    if drawdown <= -0.05:
        return "ALERT"

    return "NO ACTION"

def get_uptrend_action(
    price_change,
    intrinsic_value_change,
    fundamental_status,
    add_style,
):
    if fundamental_status == "deteriorating":
        return "THESIS REVIEW"

    if add_style == "LEFT":
        return "NO RIGHT-SIDE ADD"

    if price_change <= 0:
        return "NO UPTREND"

    valuation_gap = price_change - intrinsic_value_change

    if valuation_gap <= 0.05:
        return "ADD ALLOWED"

    if valuation_gap <= 0.15:
        return "HOLD"

    return "DO NOT CHASE"