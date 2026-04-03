"""Quick test for the notification signal extraction logic."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.dataflows.notifications import (
    extract_signal_from_report,
    format_telegram_trade_signal,
    _validate_signal,
    compute_rr_ratio,
)

# Test 1: Well-formed BUY signal
report_buy = (
    "**Action**: BUY\n"
    "**Entry Point**: $50.38\n"
    "**Stop Loss (SL)**: $46.00\n"
    "**Take Profit 1 (TP1)**: $54.00\n"
    "**Take Profit 2 (TP2)**: $58.00\n"
    "**Take Profit 3 (TP3)**: $62.00\n"
    "**Rationale**: Strong bullish momentum confirmed by MACD crossover."
)
sig = extract_signal_from_report(report_buy)
print(f"Test 1 (BUY): action={sig['action']}, entry={sig['entry']}, sl={sig['stop_loss']}, tp1={sig['tp1']}, valid={sig['valid']}")
assert sig['valid'] == True, f"BUY should be valid, got {sig}"
assert sig['entry'] == 50.38, f"Entry should be 50.38, got {sig['entry']}"
print("  PASSED")

# Test 2: Incoherent BUY where TP < Entry (the NFLX bug from the logs)
report_bad = (
    "**Action**: BUY\n"
    "**Entry Point**: $98.66\n"
    "**Stop Loss (SL)**: $88.17\n"
    "**Take Profit 1 (TP1)**: $94.66\n"
    "**Take Profit 2 (TP2)**: $90.00\n"
    "**Take Profit 3 (TP3)**: $85.00\n"
)
sig2 = extract_signal_from_report(report_bad)
print(f"Test 2 (Bad BUY): action={sig2['action']}, entry={sig2['entry']}, tp1={sig2['tp1']}, valid={sig2['valid']}")
assert sig2['valid'] == False, f"Incoherent BUY should be INVALID, got {sig2}"
print("  PASSED")

# Test 3: Valid SELL signal
report_sell = (
    "**Action**: SELL\n"
    "**Entry Point**: $98.66\n"
    "**Stop Loss (SL)**: $105.00\n"
    "**Take Profit 1 (TP1)**: $94.00\n"
    "**Take Profit 2 (TP2)**: $90.00\n"
    "**Take Profit 3 (TP3)**: $85.00\n"
)
sig3 = extract_signal_from_report(report_sell)
print(f"Test 3 (SELL): action={sig3['action']}, entry={sig3['entry']}, valid={sig3['valid']}")
assert sig3['valid'] == True, f"SELL should be valid, got {sig3}"
print("  PASSED")

# Test 4: R/R ratio
rr = compute_rr_ratio(sig)
print(f"Test 4 (R/R): {rr}")
assert rr > 0, "R/R should be positive"
print("  PASSED")

# Test 5: Format Telegram message
msg = format_telegram_trade_signal('INTC', '2026-04-03', report_buy)
print(f"\nTest 5 (Telegram format):")
print(msg)
assert "INTC" in msg
assert "BUY" in msg
assert "$50.38" in msg
print("  PASSED")

# Test 6: Bad signal gets warning in Telegram
msg2 = format_telegram_trade_signal('NFLX', '2026-04-03', report_bad)
print(f"\nTest 6 (Bad signal Telegram):")
print(msg2)
assert "non" in msg2.lower() or "warning" in msg2.lower() or "N/A" in msg2 or "pas" in msg2.lower()
print("  PASSED")

print("\n" + "="*50)
print("ALL TESTS PASSED!")
