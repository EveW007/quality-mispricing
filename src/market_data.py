import yfinance as yf


def calculate_return(series, days):
    if len(series) <= days:
        return None

    current_price = series.iloc[-1]
    past_price = series.iloc[-days - 1]

    return current_price / past_price - 1


def get_market_data(ticker):
    stock = yf.Ticker(ticker)

    history = stock.history(period="1y")

    if history.empty:
        raise ValueError(f"No market data found for {ticker}")

    close = history["Close"]
    high = history["High"]

    current_price = close.iloc[-1]
    high_52w = high.max()

    drawdown_from_high = current_price / high_52w - 1

    return {
        "ticker": ticker,
        "current_price": current_price,
        "high_52w": high_52w,
        "drawdown_from_high": drawdown_from_high,
        "return_5d": calculate_return(close, 5),
        "return_1m": calculate_return(close, 21),
        "return_3m": calculate_return(close, 63),
    }

def get_valuation_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info

    return {
        "ticker": ticker,
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
    }

def get_historical_pe_data(ticker, period="5y"):
    stock = yf.Ticker(ticker)

    history = stock.history(period=period)

    if history.empty:
        raise ValueError(f"No price history found for {ticker}")

    income_stmt = stock.quarterly_income_stmt

    if income_stmt.empty:
        raise ValueError(f"No income statement found for {ticker}")

    return {
        "ticker": ticker,
        "price_history": history,
        "income_statement": income_stmt,
    }