import sys
from pathlib import Path

sys.path.append(
    str(Path(__file__).parent.parent / "src")
)

from scoring import (
    calculate_mispricing_score,
    classify_mispricing_score,
)


def test_high_quality_mispricing_scores_high():
    score = calculate_mispricing_score(
        drawdown=-0.35,
        pe_discount=-0.40,
        fundamental_status="stable",
        valuation_status="attractive",
    )

    assert score >= 80


def test_deteriorating_company_should_score_lower():
    score = calculate_mispricing_score(
        drawdown=-0.40,
        pe_discount=-0.40,
        fundamental_status="deteriorating",
        valuation_status="attractive",
    )

    assert score < 80


def test_high_priority_classification():
    label = classify_mispricing_score(90)

    assert label == "HIGH PRIORITY"