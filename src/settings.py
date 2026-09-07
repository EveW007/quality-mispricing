from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    project_dir: Path
    portfolio_file: Path
    data_dir: Path
    reports_dir: Path
    benchmark: str = "SPY"
    watchlist: tuple[str, ...] = ()
    timezone: str = "Asia/Singapore"
    cash_balance: float = 0.0
    total_account_value: float | None = None
    history_period: str = "5y"
    market_cache_hours: int = 8
    fundamentals_cache_hours: int = 24
    sec_cache_hours: int = 168
    max_candidates: int = 5
    request_timeout_seconds: int = 20
    universe_provider: str = "watchlist"
    universe_cache_hours: int = 168
    deep_candidate_limit: int = 12
    min_average_dollar_volume: float = 20_000_000.0
    deep_research_enabled: bool = True
    deep_research_max_new_tasks: int = 1
    deep_research_cooldown_days: int = 30
    deep_research_min_combined_score: float = 85.0
    deep_research_min_margin_of_safety: float = 0.25
    sec_user_agent: str | None = field(default=None, repr=False)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "quality_mispricing.sqlite3"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def universe(self) -> tuple[str, ...]:
        tickers = [self.benchmark, *self.watchlist]
        return tuple(dict.fromkeys(ticker.upper() for ticker in tickers if ticker))

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)


def _resolve(project_dir: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else project_dir / path


def _as_tickers(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("watchlist must be a list of ticker strings")
    return tuple(dict.fromkeys(item.strip().upper() for item in value if item.strip()))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError("deep_research_enabled must be true or false")


def load_settings(config_path: str | Path = "config.json") -> Settings:
    config_file = Path(config_path).expanduser().resolve()
    project_dir = config_file.parent
    payload: dict[str, Any] = {}
    if config_file.exists():
        payload = json.loads(config_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("config file must contain a JSON object")

    settings = Settings(
        project_dir=project_dir,
        portfolio_file=_resolve(project_dir, payload.get("portfolio_file", "portfolio.csv")),
        data_dir=_resolve(project_dir, payload.get("data_dir", "data")),
        reports_dir=_resolve(project_dir, payload.get("reports_dir", "reports")),
        benchmark=str(payload.get("benchmark", "SPY")).strip().upper(),
        watchlist=_as_tickers(payload.get("watchlist", [])),
        timezone=str(payload.get("timezone", "Asia/Singapore")),
        cash_balance=float(payload.get("cash_balance", 0.0)),
        total_account_value=(
            None
            if payload.get("total_account_value") is None
            else float(payload["total_account_value"])
        ),
        history_period=str(payload.get("history_period", "5y")),
        market_cache_hours=int(payload.get("market_cache_hours", 8)),
        fundamentals_cache_hours=int(payload.get("fundamentals_cache_hours", 24)),
        sec_cache_hours=int(payload.get("sec_cache_hours", 168)),
        max_candidates=int(payload.get("max_candidates", 5)),
        request_timeout_seconds=int(payload.get("request_timeout_seconds", 20)),
        universe_provider=str(payload.get("universe_provider", "watchlist")),
        universe_cache_hours=int(payload.get("universe_cache_hours", 168)),
        deep_candidate_limit=int(payload.get("deep_candidate_limit", 12)),
        min_average_dollar_volume=float(
            payload.get("min_average_dollar_volume", 20_000_000)
        ),
        deep_research_enabled=_as_bool(payload.get("deep_research_enabled", True)),
        deep_research_max_new_tasks=int(payload.get("deep_research_max_new_tasks", 1)),
        deep_research_cooldown_days=int(payload.get("deep_research_cooldown_days", 30)),
        deep_research_min_combined_score=float(
            payload.get("deep_research_min_combined_score", 85.0)
        ),
        deep_research_min_margin_of_safety=float(
            payload.get("deep_research_min_margin_of_safety", 0.25)
        ),
        sec_user_agent=(
            os.getenv("SEC_USER_AGENT")
            or payload.get("sec_user_agent")
            or None
        ),
    )
    if not settings.benchmark:
        raise ValueError("benchmark cannot be empty")
    if settings.cash_balance < 0:
        raise ValueError("cash_balance cannot be negative")
    if settings.total_account_value is not None and settings.total_account_value <= 0:
        raise ValueError("total_account_value must be positive")
    if settings.deep_candidate_limit < 0:
        raise ValueError("deep_candidate_limit cannot be negative")
    if settings.min_average_dollar_volume < 0:
        raise ValueError("min_average_dollar_volume cannot be negative")
    if settings.deep_research_max_new_tasks < 0:
        raise ValueError("deep_research_max_new_tasks cannot be negative")
    if settings.deep_research_cooldown_days < 0:
        raise ValueError("deep_research_cooldown_days cannot be negative")
    if not 0 <= settings.deep_research_min_margin_of_safety <= 1:
        raise ValueError("deep_research_min_margin_of_safety must be between 0 and 1")
    settings.ensure_directories()
    return settings
