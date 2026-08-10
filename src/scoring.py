def score_drawdown(drawdown):
    if drawdown is None:
        return 0

    if drawdown <= -0.40:
        return 25
    if drawdown <= -0.30:
        return 22
    if drawdown <= -0.20:
        return 18
    if drawdown <= -0.10:
        return 10

    return 3


def score_pe_discount(pe_discount):
    if pe_discount is None:
        return 0

    if pe_discount <= -0.40:
        return 25
    if pe_discount <= -0.30:
        return 22
    if pe_discount <= -0.20:
        return 18
    if pe_discount <= -0.10:
        return 12

    if pe_discount <= 0.10:
        return 5

    return 0


def score_fundamentals(fundamental_status):
    if fundamental_status == "improving":
        return 25

    if fundamental_status == "stable":
        return 20

    if fundamental_status == "mixed":
        return 10

    if fundamental_status == "deteriorating":
        return 0

    return 5


def score_valuation(valuation_status):
    if valuation_status in (
        "attractive",
        "potentially attractive",
    ):
        return 25

    if valuation_status in (
        "fair",
        "reasonable",
    ):
        return 15

    if valuation_status == "premium":
        return 5

    if valuation_status == "expensive":
        return 0

    return 5


def calculate_mispricing_score(
    drawdown,
    pe_discount,
    fundamental_status,
    valuation_status,
):
    score = (
        score_drawdown(drawdown)
        + score_pe_discount(pe_discount)
        + score_fundamentals(fundamental_status)
        + score_valuation(valuation_status)
    )

    return score

def classify_mispricing_score(score):
    if score >= 85:
        return "HIGH PRIORITY"

    if score >= 70:
        return "RESEARCH"

    if score >= 55:
        return "WATCH"

    return "LOW PRIORITY"