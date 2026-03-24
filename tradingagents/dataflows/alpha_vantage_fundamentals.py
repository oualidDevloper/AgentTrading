from .alpha_vantage_common import _make_api_request
from .utils import map_symbol


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """
    Retrieve comprehensive fundamental data for a given ticker symbol using Alpha Vantage.
    """
    # Map symbol to correct ticker
    ticker = map_symbol(ticker, "alpha_vantage")

    params = {
        "symbol": ticker,
    }

    return _make_api_request("OVERVIEW", params)


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """
    Retrieve balance sheet data for a given ticker symbol using Alpha Vantage.
    """
    # Map symbol to correct ticker
    ticker = map_symbol(ticker, "alpha_vantage")

    params = {
        "symbol": ticker,
    }

    return _make_api_request("BALANCE_SHEET", params)


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """
    Retrieve cash flow statement data for a given ticker symbol using Alpha Vantage.
    """
    # Map symbol to correct ticker
    ticker = map_symbol(ticker, "alpha_vantage")

    params = {
        "symbol": ticker,
    }

    return _make_api_request("CASH_FLOW", params)


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """
    Retrieve income statement data for a given ticker symbol using Alpha Vantage.
    """
    # Map symbol to correct ticker
    ticker = map_symbol(ticker, "alpha_vantage")

    params = {
        "symbol": ticker,
    }

    return _make_api_request("INCOME_STATEMENT", params)

