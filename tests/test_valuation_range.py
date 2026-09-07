import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "src"))

from valuation import calculate_valuation, historical_pe_series


def test_historical_pe_and_scenario_range():
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B", tz="UTC")
    history = pd.DataFrame({"Close": 100.0}, index=dates)
    annual = [
        {"period_end": f"{year}-12-31", "diluted_eps": 5.0}
        for year in range(2021, 2026)
    ]
    observations = historical_pe_series(history, annual)
    result = calculate_valuation(
        current_price=80,
        trailing_eps=5,
        forward_eps=None,
        trailing_pe=16,
        forward_pe=None,
        free_cash_flow=10,
        market_cap=100,
        historical_pe=observations,
        revenue_growth=0.05,
    )
    assert result["historical_median_pe"] == 20
    assert result["value_range"]["base"] == 100
    assert result["base_margin_of_safety_pct"] == 0.25


def test_forward_eps_is_capped_when_it_conflicts_with_observed_growth():
    result = calculate_valuation(
        current_price=100,
        trailing_eps=10,
        forward_eps=20,
        trailing_pe=10,
        forward_pe=5,
        free_cash_flow=10,
        market_cap=100,
        historical_pe=[{"pe": 20}],
        revenue_growth=0.08,
        eps_growth=0.10,
    )
    assert result["value_range"]["eps_basis"] == 11
    assert result["value_range"]["eps_basis_type"] == "normalized forward cap"
    assert result["value_range"]["raw_forward_eps"] == 20
