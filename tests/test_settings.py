import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent / "src"))

from settings import load_settings


def test_load_settings_resolves_project_paths(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"watchlist": ["msft", "QCOM", "msft"], "cash_balance": 100}),
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.watchlist == ("MSFT", "QCOM")
    assert settings.portfolio_file == tmp_path / "portfolio.csv"
    assert settings.data_dir.exists()


def test_invalid_watchlist_is_rejected(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"watchlist": "MSFT"}', encoding="utf-8")
    with pytest.raises(ValueError, match="watchlist"):
        load_settings(config)
