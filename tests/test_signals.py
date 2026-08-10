import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))
from signals import (
    get_signal,
    get_drawdown_action,
    get_uptrend_action,
)

sys.path.append(str(Path(__file__).parent.parent / "src"))

from signals import get_signal


def test_attractive_stock_below_target_should_add():
    signal = get_signal(
        current_weight=0.03,
        target_weight=0.05,
        max_weight=0.08,
        fundamental_status="stable",
        valuation_status="attractive",
    )

    assert signal == "ADD"


def test_deteriorating_fundamentals_should_review():
    signal = get_signal(
        current_weight=0.03,
        target_weight=0.05,
        max_weight=0.08,
        fundamental_status="deteriorating",
        valuation_status="attractive",
    )

    assert signal == "THESIS REVIEW"


def test_position_above_max_should_not_add():
    signal = get_signal(
        current_weight=0.09,
        target_weight=0.05,
        max_weight=0.08,
        fundamental_status="stable",
        valuation_status="attractive",
    )

    assert signal == "DO NOT ADD"

def test_left_stock_down_10_percent_can_add():
    action = get_drawdown_action(
        drawdown=-0.10,
        fundamental_status="stable",
        add_style="LEFT",
    )

    assert action == "ADD ALLOWED"


def test_left_stock_down_15_percent_requires_review():
    action = get_drawdown_action(
        drawdown=-0.15,
        fundamental_status="stable",
        add_style="LEFT",
    )

    assert action == "REVIEW THEN ADD"


def test_deteriorating_stock_should_not_average_down():
    action = get_drawdown_action(
        drawdown=-0.20,
        fundamental_status="deteriorating",
        add_style="LEFT",
    )

    assert action == "THESIS REVIEW"


def test_right_side_add_when_value_rises_with_price():
    action = get_uptrend_action(
        price_change=0.10,
        intrinsic_value_change=0.08,
        fundamental_status="stable",
        add_style="HYBRID",
    )

    assert action == "ADD ALLOWED"


def test_do_not_chase_when_price_runs_far_ahead():
    action = get_uptrend_action(
        price_change=0.30,
        intrinsic_value_change=0.05,
        fundamental_status="stable",
        add_style="HYBRID",
    )

    assert action == "DO NOT CHASE"