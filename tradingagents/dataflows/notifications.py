import requests
import os
import re
import json
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


def send_telegram_error(ticker: str, error_msg: str) -> bool:
    """Send an error notification to Telegram when analysis fails."""
    msg = f"⚠️ *Analyse échouée*\n\n"
    msg += f"📊 Ticker: `{ticker}`\n"
    msg += f"❌ Erreur: {error_msg}\n"
    msg += f"➡️ Passé au suivant."
    return send_telegram_message(msg)


def send_telegram_summary(results: list) -> bool:
    """Send a final summary of all analyses for the day."""
    total = len(results)
    success = sum(1 for r in results if r.get("success"))
    failed = total - success
    
    buys = sum(1 for r in results if r.get("action") == "BUY")
    sells = sum(1 for r in results if r.get("action") == "SELL")
    holds = sum(1 for r in results if r.get("action") == "HOLD")
    
    msg = f"📊 *Résumé du jour*\n\n"
    msg += f"✅ Analyses réussies: {success}/{total}\n"
    if failed > 0:
        msg += f"❌ Échouées: {failed}\n"
    msg += f"\n"
    if buys > 0:
        msg += f"🟢 BUY: {buys}\n"
    if sells > 0:
        msg += f"🔴 SELL: {sells}\n"
    if holds > 0:
        msg += f"⚪ HOLD: {holds}\n"
    
    # List tickers
    msg += f"\n*Détails:*\n"
    for r in results:
        status = "✅" if r.get("success") else "❌"
        action = r.get("action", "N/A")
        ticker = r.get("ticker", "???")
        if r.get("success"):
            msg += f"{status} {ticker} → {action}\n"
        else:
            msg += f"{status} {ticker} → Erreur\n"
    
    return send_telegram_message(msg)


def _extract_price(text: str) -> float:
    """Extract a price value from text like '$49.50'.
    Requires $ sign to avoid matching stray numbers like TP label indices.
    """
    # First try to match a price with $ sign
    match = re.search(r'\$([\d,]+\.\d+)', text.replace(',', ''))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    # Fallback: match $ followed by integer
    match = re.search(r'\$([\d,]+)', text.replace(',', ''))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    # Last resort: match any decimal number >= 1.0 (skip tiny numbers from labels)
    match = re.search(r'(\d+\.\d{2,})', text)
    if match:
        try:
            val = float(match.group(1))
            if val >= 1.0:
                return val
        except ValueError:
            pass
    return 0.0


def extract_signal_from_report(report_content: str, llm=None) -> dict:
    """
    Extract structured trade signal from the Risk Judge's report.
    
    Uses LLM for structured extraction if available, falls back to regex.
    Returns a dict with: action, entry, stop_loss, tp1, tp2, tp3, rationale
    """
    signal = {
        "action": "HOLD",
        "entry": 0.0,
        "stop_loss": 0.0,
        "tp1": 0.0,
        "tp2": 0.0,
        "tp3": 0.0,
        "rationale": "",
        "valid": False,
    }
    
    # Strategy 1: Use LLM for structured extraction (most reliable)
    if llm:
        try:
            extraction_prompt = f"""Extract the trading signal from the following report. Return ONLY a valid JSON object with these exact keys, no other text:

{{
  "action": "BUY" or "SELL" or "HOLD",
  "entry": <number>,
  "stop_loss": <number>,
  "tp1": <number>,
  "tp2": <number>,
  "tp3": <number>,
  "rationale": "<one sentence summary>"
}}

Rules:
- All price values must be numbers (no $ sign, no commas)
- If action is BUY: stop_loss < entry < tp1 < tp2 < tp3
- If action is SELL: stop_loss > entry > tp1 > tp2 > tp3
- If any level is missing, set it to 0

Report:
{report_content}"""

            result = llm.invoke(extraction_prompt)
            content = result.content.strip()
            
            # Extract JSON from the response (handle markdown code blocks)
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                signal["action"] = parsed.get("action", "HOLD").upper()
                signal["entry"] = float(parsed.get("entry", 0))
                signal["stop_loss"] = float(parsed.get("stop_loss", 0))
                signal["tp1"] = float(parsed.get("tp1", 0))
                signal["tp2"] = float(parsed.get("tp2", 0))
                signal["tp3"] = float(parsed.get("tp3", 0))
                signal["rationale"] = parsed.get("rationale", "")
                
                # Validate mathematical consistency
                signal["valid"] = _validate_signal(signal)
                
                if signal["valid"]:
                    print(f"  ✓ LLM extraction successful: {signal['action']} @ ${signal['entry']:.2f}")
                    return signal
                else:
                    print(f"  ⚠ LLM extraction returned invalid levels, trying regex fallback...")
        except Exception as e:
            print(f"  ⚠ LLM extraction failed ({e}), trying regex fallback...")
    
    # Strategy 2: Regex-based extraction (fallback)
    signal = _regex_extract(report_content)
    signal["valid"] = _validate_signal(signal)
    
    return signal


