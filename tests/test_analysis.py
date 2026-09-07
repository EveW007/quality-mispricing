import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "src"))

from analysis import analyze_company


def _history():
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B", tz="UTC")
    return pd.DataFrame({"Close": 100.0}, index=dates)


def _package(with_sec=True):
    return {
        "metrics": {
            "revenue_growth": 0.12,
            "eps_growth": 0.14,
            "fcf_margin": 0.25,
            "debt_to_equity": 0.4,
            "free_cash_flow": 20,
            "operating_margin": 0.25,
            "trailing_eps": 5,
            "forward_eps": 6,
            "trailing_pe": 16,
            "forward_pe": 14,
            "market_cap": 100,
            "currency": "USD",
        },
        "sec": (
            {"annual": [{"period_end": "2025-12-31", "diluted_eps": 5}]}
            if with_sec
            else None
        ),
        "validation": {"status": "VERIFIED" if with_sec else "UNVERIFIED", "warnings": []},
        "sources": (
            [
                {"tier": "primary", "url": "https://sec.gov/test"},
                {"tier": "independent", "url": "https://finance.yahoo.com/test"},
            ]
            if with_sec
            else [{"tier": "independent", "url": "https://finance.yahoo.com/test"}]
        ),
    }


def test_missing_primary_source_cannot_create_buy_candidate():
    market = {
        "current_price": 70,
        "drawdown_from_high": -0.30,
        "relative_return_3m": -0.20,
        "trend": "DOWNTREND",
        "as_of": "2026-01-01",
        "source": "market",
        "source_url": "https://example.com",
    }
    result = analyze_company("TEST", market, _package(with_sec=False), _history())
    assert result["action"] == "RESEARCH"
