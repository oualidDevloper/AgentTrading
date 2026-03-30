import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def send_telegram_message(message: str) -> bool:
    """
    Sends a message to a Telegram chat via Bot API.
    
    Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id or token == "REPLACE_ME" or chat_id == "REPLACE_ME":
        print("Telegram configuration missing. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

def format_telegram_trade_signal(ticker: str, analysis_date: str, report_content: str) -> str:
    """
    Extracts summary info from report content and formats a Telegram message.
    """
    # Simple extraction logic - looks for the recommendation and levels
    # This assumes the Risk Manager follows the deliverable instructions.
    
    recommendation = "HOLD"
    if "BUY" in report_content.upper():
        recommendation = "BUY 🟢"
    elif "SELL" in report_content.upper():
        recommendation = "SELL 🔴"
        
    # Attempt to extract Entry, TP, SL using simple text search if structured as required
    # Note: A more robust extraction could use an LLM summary, but this is a starting point.
    
    msg = f"Trade Signal: {ticker}\n"
    msg += f"Date: {analysis_date}\n\n"
    msg += f"Action: {recommendation}\n"
    
    # Extraction logic for Entry, SL, TP1, TP2, TP3
    levels = {"Entry": "N/A", "Stop Loss": "N/A", "TP1": "N/A", "TP2": "N/A", "TP3": "N/A"}
    
    for line in report_content.split('\n'):
        line_upper = line.upper()
        if "ENTRY" in line_upper and "$" in line:
            levels["Entry"] = line.split(':', 1)[-1].strip() if ':' in line else line.strip()
        if ("STOP LOSS" in line_upper or "SL" in line_upper) and "$" in line:
            levels["Stop Loss"] = line.split(':', 1)[-1].strip() if ':' in line else line.strip()
        if "TP1" in line_upper and "$" in line:
            levels["TP1"] = line.split(':', 1)[-1].strip() if ':' in line else line.strip()
        elif "TP2" in line_upper and "$" in line:
            levels["TP2"] = line.split(':', 1)[-1].strip() if ':' in line else line.strip()
        elif "TP3" in line_upper and "$" in line:
            levels["TP3"] = line.split(':', 1)[-1].strip() if ':' in line else line.strip()
        elif ("TAKE PROFIT" in line_upper or "TP" in line_upper) and "$" in line and levels["TP1"] == "N/A":
             # Fallback for single TP
             levels["TP1"] = line.split(':', 1)[-1].strip() if ':' in line else line.strip()

    for label, val in levels.items():
        if val == "N/A":
            print(f"⚠ Warning: Could not find '{label}' level in report for {ticker}")

    msg += f"Entry: {levels['Entry']}\n"
    msg += f"Stop Loss: {levels['Stop Loss']}\n"
    msg += f"Take Profit 1: {levels['TP1']}\n"
    msg += f"Take Profit 2: {levels['TP2']}\n"
    msg += f"Take Profit 3: {levels['TP3']}\n"
    
    return msg
