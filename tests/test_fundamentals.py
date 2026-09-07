import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

import pandas as pd

from fundamentals import _annual_history_from_income, cross_validate_fundamentals


def test_annual_history_normalizes_statement_rows():
    statement = pd.DataFrame(
        {
            pd.Timestamp("2025-12-31"): [1000, 120, 6.0],
            pd.Timestamp("2024-12-31"): [900, 100, 5.0],
        },
        index=["Total Revenue", "Net Income", "Diluted EPS"],
    )
    result = _annual_history_from_income(statement)
    assert result == [
        {"period_end": "2024-12-31", "revenue": 900.0, "net_income": 100.0, "diluted_eps": 5.0},
        {"period_end": "2025-12-31", "revenue": 1000.0, "net_income": 120.0, "diluted_eps": 6.0},
    ]


def test_cross_validation_flags_one_percent_difference():
    secondary = {
        "annual": {
            "period_end": "2025-12-31",
            "revenue": 980,
            "net_income_period": "2025-12-31",
            "net_income": 100,
            "operating_cash_flow_period": "2025-12-31",
            "operating_cash_flow": 150,
        }
    }
    primary = {
        "annual": [
            {
                "period_end": "2025-12-31",
                "revenue": 1000,
                "net_income": 100,
                "operating_cash_flow": 150,
            }
        ]
    }
    result = cross_validate_fundamentals(secondary, primary)
    assert result["status"] == "REVIEW"
    assert "revenue differs" in result["warnings"][0]


def test_cross_validation_does_not_compare_different_periods():
    secondary = {"annual": {"period_end": "2024-12-31", "revenue": 900}}
    primary = {"annual": [{"period_end": "2025-12-31", "revenue": 1000}]}
    result = cross_validate_fundamentals(secondary, primary)
    assert result["checks"][0]["status"] == "PERIOD_MISMATCH"
