from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import pandas as pd


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def classify_pe(forward_pe: float | None) -> str:
    if forward_pe is None:
        return "unknown"
    if forward_pe <= 0:
        return "not meaningful"
    if forward_pe < 15:
        return "potentially attractive"
    if forward_pe < 25:
        return "reasonable"
    return "premium"


def historical_pe_series(
    price_history: pd.DataFrame,
    sec_annual: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not sec_annual or price_history.empty or "Close" not in price_history:
        return []
    close = price_history["Close"].dropna().copy()
    close.index = pd.to_datetime(close.index, utc=True)
    observations: list[dict[str, Any]] = []
    for row in sec_annual:
        eps = _finite(row.get("diluted_eps"))
        period_end = row.get("period_end")
        if eps is None or eps <= 0 or not period_end:
            continue
        cutoff = pd.Timestamp(datetime.fromisoformat(period_end), tz="UTC")
        eligible = close.loc[close.index <= cutoff]
        if eligible.empty:
            continue
        price = _finite(eligible.iloc[-1])
        if price is None:
            continue
        multiple = price / eps
        if 0 < multiple < 150:
            observations.append(
                {"period_end": period_end, "price": price, "diluted_eps": eps, "pe": multiple}
            )
    return observations[-5:]


def calculate_valuation(
    current_price: float | None,
    trailing_eps: float | None,
    forward_eps: float | None,
    trailing_pe: float | None,
    forward_pe: float | None,
    free_cash_flow: float | None,
    market_cap: float | None,
    historical_pe: list[dict[str, Any]],
    revenue_growth: float | None,
    eps_growth: float | None = None,
) -> dict[str, Any]:
    price = _finite(current_price)
    trailing_eps_value = _finite(trailing_eps)
    forward_eps_value = _finite(forward_eps)
    growth_anchor = _finite(eps_growth)
    if growth_anchor is None:
        growth_anchor = _finite(revenue_growth)
    if trailing_eps_value is not None and trailing_eps_value > 0 and forward_eps_value is not None:
        allowed_growth = min(0.25, max(0.0, growth_anchor if growth_anchor is not None else 0.15))
        forward_cap = trailing_eps_value * (1 + allowed_growth)
        eps = min(forward_eps_value, forward_cap)
        eps_basis_type = "forward" if forward_eps_value <= forward_cap else "normalized forward cap"
    else:
        eps = forward_eps_value or trailing_eps_value
        eps_basis_type = "forward" if forward_eps_value is not None else "trailing"
    historical_values = [item["pe"] for item in historical_pe if _finite(item.get("pe"))]
    historical_median = (
        float(pd.Series(historical_values).median()) if historical_values else None
    )
    current_multiple = _finite(forward_pe) or _finite(trailing_pe)
    base_multiple = historical_median or current_multiple
    if base_multiple is not None:
        growth = _finite(revenue_growth)
        if growth is not None:
            base_multiple = min(base_multiple, 35 if growth >= 0.15 else 28 if growth >= 0.08 else 22)
        base_multiple = max(8.0, min(base_multiple, 45.0))

    values = None
    if price is not None and eps is not None and eps > 0 and base_multiple is not None:
        bear_multiple = max(7.0, base_multiple * 0.75)
        bull_multiple = min(50.0, base_multiple * 1.25)
        values = {
            "bear": eps * bear_multiple,
            "base": eps * base_multiple,
            "bull": eps * bull_multiple,
            "bear_multiple": bear_multiple,
            "base_multiple": base_multiple,
            "bull_multiple": bull_multiple,
            "eps_basis": eps,
            "eps_basis_type": eps_basis_type,
            "raw_forward_eps": forward_eps_value,
        }

    margin_of_safety = (
        None if values is None or price is None or values["base"] == 0 else values["base"] / price - 1
    )
    expected_return_5y = (
        None
        if values is None or price is None or price <= 0 or values["base"] <= 0
        else (values["base"] / price) ** (1 / 5) - 1
    )
    fcf_yield = (
        None
        if free_cash_flow is None or market_cap in (None, 0)
        else float(free_cash_flow) / float(market_cap)
    )
    pe_discount = (
        None
        if current_multiple is None or historical_median in (None, 0)
        else current_multiple / historical_median - 1
    )
    return {
        "trailing_pe": _finite(trailing_pe),
        "forward_pe": _finite(forward_pe),
        "historical_pe_observations": historical_pe,
        "historical_median_pe": historical_median,
        "pe_discount_to_history": pe_discount,
        "fcf_yield": fcf_yield,
        "value_range": values,
        "base_margin_of_safety_pct": margin_of_safety,
        "expected_annualized_return_5y": expected_return_5y,
        "method": "EPS scenario multiples anchored to historical fiscal-year P/E",
        "historical_source": "annual diluted EPS matched to fiscal-year-end market price",
        "limitations": (
            "Screening valuation only; forward EPS is capped by observed growth when necessary. "
            "Update assumptions and use DCF/segment methods before investing."
        ),
    }
