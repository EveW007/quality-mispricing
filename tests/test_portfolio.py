import sys
from pathlib import Path
import pytest

import pandas as pd

sys.path.append(
    str(Path(__file__).parent.parent / "src")
)

from portfolio import (
    analyze_index_enhancement,
    calculate_position_metrics,
    load_portfolio,
    position_alert,
)


def test_calculate_position_metrics():
    portfolio = pd.DataFrame(
        {
            "ticker": ["TEST"],
            "shares": [10],
            "average_cost": [100],
            "current_price": [120],
        }
    )

    result = calculate_position_metrics(
        portfolio=portfolio,
        total_account_value=10000,
    )

    assert result.iloc[0]["market_value"] == 1200
    assert result.iloc[0]["cost_basis"] == 1000
    assert result.iloc[0]["profit_loss"] == 200
    assert result.iloc[0]["return_pct"] == pytest.approx(0.20)
    assert result.iloc[0]["portfolio_weight"] == 0.12


def test_account_value_can_be_calculated_from_positions_and_cash():
    portfolio = pd.DataFrame(
        {"ticker": ["TEST"], "shares": [10], "average_cost": [100], "current_price": [120]}
    )
    result = calculate_position_metrics(portfolio, cash_balance=800)
    assert result.iloc[0]["portfolio_weight"] == pytest.approx(0.60)


def test_position_alert_prioritizes_position_limit():
    row = pd.Series({"above_max_weight": True, "drawdown_from_high": -0.25})
    assert position_alert(row) == "POSITION_LIMIT_REVIEW"


def test_load_portfolio_rejects_duplicate_tickers(tmp_path):
    path = tmp_path / "portfolio.csv"
    path.write_text("ticker,shares,average_cost\nMSFT,1,100\nMSFT,2,100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_portfolio(path)


def test_load_portfolio_allows_unknown_cost(tmp_path):
    path = tmp_path / "portfolio.csv"
    path.write_text("ticker,shares,average_cost\nMSFT,1,\n", encoding="utf-8")
    result = load_portfolio(path)
    assert pd.isna(result.iloc[0]["average_cost"])


def test_index_enhancement_measures_active_sleeve_and_tracking_error():
    dates = pd.date_range("2025-01-01", periods=260, tz="UTC")
    spy = pd.DataFrame({"Close": [100 * (1.001**day) for day in range(260)]}, index=dates)
    stock = pd.DataFrame({"Close": [100 * (1.002**day) for day in range(260)]}, index=dates)
    portfolio = pd.DataFrame(
        {
            "ticker": ["SPY", "AAA"],
            "portfolio_weight": [0.4, 0.2],
        }
    )
    result = analyze_index_enhancement(
        portfolio, {"SPY": spy, "AAA": stock}, "SPY"
    )
    assert result["status"] == "OK"
    assert result["core_index_weight"] == pytest.approx(0.4)
    assert result["active_sleeve_weight"] == pytest.approx(0.2)
    assert result["cash_or_unallocated_weight"] == pytest.approx(0.4)
    assert result["tracking_error"] >= 0
    assert result["active_return_12m"] is not None
