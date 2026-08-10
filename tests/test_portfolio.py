import sys
from pathlib import Path
import pytest

import pandas as pd

sys.path.append(
    str(Path(__file__).parent.parent / "src")
)

from portfolio import calculate_position_metrics


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