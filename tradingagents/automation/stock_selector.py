import yfinance as yf
import pandas as pd
from datetime import datetime

def get_interesting_stocks(limit=5):
    """
    Selects interesting stocks based on daily volume and price movement.
    Uses an 'Interest Score' based on volume spikes and price volatility.
    """
    # Expanded list of stocks and crypto (70+ tickers)
    tickers = [
        # Tech & AI
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX", "AMD", "INTC", 
        "AVGO", "ORCL", "SMCI", "PLTR", "ASML", "TSM", "ARM", "QCOM", "MU", "AMAT",
        # Finance & Payments
        "JPM", "V", "MA", "PYPL", "SQ", "COIN", "GS", "MS", "BAC", "WFC",
        # Consumer & Others
        "DIS", "BA", "XOM", "CVX", "COST", "WMT", "NKE", "SBUX", "PFE", "MRNA",
        "U", "RBLX", "SHOP", "SE", "MELI", "BABA", "PDD", "JD", "BIDU", "TME",
        # Crypto (Yahoo Finance format)
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD",
        "AVAX-USD", "DOT-USD", "LINK-USD", "MATIC-USD", "LTC-USD", "SHIB-USD"
    ]
    
    print(f"Scanning {len(tickers)} tickers for interesting opportunities...")
    
    results = []
    for i, ticker_symbol in enumerate(tickers):
        if i % 10 == 0:
            print(f"[{i}/{len(tickers)}] Working on {ticker_symbol}...", flush=True)
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Get 20 days of data to calculate metrics
            hist = ticker.history(period="20d")
            if len(hist) < 2:
                continue
                
            # 1. Volume Spike (Today's volume vs 14-day average)
            # Use iloc[:-1] to exclude the current day from the average
            avg_volume = hist['Volume'].tail(15).iloc[:-1].mean()
            curr_volume = hist['Volume'].iloc[-1]
            volume_spike = curr_volume / avg_volume if avg_volume > 0 else 1
            
            # 2. Price Volatility (abs change today)
            price_change = ((hist['Close'].iloc[-1] - hist['Open'].iloc[-1]) / hist['Open'].iloc[-1]) * 100
            
            # 3. Composite Interest Score
            # Weight: 60% volume spike (novelty/news), 40% price movement (volatility)
            interest_score = (abs(price_change) * 0.4) + (min(volume_spike, 5) * 0.6)
            
            is_crypto = "-USD" in ticker_symbol
            timeframe = "INTRADAY" if is_crypto or abs(price_change) > 5 else "SWING"
            
            results.append({
                "ticker": ticker_symbol,
                "interest_score": interest_score,
                "change": price_change,
                "volume_spike": volume_spike,
                "timeframe": timeframe
            })
        except Exception:
            # Skip individual errors to maintain scanning momentum
            continue
            
    df = pd.DataFrame(results)
    if df.empty:
        return [{"ticker": "AAPL", "timeframe": "SWING"}, {"ticker": "BTC-USD", "timeframe": "INTRADAY"}]
        
    # Sort by interest score (descending)
    df = df.sort_values(by="interest_score", ascending=False)
    
    selected_dicts = df.head(limit).to_dict('records')
    print(f"Selected tickers for today: {[d['ticker'] for d in selected_dicts]}")
    return selected_dicts

if __name__ == "__main__":
    stocks = get_interesting_stocks()
    print(stocks)
