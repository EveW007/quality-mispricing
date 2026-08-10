import sys
from pathlib import Path

sys.path.append(
    str(Path(__file__).parent.parent / "src")
)

from historical_valuation import compare_to_historical_pe


def test_deep_discount():
    status = compare_to_historical_pe(
        current_pe=14,
        historical_median_pe=20,
    )

    assert status == "deep discount"


def test_normal_valuation():
    status = compare_to_historical_pe(
        current_pe=20,
        historical_median_pe=20,
    )

    assert status == "normal"


def test_high_premium():
    status = compare_to_historical_pe(
        current_pe=30,
        historical_median_pe=20,
    )

    assert status == "high premium"