from __future__ import annotations

from pathlib import Path
import math

import pandas as pd


REQUIRED_COLUMNS = {"ticker", "shares"}
OPTIONAL_DEFAULTS = {
    "target_weight": 0.05,
    "max_weight": 0.10,
    "add_style": "HYBRID",
}


def load_portfolio(file_path: str | Path) -> pd.DataFrame:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Portfolio file not found: {path}")
    portfolio = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(portfolio.columns)
    if missing:
        raise ValueError(f"Portfolio is missing columns: {', '.join(sorted(missing))}")
    portfolio = portfolio.copy()
    portfolio["ticker"] = portfolio["ticker"].astype(str).str.strip().str.upper()
    if portfolio["ticker"].eq("").any() or portfolio["ticker"].duplicated().any():
        raise ValueError("Portfolio tickers must be non-empty and unique")
    portfolio["shares"] = pd.to_numeric(portfolio["shares"], errors="raise")
    if (portfolio["shares"] <= 0).any():
        raise ValueError("Portfolio shares values must be positive")
    if "average_cost" not in portfolio:
        portfolio["average_cost"] = pd.NA
    raw_cost = portfolio["average_cost"]
    portfolio["average_cost"] = pd.to_numeric(raw_cost, errors="coerce")
    invalid_cost = raw_cost.notna() & raw_cost.astype(str).str.strip().ne("") & portfolio[
        "average_cost"
    ].isna()
    if invalid_cost.any() or (portfolio["average_cost"].dropna() <= 0).any():
        raise ValueError("Portfolio average_cost values must be positive or blank")
    for column, default in OPTIONAL_DEFAULTS.items():
        if column not in portfolio:
            portfolio[column] = default
    for column in ("target_weight", "max_weight"):
        portfolio[column] = pd.to_numeric(portfolio[column], errors="raise")
        if ((portfolio[column] <= 0) | (portfolio[column] > 1)).any():
            raise ValueError(f"{column} must be between 0 and 1")
    if (portfolio["target_weight"] > portfolio["max_weight"]).any():
        raise ValueError("target_weight cannot exceed max_weight")
    portfolio["add_style"] = portfolio["add_style"].astype(str).str.upper()
    return portfolio


def calculate_position_metrics(
    portfolio: pd.DataFrame,
    total_account_value: float | None = None,
    cash_balance: float = 0.0,
) -> pd.DataFrame:
    portfolio = portfolio.copy()
    for column, default in OPTIONAL_DEFAULTS.items():
        if column not in portfolio:
            portfolio[column] = default
    portfolio["market_value"] = portfolio["shares"] * portfolio["current_price"]
    portfolio["cost_basis"] = portfolio["shares"] * portfolio["average_cost"]
    portfolio["profit_loss"] = portfolio["market_value"] - portfolio["cost_basis"]
    portfolio["return_pct"] = portfolio["current_price"] / portfolio["average_cost"] - 1
    calculated_value = float(portfolio["market_value"].sum()) + float(cash_balance)
    account_value = calculated_value if total_account_value is None else float(total_account_value)
    if account_value <= 0:
        raise ValueError("total_account_value must be positive")
    portfolio["portfolio_weight"] = portfolio["market_value"] / account_value
    portfolio["weight_vs_target"] = portfolio["portfolio_weight"] - portfolio["target_weight"]
    portfolio["above_max_weight"] = portfolio["portfolio_weight"] > portfolio["max_weight"]
    portfolio.attrs["total_account_value"] = account_value
    portfolio.attrs["cash_balance"] = float(cash_balance)
    return portfolio


def position_alert(row: pd.Series) -> str:
    if bool(row.get("above_max_weight", False)):
        return "POSITION_LIMIT_REVIEW"
    drawdown = row.get("drawdown_from_high")
    if pd.notna(drawdown) and drawdown <= -0.20:
        return "FULL_FUNDAMENTAL_REVIEW"
    if pd.notna(drawdown) and drawdown <= -0.15:
        return "FUNDAMENTAL_REVIEW"
    if pd.notna(drawdown) and drawdown <= -0.10:
        return "VALUATION_REVIEW"
    if pd.notna(drawdown) and drawdown <= -0.05:
        return "PRICE_ALERT"
    return "NO_ALERT"


