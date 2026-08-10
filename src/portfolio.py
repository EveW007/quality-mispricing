import pandas as pd


def load_portfolio(file_path):
    portfolio = pd.read_csv(file_path)
    return portfolio


def calculate_position_metrics(
    portfolio,
    total_account_value,
):
    portfolio = portfolio.copy()

    portfolio["market_value"] = (
        portfolio["shares"]
        * portfolio["current_price"]
    )

    portfolio["cost_basis"] = (
        portfolio["shares"]
        * portfolio["average_cost"]
    )

    portfolio["profit_loss"] = (
        portfolio["market_value"]
        - portfolio["cost_basis"]
    )

    portfolio["return_pct"] = (
        portfolio["current_price"]
        / portfolio["average_cost"]
        - 1
    )

    portfolio["portfolio_weight"] = (
        portfolio["market_value"]
        / total_account_value
    )

    return portfolio