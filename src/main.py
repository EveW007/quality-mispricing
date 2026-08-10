import pandas as pd

from quality import (
    calculate_quality_score,
    classify_quality_score,
)

from config import (
    fundamentals,
    manual_valuation_status,
    historical_medians,
    reference_prices,
    price_changes,
    intrinsic_value_changes,
    total_account_value,
    quality_inputs,
)

from portfolio import (
    load_portfolio,
    calculate_position_metrics,
)

from market_data import (
    get_market_data,
    get_valuation_data,
)

from valuation import classify_pe

from historical_valuation import (
    compare_to_historical_pe,
    calculate_pe_discount,
)

from signals import (
    get_signal,
    get_drawdown_action,
    get_uptrend_action,
)

from scoring import (
    calculate_mispricing_score,
    classify_mispricing_score,
)

from reporting import (
    print_portfolio_report,
    print_mispricing_ranking,
)


def main():
    # ========================================================
    # LOAD PORTFOLIO
    # ========================================================

    portfolio = load_portfolio(
        "portfolio.csv"
    )


    # ========================================================
    # FETCH MARKET DATA
    # ========================================================

    market_data_rows = []

    for ticker in portfolio["ticker"]:
        print(
            f"Fetching market data for {ticker}..."
        )

        data = get_market_data(
            ticker
        )

        market_data_rows.append(
            data
        )

    market_df = pd.DataFrame(
        market_data_rows
    )

    portfolio = portfolio.merge(
        market_df,
        on="ticker",
        how="left",
    )


    # ========================================================
    # FETCH VALUATION DATA
    # ========================================================

    valuation_rows = []

    for ticker in portfolio["ticker"]:
        print(
            f"Fetching valuation data for {ticker}..."
        )

        data = get_valuation_data(
            ticker
        )

        valuation_rows.append(
            data
        )

    valuation_df = pd.DataFrame(
        valuation_rows
    )

    portfolio = portfolio.merge(
        valuation_df,
        on="ticker",
        how="left",
    )


    # ========================================================
    # BASIC P/E VALUATION CLASSIFICATION
    # ========================================================

    pe_valuation_labels = []

    for _, stock in portfolio.iterrows():
        label = classify_pe(
            stock["forward_pe"]
        )

        pe_valuation_labels.append(
            label
        )

    portfolio["pe_valuation_status"] = (
        pe_valuation_labels
    )


    # ========================================================
    # HISTORICAL P/E DISCOUNT
    # ========================================================

    pe_discounts = []
    historical_pe_statuses = []

    for _, stock in portfolio.iterrows():
        ticker = stock["ticker"]

        historical_median = (
            historical_medians[ticker]
        )

        discount = calculate_pe_discount(
            current_pe=stock["trailing_pe"],
            historical_median_pe=(
                historical_median
            ),
        )

        pe_discounts.append(
            discount
        )

        historical_status = (
            compare_to_historical_pe(
                current_pe=(
                    stock["trailing_pe"]
                ),
                historical_median_pe=(
                    historical_median
                ),
            )
        )

        historical_pe_statuses.append(
            historical_status
        )

    portfolio["pe_discount"] = (
        pe_discounts
    )

    portfolio["historical_pe_status"] = (
        historical_pe_statuses
    )


    # ========================================================
    # MISPRICING SCORE
    # ========================================================

    mispricing_scores = []
    research_priorities = []

    for _, stock in portfolio.iterrows():
        ticker = stock["ticker"]

        score = calculate_mispricing_score(
            drawdown=(
                stock["drawdown_from_high"]
            ),
            pe_discount=(
                stock["pe_discount"]
            ),
            fundamental_status=(
                fundamentals[ticker]
            ),
            valuation_status=(
                stock["pe_valuation_status"]
            ),
        )

        mispricing_scores.append(
            score
        )

        priority = (
            classify_mispricing_score(
                score
            )
        )

        research_priorities.append(
            priority
        )

    portfolio["mispricing_score"] = (
        mispricing_scores
    )

    portfolio["research_priority"] = (
        research_priorities
    )

    # ========================================================
    # QUALITY SCORE
    # ========================================================

    quality_scores = []
    quality_statuses = []

    for _, stock in portfolio.iterrows():
        ticker = stock["ticker"]

        inputs = quality_inputs[ticker]

        score = calculate_quality_score(
            revenue_growth=inputs["revenue_growth"],
            eps_growth=inputs["eps_growth"],
            fcf_margin=inputs["fcf_margin"],
            debt_to_equity=inputs["debt_to_equity"],)

        quality_scores.append(score)

        status = classify_quality_score(score)

        quality_statuses.append(status)


    portfolio["quality_score"] = quality_scores
    portfolio["quality_status"] = quality_statuses



    # ========================================================
    # REFERENCE-PRICE DRAWDOWN
    #
    # drawdown_from_high:
    #     current price vs 52-week high
    #
    # drawdown:
    #     current price vs manual reference price
    # ========================================================

    portfolio["reference_price"] = (
        portfolio["ticker"].map(
            reference_prices
        )
    )

    portfolio["drawdown"] = (
        portfolio["current_price"]
        / portfolio["reference_price"]
        - 1
    )


    # ========================================================
    # POSITION CALCULATIONS
    # ========================================================

    portfolio = calculate_position_metrics(
        portfolio=portfolio,
        total_account_value=(
            total_account_value
        ),
    )


    # ========================================================
    # GENERAL POSITION SIGNAL
    # ========================================================

    signals = []

    for _, stock in portfolio.iterrows():
        ticker = stock["ticker"]

        signal = get_signal(
            current_weight=(
                stock["portfolio_weight"]
            ),
            target_weight=(
                stock["target_weight"]
            ),
            max_weight=(
                stock["max_weight"]
            ),
            fundamental_status=(
                fundamentals[ticker]
            ),
            valuation_status=(
                manual_valuation_status[
                    ticker
                ]
            ),
        )

        signals.append(
            signal
        )

    portfolio["signal"] = signals


    # ========================================================
    # LEFT-SIDE ADDING LOGIC
    # ========================================================

    drawdown_actions = []

    for _, stock in portfolio.iterrows():
        ticker = stock["ticker"]

        action = get_drawdown_action(
            drawdown=(
                stock["drawdown"]
            ),
            fundamental_status=(
                fundamentals[ticker]
            ),
            add_style=(
                stock["add_style"]
            ),
        )

        drawdown_actions.append(
            action
        )

    portfolio["drawdown_action"] = (
        drawdown_actions
    )


    # ========================================================
    # RIGHT-SIDE ADDING LOGIC
    # ========================================================

    uptrend_actions = []

    for _, stock in portfolio.iterrows():
        ticker = stock["ticker"]

        action = get_uptrend_action(
            price_change=(
                price_changes[ticker]
            ),
            intrinsic_value_change=(
                intrinsic_value_changes[
                    ticker
                ]
            ),
            fundamental_status=(
                fundamentals[ticker]
            ),
            add_style=(
                stock["add_style"]
            ),
        )

        uptrend_actions.append(
            action
        )

    portfolio["uptrend_action"] = (
        uptrend_actions
    )


    # ========================================================
    # REPORTING
    # ========================================================

    print_portfolio_report(
    portfolio=portfolio,
    fundamentals=fundamentals,
    manual_valuation_status=manual_valuation_status,
    historical_medians=historical_medians,
    price_changes=price_changes,
    intrinsic_value_changes=intrinsic_value_changes,)

    print_mispricing_ranking(
        portfolio
    )


if __name__ == "__main__":
    main()