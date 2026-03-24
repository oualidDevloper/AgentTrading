import yfinance as yf
import pandas as pd
from datetime import datetime

def get_interesting_stocks(limit=5):
    """
    Selects interesting stocks based on daily volume and price movement.
    """
    # Popular liquid stocks to scan
    tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", 
        "NFLX", "AMD", "INTC", "PYPL", "BABA", "CRM", "ADBE", 
        "JPM", "V", "MA", "DIS", "BA", "XOM", "CVX", "COST", "WMT"
    ]
    
    print(f"Scanning {len(tickers)} tickers for interesting opportunities...")
    
    results = []
    for ticker_symbol in tickers:
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Get 1 day of data
            hist = ticker.history(period="1d")
            if hist.empty:
                continue
                
            # Calculate basic metrics
            price_change = ((hist['Close'].iloc[-1] - hist['Open'].iloc[0]) / hist['Open'].iloc[0]) * 100
            volume = hist['Volume'].iloc[-1]
            
            results.append({
                "ticker": ticker_symbol,
                "change": abs(price_change),
                "volume": volume,
                "raw_change": price_change
            })
        except Exception as e:
            print(f"Error scanning {ticker_symbol}: {e}")
            
    # Sort by absolute price change (volatility) and volume
    # This identifies stocks with significant movement
    df = pd.DataFrame(results)
    if df.empty:
        return ["AAPL", "NVDA", "TSLA"] # Fallback
        
    df = df.sort_values(by=["change", "volume"], ascending=False)
    
    selected = df.head(limit)["ticker"].tolist()
    print(f"Selected stocks for today: {selected}")
    return selected

if __name__ == "__main__":
    stocks = get_interesting_stocks()
    print(stocks)