def _regex_extract(report_content: str) -> dict:
    """Extract signal data using regex patterns."""
    signal = {
        "action": "HOLD",
        "entry": 0.0,
        "stop_loss": 0.0,
        "tp1": 0.0,
        "tp2": 0.0,
        "tp3": 0.0,
        "rationale": "",
        "valid": False,
    }
    
    # Determine action — check multiple possible formats
    upper = report_content.upper()
    buy_patterns = ["**BUY**", "ACTION: BUY", "ACTION**: BUY", "ACTION:**BUY", ": BUY\n", ": BUY ", "RECOMMEND BUY", "PROPOSAL: **BUY"]
    sell_patterns = ["**SELL**", "ACTION: SELL", "ACTION**: SELL", "ACTION:**SELL", ": SELL\n", ": SELL ", "RECOMMEND SELL", "PROPOSAL: **SELL"]
    
    if any(p in upper for p in buy_patterns):
        signal["action"] = "BUY"
    elif any(p in upper for p in sell_patterns):
        signal["action"] = "SELL"
    
    # Extract levels line by line
    for line in report_content.split('\n'):
        line_upper = line.upper().strip()
        
        if ("ENTRY" in line_upper or "ENTRY POINT" in line_upper) and "$" in line:
            signal["entry"] = _extract_price(line)
        
        if ("STOP LOSS" in line_upper or "STOP-LOSS" in line_upper or "(SL)" in line_upper) and "$" in line:
            signal["stop_loss"] = _extract_price(line)
        
        # TP detection — handle numbered TPs
        if "TP1" in line_upper or "TAKE PROFIT 1" in line_upper:
            if "$" in line:
                signal["tp1"] = _extract_price(line)
        elif "TP2" in line_upper or "TAKE PROFIT 2" in line_upper:
            if "$" in line:
                signal["tp2"] = _extract_price(line)
        elif "TP3" in line_upper or "TAKE PROFIT 3" in line_upper:
            if "$" in line:
                signal["tp3"] = _extract_price(line)
        elif ("TAKE PROFIT" in line_upper or "TARGET" in line_upper) and "$" in line:
            # Generic TP — fill first empty slot
            price = _extract_price(line)
            if price > 0:
                if signal["tp1"] == 0:
                    signal["tp1"] = price
                elif signal["tp2"] == 0:
                    signal["tp2"] = price
                elif signal["tp3"] == 0:
                    signal["tp3"] = price
    
    # Extract rationale (first paragraph after "Rationale" heading)
    rationale_match = re.search(r'(?:rationale|reasoning|justification)[:\s]*\n?(.*?)(?:\n\n|\Z)', 
                                 report_content, re.IGNORECASE | re.DOTALL)
    if rationale_match:
        rationale_text = rationale_match.group(1).strip()
        # Clean markdown artifacts
        rationale_text = rationale_text.replace("**", "").replace("__", "").strip(":* \n")
        signal["rationale"] = rationale_text[:200]
    
    return signal


def _validate_signal(signal: dict) -> bool:
    """Validate that trade levels are mathematically consistent."""
    action = signal.get("action", "HOLD")
    entry = signal.get("entry", 0)
    sl = signal.get("stop_loss", 0)
    tp1 = signal.get("tp1", 0)
    
    # Must have at least entry and one TP
    if entry <= 0 or tp1 <= 0:
        return False
    
    if action == "BUY":
        # SL < Entry < TP1 (TP2, TP3 are optional but must be > TP1 if set)
        if sl > 0 and sl >= entry:
            return False
        if tp1 <= entry:
            return False
        if signal.get("tp2", 0) > 0 and signal["tp2"] <= tp1:
            return False
        if signal.get("tp3", 0) > 0 and signal["tp3"] <= signal.get("tp2", tp1):
            return False
        return True
    
    elif action == "SELL":
        # SL > Entry > TP1
        if sl > 0 and sl <= entry:
            return False
        if tp1 >= entry:
            return False
        if signal.get("tp2", 0) > 0 and signal["tp2"] >= tp1:
            return False
        if signal.get("tp3", 0) > 0 and signal["tp3"] >= signal.get("tp2", tp1):
            return False
        return True
    
    return True  # HOLD is always valid


