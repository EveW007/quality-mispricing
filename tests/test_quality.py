import sys
from pathlib import Path

sys.path.append(
    str(Path(__file__).parent.parent / "src")
)

from quality import (
    calculate_quality_score,
    classify_quality_score,
)


def test_high_quality_company_scores_high():
    score = calculate_quality_score(
        revenue_growth=0.20,
        eps_growth=0.20,
        fcf_margin=0.30,
        debt_to_equity=0.20,
    )

    assert score == 100


def test_weak_company_scores_low():
    score = calculate_quality_score(
        revenue_growth=-0.05,
        eps_growth=-0.10,
        fcf_margin=0.02,
        debt_to_equity=3.0,
    )

    assert score == 0


def test_good_quality_classification():
    status = classify_quality_score(75)

    assert status == "GOOD"