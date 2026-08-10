import pandas as pd


def format_number(value):
    if pd.isna(value):
        return "N/A"

    return f"{value:.1f}"


def format_percent(value):
    if pd.isna(value):
        return "N/A"

    return f"{value:.1%}"


def format_money(value):
    if pd.isna(value):
        return "N/A"

    return f"${value:.2f}"


def print_portfolio_report(
    portfolio,
    fundamentals,
    manual_valuation_status,
    historical_medians,
    price_changes,
    intrinsic_value_changes,
):
    print("\n")
    print("=" * 60)
    print("PORTFOLIO REPORT")
    print("=" * 60)

    for _, stock in portfolio.iterrows():
        ticker = stock["ticker"]

        print("\n" + "-" * 60)
        print(ticker)
        print("-" * 60)

        print(
            f"Current price: "
            f"{format_money(stock['current_price'])}"
        )

        print(
            f"Average cost: "
            f"{format_money(stock['average_cost'])}"
        )

        print(
            f"Shares: "
            f"{stock['shares']}"
        )

        print(
            f"Market value: "
            f"{format_money(stock['market_value'])}"
        )

        print(
            f"Profit/Loss: "
            f"{format_money(stock['profit_loss'])}"
        )

        print(
            f"Return: "
            f"{format_percent(stock['return_pct'])}"
        )

        print(
            f"Portfolio weight: "
            f"{format_percent(stock['portfolio_weight'])}"
        )

        print(
            f"Target weight: "
            f"{format_percent(stock['target_weight'])}"
        )

        print(
            f"Max weight: "
            f"{format_percent(stock['max_weight'])}"
        )

        print()

        print(
            f"Add style: "
            f"{stock['add_style']}"
        )

        print(
            f"Fundamentals: "
            f"{fundamentals[ticker]}"
        )

        print(
            f"Manual valuation: "
            f"{manual_valuation_status[ticker]}"
        )

        print(
            f"General action: "
            f"{stock['signal']}"
        )

        print()

        print(
            f"Reference price: "
            f"{format_money(stock['reference_price'])}"
        )

        print(
            f"Drawdown vs reference: "
            f"{format_percent(stock['drawdown'])}"
        )

        print(
            f"Left-side action: "
            f"{stock['drawdown_action']}"
        )

        print()

        print(
            f"Price change: "
            f"{format_percent(price_changes[ticker])}"
        )

        print(
            f"Intrinsic value change: "
            f"{format_percent(intrinsic_value_changes[ticker])}"
        )

        print(
            f"Right-side action: "
            f"{stock['uptrend_action']}"
        )

        print()

        print(
            f"52W high: "
            f"{format_money(stock['high_52w'])}"
        )

        print(
            f"Drawdown from 52W high: "
            f"{format_percent(stock['drawdown_from_high'])}"
        )

        print(
            f"5D return: "
            f"{format_percent(stock['return_5d'])}"
        )

        print(
            f"1M return: "
            f"{format_percent(stock['return_1m'])}"
        )

        print(
            f"3M return: "
            f"{format_percent(stock['return_3m'])}"
        )

        print()

        print(
            f"Trailing P/E: "
            f"{format_number(stock['trailing_pe'])}"
        )

        print(
            f"Forward P/E: "
            f"{format_number(stock['forward_pe'])}"
        )

        print(
            f"P/E status: "
            f"{stock['pe_valuation_status']}"
        )

        print(
            f"Historical median P/E: "
            f"{historical_medians[ticker]:.1f}"
        )

        print(
            f"PE vs history: "
            f"{format_percent(stock['pe_discount'])}"
        )

        print(
            f"Historical valuation: "
            f"{stock['historical_pe_status']}"
        )

        print()

        print(
            f"Mispricing score: "
            f"{stock['mispricing_score']}/100"
        )

        print(
            f"Research priority: "
            f"{stock['research_priority']}"
        )

        print(
            f"Quality score: "
            f"{stock['quality_score']}/100"
        )

        print(
            f"Quality status: "
            f"{stock['quality_status']}"
            )


def print_mispricing_ranking(portfolio):
    ranked = portfolio.sort_values(
        by="mispricing_score",
        ascending=False,
    )

    print("\n")
    print("=" * 60)
    print("MISPRICING RANKING")
    print("=" * 60)

    for _, stock in ranked.iterrows():
        print(
            f"{stock['ticker']}: "
            f"{stock['mispricing_score']}/100 "
            f"- {stock['research_priority']}"
        )