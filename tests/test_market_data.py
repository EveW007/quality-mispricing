import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent / "src"))

from market_data import analyze_price_history, calculate_return, rank_market_scan


def test_calculate_return():
    prices = pd.Series([
        100,
        102,
        104,
        106,
        110,
        120,
    ])

    result = calculate_return(prices, 5)

    assert result == pytest.approx(0.20)


def test_not_enough_data_returns_none():
    prices = pd.Series([
        100,
        105,
    ])

    result = calculate_return(prices, 5)

    assert result is None


def test_analyze_price_history_calculates_trend_and_relative_strength():
    dates = pd.date_range("2025-01-01", periods=260, tz="UTC")
    stock = pd.DataFrame(
        {"Close": range(100, 360), "High": range(101, 361)}, index=dates
    )
    benchmark = pd.DataFrame(
        {"Close": range(100, 360), "High": range(101, 361)}, index=dates
    )
    result = analyze_price_history("TEST", stock, benchmark)
    assert result["trend"] == "UPTREND"
    assert result["drawdown_from_high"] < 0
    assert result["relative_return_3m"] == pytest.approx(0)


def test_relative_strength_aligns_same_trade_date_with_different_utc_times():
    dates_stock = pd.date_range("2025-01-01", periods=260, tz="UTC")
    dates_benchmark = dates_stock + pd.Timedelta(hours=4)
    stock = pd.DataFrame(
        {"Close": range(100, 360), "High": range(101, 361)}, index=dates_stock
    )
    benchmark = pd.DataFrame(
        {"Close": range(100, 360), "High": range(101, 361)}, index=dates_benchmark
    )
    result = analyze_price_history("TEST", stock, benchmark)
    assert result["relative_return_3m"] == pytest.approx(0)


def test_market_scan_filters_liquidity_and_ranks_dislocations():
    packages = {
        "AAA": {
            "current_price": 100,
            "drawdown_from_high": -0.30,
            "relative_return_3m": -0.10,
            "distance_to_sma_200": -0.10,
            "return_1m": 0.03,
            "average_dollar_volume_20d": 50_000_000,
            "trend": "MIXED",
        },
        "ILLIQUID": {
            "current_price": 100,
            "drawdown_from_high": -0.50,
            "average_dollar_volume_20d": 1_000,
        },
    }
    result = rank_market_scan(packages, 20_000_000, 10)
    assert [item["ticker"] for item in result] == ["AAA"]
    assert result[0]["screen_score"] > 0
