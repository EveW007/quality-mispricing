import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent / "src"))

from market_data import calculate_return


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