def analyze_index_enhancement(
    portfolio: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    benchmark: str,
    lookback_days: int = 252,
) -> dict[str, object]:
    """Measure a static current-weight portfolio against its benchmark."""
    benchmark = benchmark.upper()
    core_tickers = {benchmark, "SPY", "VOO", "IVV"}
    weights = {
        str(row["ticker"]).upper(): float(row["portfolio_weight"])
        for _, row in portfolio.iterrows()
    }
    invested_weight = sum(weights.values())
    core_weight = sum(weight for ticker, weight in weights.items() if ticker in core_tickers)
    active_weight = invested_weight - core_weight
    cash_weight = max(0.0, 1.0 - invested_weight)
    active_positions = {
        ticker: weight for ticker, weight in weights.items() if ticker not in core_tickers
    }
    largest_active = max(active_positions.items(), key=lambda item: item[1], default=(None, 0.0))

    returns: dict[str, pd.Series] = {}
    missing: list[str] = []
    for ticker in dict.fromkeys([*weights, benchmark]):
        history = histories.get(ticker)
        if history is None or history.empty or "Close" not in history:
            missing.append(ticker)
            continue
        close = history["Close"].dropna().copy()
        close.index = pd.to_datetime(close.index, utc=True).normalize()
        returns[ticker] = close.groupby(level=0).last().pct_change().dropna()

    result: dict[str, object] = {
        "benchmark": benchmark,
        "invested_weight": invested_weight,
        "core_index_weight": core_weight,
        "active_sleeve_weight": active_weight,
        "cash_or_unallocated_weight": cash_weight,
        "largest_active_ticker": largest_active[0],
        "largest_active_weight": largest_active[1],
        "missing_histories": missing,
        "method": "Current static weights versus benchmark daily close returns",
    }
    if benchmark not in returns or any(ticker not in returns for ticker in weights):
        result["status"] = "INSUFFICIENT_DATA"
        return result

    aligned = pd.concat(
        {ticker: returns[ticker] for ticker in dict.fromkeys([*weights, benchmark])},
        axis=1,
        join="inner",
    ).dropna().tail(lookback_days)
    if len(aligned) < 60:
        result["status"] = "INSUFFICIENT_DATA"
        return result

    portfolio_returns = sum(aligned[ticker] * weight for ticker, weight in weights.items())
    benchmark_returns = aligned[benchmark]
    active_returns = portfolio_returns - benchmark_returns
    benchmark_variance = benchmark_returns.var()
    beta = (
        None
        if not math.isfinite(benchmark_variance) or benchmark_variance == 0
        else portfolio_returns.cov(benchmark_returns) / benchmark_variance
    )

    def active_return(days: int) -> float | None:
        if len(aligned) < days:
            return None
        portfolio_total = (1 + portfolio_returns.tail(days)).prod() - 1
        benchmark_total = (1 + benchmark_returns.tail(days)).prod() - 1
        return float(portfolio_total - benchmark_total)

    tracking_error = float(active_returns.std() * math.sqrt(252))
    warnings: list[str] = []
    if active_weight > 0.40:
        warnings.append("ACTIVE_SLEEVE_ABOVE_40_PERCENT")
    if largest_active[1] > 0.10:
        warnings.append("SINGLE_ACTIVE_POSITION_ABOVE_10_PERCENT")
    if tracking_error > 0.10:
        warnings.append("TRACKING_ERROR_ABOVE_10_PERCENT")

    result.update(
        {
            "status": "OK",
            "observations": len(aligned),
            "annualized_volatility": float(portfolio_returns.std() * math.sqrt(252)),
            "tracking_error": tracking_error,
            "beta": None if beta is None else float(beta),
            "correlation": float(portfolio_returns.corr(benchmark_returns)),
            "active_return_3m": active_return(63),
            "active_return_6m": active_return(126),
            "active_return_12m": active_return(252),
            "warnings": warnings,
        }
    )
    return result
