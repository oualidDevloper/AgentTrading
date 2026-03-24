import os
import datetime
import time
from dotenv import load_dotenv
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.automation.stock_selector import get_interesting_stocks
from tradingagents.dataflows.notifications import send_telegram_message, format_telegram_trade_signal
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients import create_llm_client

# Load environment variables
load_dotenv()

def run_daily_automation():
    """
    Automated daily run: select stocks, analyze, and notify.
    """
    print(f"Starting automated analysis: {datetime.datetime.now()}")
    
    # 1. Select stocks
    stocks = get_interesting_stocks(limit=3) # Analyze top 3 interesting stocks
    
    # 2. Setup Analysis Params
    analysis_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Use Z.AI (ZhipuAI) or fallback to OpenAI
    provider = os.getenv("LLM_PROVIDER", "openai")
    model = os.getenv("LLM_MODEL", "gpt-4o")
    
    print(f"Using Provider: {provider}, Model: {model}")
    
    # Initialize Graph
    # We select analysts as requested (user mentioned Market Analyst)
    selected_analysts = ["market"] 
    
    # Update config with .env values
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = provider
    config["deep_think_llm"] = model
    config["quick_think_llm"] = model
    if provider == "z.ai":
        config["backend_url"] = "https://api.z.ai/api/paas/v4"
    
    graph_engine = TradingAgentsGraph(selected_analysts=selected_analysts, config=config, debug=True)
    
    for i, ticker in enumerate(stocks):
        print(f"\n--- Analyzing {ticker} ({i+1}/{len(stocks)}) ---")
        
        max_retries = 3
        retry_delay = 60 # Start with 1 minute delay for 429
        
        for attempt in range(max_retries):
            try:
                # Run the graph using the propagator
                final_state, decision = graph_engine.propagate(ticker, analysis_date)
                
                # 3. Send Notification
                report_content = final_state.get("final_trade_decision", "")
                if report_content:
                    print(f"Analysis complete for {ticker}. Sending notification...")
                    tg_msg = format_telegram_trade_signal(ticker, analysis_date, report_content)
                    if send_telegram_message(tg_msg):
                        print(f"✓ Telegram message sent for {ticker}")
                    else:
                        print(f"✗ Failed to send Telegram message for {ticker}")
                else:
                    print(f"No report generated for {ticker}")
                
                break # Success, exit retry loop
                
            except Exception as e:
                # Capture partial result if we already have it in state
                print(f"Error during {ticker} analysis: {e}")
                
                # Check if we have a decision in the state despite the error
                # We try one more time to fetch the latest state
                try:
                    # In LangGraph, we can sometimes get the latest state even if interrupted
                    # But for now, we'll check if the graph engine has it cached or if we can extract it
                    # Since we used the propagator, we might need a better way to catch state
                    pass
                except:
                    pass

                if "429" in str(e) or "1302" in str(e):
                    print(f"Rate limit hit during {ticker} (Attempt {attempt+1}/{max_retries}). Waiting {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2 # Exponential backoff
                else:
                    print(f"Full error for {ticker}: {e}")
                    # Don't break here, we might want to try other stocks if this one failed due to 500
                    break
                    
        # Add delay between different stocks
        if i < len(stocks) - 1:
            delay = int(os.getenv("ANALYSIS_DELAY_SECONDS", "120")) # Default 2 mins between stocks
            print(f"Waiting {delay} seconds before next stock...")
            time.sleep(delay)
            
    print(f"\nAutomated analysis finished: {datetime.datetime.now()}")

if __name__ == "__main__":
    run_daily_automation()
