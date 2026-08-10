def score_revenue_growth(revenue_growth):
    if revenue_growth is None:
        return 0

    if revenue_growth >= 0.20:
        return 25

    if revenue_growth >= 0.10:
        return 20

    if revenue_growth >= 0.05:
        return 15

    if revenue_growth >= 0:
        return 8

    return 0


def score_eps_growth(eps_growth):
    if eps_growth is None:
        return 0

    if eps_growth >= 0.20:
        return 25

    if eps_growth >= 0.10:
        return 20

    if eps_growth >= 0.05:
        return 15

    if eps_growth >= 0:
        return 8

    return 0


def score_fcf_margin(fcf_margin):
    if fcf_margin is None:
        return 0

    if fcf_margin >= 0.25:
        return 25

    if fcf_margin >= 0.15:
        return 20

    if fcf_margin >= 0.10:
        return 15

    if fcf_margin >= 0.05:
        return 8

    return 0


def score_debt_to_equity(debt_to_equity):
    if debt_to_equity is None:
        return 0

    if debt_to_equity <= 0.30:
        return 25

    if debt_to_equity <= 0.60:
        return 20

    if debt_to_equity <= 1.00:
        return 15

    if debt_to_equity <= 2.00:
        return 8

    return 0


def calculate_quality_score(
    revenue_growth,
    eps_growth,
    fcf_margin,
    debt_to_equity,
):
    return (
        score_revenue_growth(revenue_growth)
        + score_eps_growth(eps_growth)
        + score_fcf_margin(fcf_margin)
        + score_debt_to_equity(debt_to_equity)
    )


def classify_quality_score(score):
    if score >= 85:
        return "EXCELLENT"

    if score >= 70:
        return "GOOD"

    if score >= 50:
        return "AVERAGE"

    return "WEAK"