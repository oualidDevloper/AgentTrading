import os
import json
import pandas as pd
from datetime import date, timedelta, datetime
from typing import Annotated

SavePathType = Annotated[str, "File path to save data. If None, data is not saved."]

def save_output(data: pd.DataFrame, tag: str, save_path: SavePathType = None) -> None:
    if save_path:
        data.to_csv(save_path)
        print(f"{tag} saved to {save_path}")


def get_current_date():
    return date.today().strftime("%Y-%m-%d")


def decorate_all_methods(decorator):
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls

    return class_decorator



SYMBOL_MAPPING = {
    "yfinance": {
        "S&P 500": "^GSPC",
        "SPX": "^GSPC",
        "NASDAQ 100": "^NDX",
        "NDX": "^NDX",
        "DOW JONES": "^DJI",
        "DJI": "^DJI",
        "FTSE 100": "^FTSE",
        "DAX": "^GDAXI",
        "CAC 40": "^FCHI",
        "NIKKEI 225": "^N225",
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
    },
    "alpha_vantage": {
        "S&P 500": "SPX",
        "NASDAQ 100": "NDX",
        "DOW JONES": "DJI",
    }
}

def map_symbol(symbol: str, vendor: str) -> str:
    """
    Maps common index names or aliases to vendor-specific tickers.
    
    Args:
        symbol: The input symbol or name (e.g., "S&P 500")
        vendor: The data vendor ("yfinance" or "alpha_vantage")
        
    Returns:
        The mapped ticker symbol, or the original symbol if no mapping exists.
    """
    if not symbol:
        return symbol
        
    vendor_map = SYMBOL_MAPPING.get(vendor.lower(), {})
    
    # Try case-insensitive match
    symbol_upper = symbol.strip().upper()
    
    # Check for direct matches in the mapping
    for key, mapped_value in vendor_map.items():
        if key.upper() == symbol_upper:
            return mapped_value
            
    # If no mapping found, return original (but stripped)
    return symbol.strip()

def get_next_weekday(date):

    if not isinstance(date, datetime):
        date = datetime.strptime(date, "%Y-%m-%d")

    if date.weekday() >= 5:
        days_to_add = 7 - date.weekday()
        next_weekday = date + timedelta(days=days_to_add)
        return next_weekday
    else:
        return date
