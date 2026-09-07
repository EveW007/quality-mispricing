from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yfinance as yf

try:
    from .cache import JsonFileCache
    from .sec_data import SecClient, fetch_sec_fundamentals
except ImportError:
    from cache import JsonFileCache
    from sec_data import SecClient, fetch_sec_fundamentals


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _latest_row(statement: pd.DataFrame, labels: tuple[str, ...]) -> tuple[str | None, float | None]:
    if statement is None or statement.empty:
        return None, None
    for label in labels:
        if label not in statement.index:
            continue
        values = statement.loc[label].dropna()
        if values.empty:
            continue
        column = values.index[0]
        return pd.Timestamp(column).date().isoformat(), _finite(values.iloc[0])
    return None, None


def _growth_from_statement(
    statement: pd.DataFrame, labels: tuple[str, ...]
) -> float | None:
    if statement is None or statement.empty:
        return None
    for label in labels:
        if label not in statement.index:
            continue
        values = statement.loc[label].dropna()
        if len(values) < 2:
            continue
        latest = _finite(values.iloc[0])
        previous = _finite(values.iloc[1])
        if latest is None or previous in (None, 0):
            continue
        return latest / previous - 1
    return None


def _annual_history_from_income(statement: pd.DataFrame) -> list[dict[str, Any]]:
    """Return normalized annual observations used for trend and valuation history."""
    if statement is None or statement.empty:
        return []
    labels = {
        "revenue": ("Total Revenue", "Operating Revenue"),
        "net_income": ("Net Income", "Net Income Common Stockholders"),
        "diluted_eps": ("Diluted EPS", "Diluted EPS Continuous Operations"),
    }
    rows: dict[str, dict[str, Any]] = {}
    for metric, candidates in labels.items():
        label = next((candidate for candidate in candidates if candidate in statement.index), None)
        if label is None:
            continue
        for period, value in statement.loc[label].dropna().items():
            period_end = pd.Timestamp(period).date().isoformat()
            rows.setdefault(period_end, {"period_end": period_end})[metric] = _finite(value)
    return [rows[period] for period in sorted(rows)]


def _fetch_yfinance_once(ticker: str) -> dict[str, Any]:
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    income = stock.income_stmt
    cash_flow = stock.cash_flow

    revenue_period, annual_revenue = _latest_row(income, ("Total Revenue", "Operating Revenue"))
    net_income_period, annual_net_income = _latest_row(income, ("Net Income", "Net Income Common Stockholders"))
    ocf_period, annual_ocf = _latest_row(cash_flow, ("Operating Cash Flow", "Total Cash From Operating Activities"))
    capex_period, annual_capex = _latest_row(cash_flow, ("Capital Expenditure", "Capital Expenditures"))

    total_revenue = _finite(info.get("totalRevenue")) or annual_revenue
    free_cash_flow = _finite(info.get("freeCashflow"))
    if free_cash_flow is None and annual_ocf is not None and annual_capex is not None:
        free_cash_flow = annual_ocf + annual_capex if annual_capex < 0 else annual_ocf - annual_capex

    debt_to_equity = _finite(info.get("debtToEquity"))
    if debt_to_equity is not None and debt_to_equity > 10:
        debt_to_equity /= 100

    return {
        "schema_version": 2,
        "ticker": ticker.upper(),
        "as_of": max(
            period for period in (revenue_period, net_income_period, ocf_period, capex_period) if period
        ) if any((revenue_period, net_income_period, ocf_period, capex_period)) else None,
        "currency": info.get("financialCurrency") or info.get("currency"),
        "market_cap": _finite(info.get("marketCap")),
        "enterprise_value": _finite(info.get("enterpriseValue")),
        "trailing_pe": _finite(info.get("trailingPE")),
        "forward_pe": _finite(info.get("forwardPE")),
        "trailing_eps": _finite(info.get("trailingEps")),
        "forward_eps": _finite(info.get("forwardEps")),
        "price_to_free_cash_flow": (
            None
            if _finite(info.get("marketCap")) is None or free_cash_flow in (None, 0)
            else _finite(info.get("marketCap")) / free_cash_flow
        ),
        "revenue_growth": _finite(info.get("revenueGrowth"))
        or _growth_from_statement(income, ("Total Revenue", "Operating Revenue")),
        "eps_growth": _finite(info.get("earningsGrowth")),
        "operating_margin": _finite(info.get("operatingMargins")),
        "gross_margin": _finite(info.get("grossMargins")),
        "fcf_margin": (
            None if total_revenue in (None, 0) or free_cash_flow is None else free_cash_flow / total_revenue
        ),
        "return_on_equity": _finite(info.get("returnOnEquity")),
        "return_on_assets": _finite(info.get("returnOnAssets")),
        "debt_to_equity": debt_to_equity,
        "total_cash": _finite(info.get("totalCash")),
        "total_debt": _finite(info.get("totalDebt")),
        "free_cash_flow": free_cash_flow,
        "shares_outstanding": _finite(info.get("sharesOutstanding")),
        "annual": {
            "period_end": revenue_period,
            "revenue": annual_revenue,
            "net_income_period": net_income_period,
            "net_income": annual_net_income,
            "operating_cash_flow_period": ocf_period,
            "operating_cash_flow": annual_ocf,
            "capex_period": capex_period,
            "capex": annual_capex,
        },
        "annual_history": _annual_history_from_income(income),
        "source": "Yahoo Finance via yfinance",
        "source_tier": "independent",
        "source_url": f"https://finance.yahoo.com/quote/{ticker.upper()}/financials",
    }