def compute_rr_ratio(signal: dict) -> float:
    """Compute the Risk/Reward ratio for a signal."""
    entry = signal.get("entry", 0)
    sl = signal.get("stop_loss", 0)
    tp1 = signal.get("tp1", 0)
    
    if entry <= 0 or sl <= 0 or tp1 <= 0:
        return 0.0
    
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    
    if risk == 0:
        return 0.0
    
    return round(reward / risk, 2)


def format_telegram_trade_signal(ticker: str, analysis_date: str, report_content: str, llm=None, extracted_signal: dict = None) -> str:
    """
    Extracts structured signal data and formats a premium Telegram message.
    
    Args:
        ticker: Stock/crypto ticker
        analysis_date: Date of analysis
        report_content: Raw Risk Judge output
        llm: Optional LLM for structured extraction (much more reliable)
        extracted_signal: Pre-extracted signal array to avoid duplication
    """
    signal = extracted_signal if extracted_signal else extract_signal_from_report(report_content, llm=llm)
    
    action = signal["action"]
    entry = signal["entry"]
    sl = signal["stop_loss"]
    tp1 = signal["tp1"]
    tp2 = signal["tp2"]
    tp3 = signal["tp3"]
    rationale = signal["rationale"]
    is_valid = signal["valid"]
    
    # Action emoji
    if action == "BUY":
        action_emoji = "🟢"
        action_label = "BUY"
    elif action == "SELL":
        action_emoji = "🔴"
        action_label = "SELL"
    else:
        action_emoji = "⚪"
        action_label = "HOLD"
    
    # Validity indicator
    if is_valid:
        validity = "✅ Validé"
    else:
        validity = "⚠️ Niveaux non vérifiés"
    
    # Risk/Reward
    rr = compute_rr_ratio(signal)
    rr_label = ""
    if rr >= 2.5:
        rr_label = "⚡ HIGH R/R"
    elif rr >= 1.5:
        rr_label = "✅ Bon R/R"
    elif rr > 0:
        rr_label = f"📊 R/R: {rr}"
    
    # Build message
    msg = f"🔔 *SIGNAL TRADING*\n\n"
    msg += f"📊 *{ticker}* — {action_label} {action_emoji}\n"
    msg += f"📅 {analysis_date}\n\n"
    
    if action != "HOLD":
        if entry > 0:
            msg += f"💰 Entry: `${entry:.2f}`\n"
        if sl > 0:
            msg += f"🛑 Stop Loss: `${sl:.2f}`\n"
        if tp1 > 0:
            msg += f"🎯 TP1: `${tp1:.2f}`\n"
        if tp2 > 0:
            msg += f"🎯 TP2: `${tp2:.2f}`\n"
        if tp3 > 0:
            msg += f"🎯 TP3: `${tp3:.2f}`\n"
        
        msg += f"\n"
        msg += f"{validity}\n"
        if rr_label:
            msg += f"{rr_label}\n"
    else:
        msg += f"📝 Pas de position recommandée.\n"
    
    if rationale:
        # Truncate rationale to keep Telegram message readable
        short_rationale = rationale[:200]
        if len(rationale) > 200:
            short_rationale += "..."
        msg += f"\n📝 _{short_rationale}_\n"
    
    return msg


def send_telegram_performance_report(report_data: dict) -> bool:
    """Send a summary of past signals performance to Telegram."""
    total_evaluated = report_data.get("total_evaluated", 0)
    if total_evaluated == 0:
        return False
        
    wins = report_data.get("wins", 0)
    losses = report_data.get("losses", 0)
    pending = report_data.get("pending", 0)
    win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
    
    msg = f"📈 *Rapport de Performance Hebdomadaire*\n\n"
    msg += f"Total Évalués: {total_evaluated}\n"
    msg += f"✅ Gagnants (TP atteint): {wins}\n"
    msg += f"❌ Perdants (SL atteint): {losses}\n"
    msg += f"⏳ En cours: {pending}\n\n"
    msg += f"🎯 *Win Rate Effectif: {win_rate:.1f}%*"
    
    return send_telegram_message(msg)
