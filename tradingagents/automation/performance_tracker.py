import os
import json
import datetime
import pandas as pd
import ast
from tradingagents.agents.utils.agent_utils import get_stock_data

# Disable printing inside specific tool calls if needed
import io
import sys

class PerformanceTracker:
    def __init__(self, filename="signals_history.json"):
        # Put it in standard reports/data folder if desired, here we use data_cache or same folder
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.filepath = os.path.join(base_dir, "..", "dataflows", "data_cache", filename)
        
        # Ensure dir exists
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.load_history()

    def load_history(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.signals = json.load(f)
            except Exception:
                self.signals = []
        else:
            self.signals = []

    def save_history(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.signals, f, indent=4)

    def add_signal(self, ticker: str, date: str, signal_dict: dict):
        if signal_dict.get("action", "HOLD").upper() == "HOLD":
            return # Don't track holds
            
        new_signal = {
            "ticker": ticker,
            "date": date,
            "action": signal_dict.get("action", "BUY"),
            "entry": signal_dict.get("entry", 0),
            "stop_loss": signal_dict.get("stop_loss", 0),
            "tp1": signal_dict.get("tp1", 0),
            "tp2": signal_dict.get("tp2", 0),
            "tp3": signal_dict.get("tp3", 0),
            "status": "PENDING" # Can be WIN, LOSS, PENDING
        }
        self.signals.append(new_signal)
        self.save_history()

    def evaluate_past_signals(self) -> dict:
        total = 0
        wins = 0
        losses = 0
        pending = 0
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Evaluate up to 30 days old signals
        for sig in self.signals:
            if sig.get("status") != "PENDING":
                if sig.get("status") == "WIN":
                    wins += 1
                elif sig.get("status") == "LOSS":
                    losses += 1
                total += 1
                continue
                
            sig_date = sig.get("date")
            try:
                # If signal is too old or just today we do checks...
                # skip if it's generated today
                if sig_date == today:
                    pending += 1
                    total += 1
                    continue
                    
                # Fetch data since the signal date
                ticker = sig.get("ticker", "")
                
                # Suppress prints from get_stock_data
                save_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    df_str = get_stock_data.invoke({"symbol": ticker, "start_date": sig_date, "end_date": today})
                finally:
                    sys.stdout = save_stdout
                    
                if not df_str or "Error" in df_str or len(df_str) < 50:
                    pending += 1
                    total += 1
                    continue
                    
                df = pd.DataFrame(ast.literal_eval(df_str))
                
                # Check outcome based on high low
                action = sig.get("action", "BUY").upper()
                sl = float(sig.get("stop_loss", 0))
                tp1 = float(sig.get("tp1", 0))
                
                result = "PENDING"
                # Iterate rows sequentially
                for index, row in df.iterrows():
                    high = float(row.get("High", 0))
                    low = float(row.get("Low", 0))
                    
                    if action == "BUY":
                        if low <= sl:
                            result = "LOSS"
                            break
                        if high >= tp1:
                            result = "WIN"
                            break
                    elif action == "SELL":
                        if high >= sl:
                            result = "LOSS"
                            break
                        if low <= tp1:
                            result = "WIN"
                            break
                
                if result != "PENDING":
                    sig["status"] = result
                    if result == "WIN":
                        wins += 1
                    else:
                        losses += 1
                else:
                    pending += 1
                total += 1
                
            except Exception as e:
                pending += 1
                total += 1
                continue
                
        self.save_history()
        
        return {
            "total_evaluated": total,
            "wins": wins,
            "losses": losses,
            "pending": pending
        }

if __name__ == "__main__":
    tracker = PerformanceTracker()
    print("Local History Count:", len(tracker.signals))
    res = tracker.evaluate_past_signals()
    print("Evaluation:", res)
