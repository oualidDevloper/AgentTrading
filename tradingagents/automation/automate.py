import os
import datetime
import time
import concurrent.futures
from dotenv import load_dotenv
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.automation.stock_selector import get_interesting_stocks
from tradingagents.dataflows.notifications import (
    send_telegram_message,
    send_telegram_error,
    send_telegram_summary,
    format_telegram_trade_signal,
)
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
    stocks = get_interesting_stocks(limit=3) # Analyze top 3 interesting tickers
    
    # 2. Setup Analysis Params
    analysis_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Use Z.AI (ZhipuAI) or fallback to OpenAI
    provider = os.getenv("LLM_PROVIDER", "z.ai")
    deep_provider = os.getenv("DEEP_LLM_PROVIDER", "openrouter")
    model = os.getenv("LLM_MODEL", "glm-4-flash")
    deep_model = os.getenv("DEEP_LLM_MODEL", "google/gemini-2.0-flash-exp:free")
    
    print(f"Using Provider: {provider}, Quick Model: {model} | Deep Provider: {deep_provider}, Deep Model: {deep_model}")
    
    # Initialize Graph with market + news analysts for richer context
    selected_analysts = ["market", "news"]
    
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = provider
    config["deep_llm_provider"] = deep_provider
    config["deep_think_llm"] = deep_model
    config["quick_think_llm"] = model
    
    # Set a per-agent timeout of 240 seconds to prevent hangs but allow deep thinking
    config["timeout"] = int(os.getenv("LLM_TIMEOUT", "240"))
    
    graph_engine = TradingAgentsGraph(selected_analysts=selected_analysts, config=config, debug=True)
    
    # Create a lightweight LLM for signal extraction (reuses same provider)
    extraction_llm = None
    try:
        extraction_client = create_llm_client(
            provider=provider,
            model=model,
            base_url="https://open.bigmodel.cn/api/paas/v4" if provider == "z.ai" else None,
            timeout=30,
        )
        extraction_llm = extraction_client.get_llm()
        print("✓ Extraction LLM ready for structured signal parsing")
    except Exception as e:
        print(f"⚠ Could not create extraction LLM ({e}), will fall back to regex parsing")
    
    # Track results for summary
    daily_results = []
    
    for i, stock_item in enumerate(stocks):
        if isinstance(stock_item, dict):
            ticker = stock_item["ticker"]
            timeframe = stock_item.get("timeframe", "SWING")
        else:
            ticker = stock_item
            timeframe = "SWING"
            
        print(f"\n--- Analyzing {ticker} ({timeframe} focus) ({i+1}/{len(stocks)}) ---")
        
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
                        daily_results.append({"ticker": ticker, "success": False, "action": None})
                        send_telegram_error(ticker, f"Timeout après {timeout_sec}s")
                        break # Exit retry loop for this ticker
                
                # 3. Process signal and Send Notification
                report_content = final_state.get("final_trade_decision", "")
                if report_content:
                    print(f"Analysis complete for {ticker}. Final decision length: {len(report_content)} characters.")
                    
                    from tradingagents.dataflows.notifications import extract_signal_from_report, compute_rr_ratio
                    extracted_signal = extract_signal_from_report(report_content, llm=extraction_llm)
                    
                    action = extracted_signal.get("action", "HOLD").upper()
                    rr = compute_rr_ratio(extracted_signal)
                    
                    is_qualified = True
                    if action != "HOLD" and rr < 1.2:
                        is_qualified = False
                        print(f"⚠ Signal rejected: {action} on {ticker} has low R/R ratio ({rr} < 1.2).")
                    
                    if is_qualified:
                        tg_msg = format_telegram_trade_signal(
                            ticker, analysis_date, report_content, extracted_signal=extracted_signal
                        )
                        print(f"Formatted Telegram message for {ticker}. Sending...")
                        
                        if send_telegram_message(tg_msg):
                            print(f"✓ Telegram message SUCCESSFULLY sent for {ticker}")
                        else:
                            print(f"✗ FAILED to send Telegram message for {ticker}.")
                    
                    daily_results.append({"ticker": ticker, "success": True, "action": action})
                    
                    if action != "HOLD":
                        try:
                            from tradingagents.automation.performance_tracker import PerformanceTracker
                            PerformanceTracker().add_signal(ticker, analysis_date, extracted_signal)
                        except Exception as pt_err:
                            print(f"⚠ Failed to save signal history: {pt_err}")
                else:
                    print(f"⚠ No report generated for {ticker}. The 'final_trade_decision' key was empty in the final state.")
                    daily_results.append({"ticker": ticker, "success": False, "action": None})
                
                break # Success, exit retry loop
                
            except Exception as e:
                print(f"Error during {ticker} analysis: {e}")
                
                if "429" in str(e) or "1302" in str(e):
                    print(f"RATE LIMIT HIT during {ticker} (Attempt {attempt+1}/{max_retries}). Waiting {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2 # Exponential backoff
                else:
                    print(f"CRITICAL ERROR for {ticker}: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # Send error notification to Telegram
                    error_short = str(e)[:100]
                    send_telegram_error(ticker, error_short)
                    daily_results.append({"ticker": ticker, "success": False, "action": None})
                    break
                    
        # Add delay between different stocks
        if i < len(stocks) - 1:
            delay = int(os.getenv("ANALYSIS_DELAY_SECONDS", "120")) # Default 2 mins between stocks
            print(f"Waiting {delay} seconds before next stock...")
            time.sleep(delay)
    
    # Send daily summary
    if daily_results:
        print("\nSending daily summary to Telegram...")
        send_telegram_summary(daily_results)
        
    print("\nEvaluating past signals performance...")
    try:
        from tradingagents.automation.performance_tracker import PerformanceTracker
        from tradingagents.dataflows.notifications import send_telegram_performance_report
        
        tracker = PerformanceTracker()
        report_data = tracker.evaluate_past_signals()
        
        # Determine if we should send it to Telegram
        if datetime.datetime.today().weekday() == 4: # Friday
            print("Sending weekly performance report...")
            send_telegram_performance_report(report_data)
        else:
            print("Performance evaluated (Report sent to Telegram only on Fridays).")
    except Exception as e:
        print(f"⚠ Failed to track performance: {e}")
            
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