def fetch_yfinance_fundamentals(
    ticker: str,
    cache: JsonFileCache,
    cache_hours: int,
    offline: bool = False,
    attempts: int = 3,
) -> dict[str, Any]:
    key = f"v2_yf_fundamentals_{ticker.upper()}"
    cached = cache.get(key, timedelta(hours=cache_hours))
    if cached is not None:
        return cached
    stale = cache.get(key)
    if offline:
        if stale is not None:
            return stale
        raise RuntimeError(f"No cached fundamentals for {ticker}")
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            payload = _fetch_yfinance_once(ticker)
            cache.set(key, payload)
            return payload
        except Exception as exc:
            error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Fundamentals failed for {ticker}: {error}") from error


def _discrepancy(primary: float | None, secondary: float | None) -> float | None:
    if primary in (None, 0) or secondary is None:
        return None
    return abs(primary - secondary) / abs(primary)


def cross_validate_fundamentals(
    yfinance_data: dict[str, Any], sec_data: dict[str, Any] | None
) -> dict[str, Any]:
    if not sec_data or not sec_data.get("annual"):
        return {
            "status": "UNVERIFIED",
            "checks": [],
            "warnings": ["SEC primary-source data unavailable"],
        }
    sec_latest = sec_data["annual"][-1]
    yf_annual = yfinance_data.get("annual", {})
    checks: list[dict[str, Any]] = []
    for metric in ("revenue", "net_income", "operating_cash_flow"):
        primary = _finite(sec_latest.get(metric))
        secondary = _finite(yf_annual.get(metric))
        primary_period = sec_latest.get("period_end")
        secondary_period = (
            yf_annual.get("period_end")
            if metric == "revenue"
            else yf_annual.get(f"{metric}_period")
        )
        periods_match = primary_period == secondary_period
        difference = _discrepancy(primary, secondary) if periods_match else None
        checks.append(
            {
                "metric": metric,
                "primary_value": primary,
                "primary_period": primary_period,
                "secondary_value": secondary,
                "secondary_period": secondary_period,
                "difference_pct": difference,
                "status": (
                    "PERIOD_MISMATCH"
                    if primary is not None and secondary is not None and not periods_match
                    else "MISSING"
                    if difference is None
                    else "MATCH"
                    if difference <= 0.01
                    else "REVIEW"
                ),
            }
        )
    comparable = [check for check in checks if check["difference_pct"] is not None]
    warnings = [
        f"{check['metric']} differs by {check['difference_pct']:.1%}"
        for check in comparable
        if check["difference_pct"] > 0.01
    ]
    if not comparable:
        status = "UNVERIFIED"
    elif warnings:
        status = "REVIEW"
    else:
        status = "VERIFIED"
    return {"status": status, "checks": checks, "warnings": warnings}


def fetch_fundamental_package(
    ticker: str,
    cache_dir: str | Path,
    fundamentals_cache_hours: int,
    sec_client: SecClient | None,
    offline: bool = False,
) -> dict[str, Any]:
    cache = JsonFileCache(Path(cache_dir) / "fundamentals")
    yfinance_data = fetch_yfinance_fundamentals(
        ticker, cache, fundamentals_cache_hours, offline
    )
    sec_data = None
    sec_error = None
    if sec_client is not None:
        try:
            sec_data = fetch_sec_fundamentals(sec_client, ticker, offline)
        except Exception as exc:
            sec_error = str(exc)
    validation = cross_validate_fundamentals(yfinance_data, sec_data)
    if sec_error:
        validation["warnings"].append(sec_error)
    return {
        "ticker": ticker.upper(),
        "metrics": yfinance_data,
        "sec": sec_data,
        "validation": validation,
        "sources": [
            source
            for source in (
                {
                    "name": yfinance_data["source"],
                    "tier": yfinance_data["source_tier"],
                    "url": yfinance_data["source_url"],
                },
                None
                if sec_data is None
                else {
                    "name": sec_data["source"],
                    "tier": sec_data["source_tier"],
                    "url": sec_data["source_url"],
                },
            )
            if source is not None
        ],
    }


def fetch_universe_fundamentals(
    tickers: Iterable[str],
    cache_dir: str | Path,
    fundamentals_cache_hours: int,
    sec_client: SecClient | None,
    offline: bool = False,
    workers: int = 4,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    unique = tuple(dict.fromkeys(ticker.strip().upper() for ticker in tickers if ticker.strip()))
    packages: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(workers, max(1, len(unique)))) as executor:
        futures = {
            executor.submit(
                fetch_fundamental_package,
                ticker,
                cache_dir,
                fundamentals_cache_hours,
                sec_client,
                offline,
            ): ticker
            for ticker in unique
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                packages[ticker] = future.result()
            except Exception as exc:
                errors[ticker] = str(exc)
    return packages, errors
