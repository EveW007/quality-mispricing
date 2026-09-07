from __future__ import annotations

from typing import Any

try:
    from .quality import calculate_quality_score, classify_quality_score
    from .scoring import calculate_mispricing_score, classify_mispricing_score
    from .valuation import calculate_valuation, classify_pe, historical_pe_series
except ImportError:
    from quality import calculate_quality_score, classify_quality_score
    from scoring import calculate_mispricing_score, classify_mispricing_score
    from valuation import calculate_valuation, classify_pe, historical_pe_series


def classify_fundamental_trend(metrics: dict[str, Any]) -> str:
    revenue_growth = metrics.get("revenue_growth")
    eps_growth = metrics.get("eps_growth")
    free_cash_flow = metrics.get("free_cash_flow")
    operating_margin = metrics.get("operating_margin")
    debt_to_equity = metrics.get("debt_to_equity")
    negative = sum(
        (
            revenue_growth is not None and revenue_growth < -0.05,
            eps_growth is not None and eps_growth < -0.10,
            free_cash_flow is not None and free_cash_flow <= 0,
            operating_margin is not None and operating_margin <= 0,
            debt_to_equity is not None and debt_to_equity > 2,
        )
    )
    positive = sum(
        (
            revenue_growth is not None and revenue_growth >= 0.05,
            eps_growth is not None and eps_growth >= 0.05,
            free_cash_flow is not None and free_cash_flow > 0,
            operating_margin is not None and operating_margin >= 0.10,
            debt_to_equity is not None and debt_to_equity <= 1,
        )
    )
    if negative >= 3:
        return "deteriorating"
    if positive >= 4 and negative == 0:
        return "improving"
    if negative <= 1 and positive >= 2:
        return "stable"
    return "mixed"


def required_margin_of_safety(quality_score: float, risk_flags: list[str]) -> float:
    if risk_flags:
        return 0.325
    if quality_score >= 85:
        return 0.125
    return 0.20


def analyze_company(
    ticker: str,
    market: dict[str, Any],
    fundamental_package: dict[str, Any],
    price_history: Any,
) -> dict[str, Any]:
    metrics = fundamental_package["metrics"]
    sec = fundamental_package.get("sec")
    validation = fundamental_package.get("validation", {})
    fundamental_status = classify_fundamental_trend(metrics)
    quality_score = calculate_quality_score(
        revenue_growth=metrics.get("revenue_growth"),
        eps_growth=metrics.get("eps_growth"),
        fcf_margin=metrics.get("fcf_margin"),
        debt_to_equity=metrics.get("debt_to_equity"),
    )
    annual_history = (
        sec.get("annual")
        if sec is not None and sec.get("annual")
        else metrics.get("annual_history")
    )
    historical_pe = historical_pe_series(price_history, annual_history)
    valuation = calculate_valuation(
        current_price=market.get("current_price"),
        trailing_eps=metrics.get("trailing_eps"),
        forward_eps=metrics.get("forward_eps"),
        trailing_pe=metrics.get("trailing_pe"),
        forward_pe=metrics.get("forward_pe"),
        free_cash_flow=metrics.get("free_cash_flow"),
        market_cap=metrics.get("market_cap"),
        historical_pe=historical_pe,
        revenue_growth=metrics.get("revenue_growth"),
        eps_growth=metrics.get("eps_growth"),
    )
    pe_status = classify_pe(metrics.get("forward_pe"))
    mispricing_score = calculate_mispricing_score(
        drawdown=market.get("drawdown_from_high"),
        pe_discount=valuation.get("pe_discount_to_history"),
        fundamental_status=fundamental_status,
        valuation_status=pe_status,
    )
    combined_score = round(quality_score * 0.60 + mispricing_score * 0.40, 1)

    risk_flags: list[str] = []
    if fundamental_status == "deteriorating":
        risk_flags.append("fundamentals_deteriorating")
    if metrics.get("free_cash_flow") is not None and metrics["free_cash_flow"] <= 0:
        risk_flags.append("negative_free_cash_flow")
    if metrics.get("debt_to_equity") is not None and metrics["debt_to_equity"] > 2:
        risk_flags.append("high_leverage")
    if validation.get("status") == "REVIEW":
        risk_flags.append("financial_data_mismatch")

    margin = valuation.get("base_margin_of_safety_pct")
    required_margin = required_margin_of_safety(quality_score, risk_flags)
    primary_sources = sum(
        source.get("tier") == "primary" for source in fundamental_package.get("sources", [])
    )
    if "fundamentals_deteriorating" in risk_flags or "high_leverage" in risk_flags:
        action = "AVOID"
        failed_gate = "fundamental risk gate"
    elif quality_score < 70:
        action = "NO_BUY"
        failed_gate = "quality gate"
    elif primary_sources < 1 or validation.get("status") == "UNVERIFIED":
        action = "RESEARCH"
        failed_gate = "primary-source verification gate"
    elif valuation.get("value_range") is None:
        action = "RESEARCH"
        failed_gate = "valuation data gate"
    elif margin is not None and combined_score >= 78 and margin >= required_margin:
        action = "BUY_CANDIDATE"
        failed_gate = None
    elif combined_score >= 70:
        action = "WATCH"
        failed_gate = "score or margin-of-safety gate"
    else:
        action = "NO_BUY"
        failed_gate = "combined score gate"

    return {
        "ticker": ticker.upper(),
        "as_of": market.get("as_of"),
        "action": action,
        "quality_score": quality_score,
        "quality_status": classify_quality_score(quality_score),
        "mispricing_score": mispricing_score,
        "mispricing_status": classify_mispricing_score(mispricing_score),
        "combined_score": combined_score,
        "fundamental_status": fundamental_status,
        "trend": market.get("trend"),
        "market": market,
        "fundamentals": metrics,
        "validation": validation,
        "valuation": valuation,
        "required_margin_of_safety_pct": required_margin,
        "risk_flags": risk_flags,
        "failed_gate": failed_gate,
        "sources": [
            *fundamental_package.get("sources", []),
            {
                "name": market.get("source"),
                "tier": "market_data",
                "url": market.get("source_url"),
            },
        ],
        "human_review_required": action == "BUY_CANDIDATE",
    }
