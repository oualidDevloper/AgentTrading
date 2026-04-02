import os
import datetime
import time
import concurrent.futures
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
                # Run the graph using the propagator with a 30-minute timeout
                timeout_sec = int(os.getenv("ANALYSIS_TIMEOUT_SECONDS", "1800"))
                print(f"Running analysis with {timeout_sec}s timeout...")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(graph_engine.propagate, ticker, analysis_date)
                    try:
                        final_state, decision = future.result(timeout=timeout_sec)
                    except concurrent.futures.TimeoutError:
                        print(f"⌛ TIMEOUT: Analysis for {ticker} exceeded {timeout_sec}s. Skipping to next stock.")
                        break # Exit retry loop for this ticker
                
                # 3. Send Notification
                report_content = final_state.get("final_trade_decision", "")
                if report_content:
                    print(f"Analysis complete for {ticker}. Final decision length: {len(report_content)} characters.")
                    print(f"Decision preview: {report_content[:100]}...")
                    tg_msg = format_telegram_trade_signal(ticker, analysis_date, report_content)
                    print(f"Formatted Telegram message for {ticker}. Sending...")
                    if send_telegram_message(tg_msg):
                        print(f"✓ Telegram message SUCCESSFULLY sent for {ticker}")
                    else:
                        print(f"✗ FAILED to send Telegram message for {ticker}. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
                else:
                    print(f"⚠ No report generated for {ticker}. The 'final_trade_decision' key was empty in the final state.")
                
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
                    print(f"RATE LIMIT HIT during {ticker} (Attempt {attempt+1}/{max_retries}). Waiting {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2 # Exponential backoff
                else:
                    print(f"CRITICAL ERROR for {ticker}: {e}")
                    # Log full traceback for debugging (if we had a logger, but print works for CI)
                    import traceback
                    traceback.print_exc()
                    break
                    
        # Add delay between different stocks
        if i < len(stocks) - 1:
            delay = int(os.getenv("ANALYSIS_DELAY_SECONDS", "120")) # Default 2 mins between stocks
            print(f"Waiting {delay} seconds before next stock...")
            time.sleep(delay)
            
    print(f"\nAutomated analysis finished: {datetime.datetime.now()}")

if __name__ == "__main__":
    import schedule
    import time
    
    print("Initializing internal scheduler for Render free tier worker...")
    print("Configuration: Run at 14:30 UTC Mon-Fri.")

    schedule.every().monday.at("14:30").do(run_daily_automation)
    schedule.every().tuesday.at("14:30").do(run_daily_automation)
    schedule.every().wednesday.at("14:30").do(run_daily_automation)
    schedule.every().thursday.at("14:30").do(run_daily_automation)
    schedule.every().friday.at("14:30").do(run_daily_automation)

    # Note: Docker containers on Render run in UTC timezone by default.
    while True:
        schedule.run_pending()
        time.sleep(60)
