import sys
import os
import asyncio

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scanner_engine import ScannerEngine
from templates.telegram_signal_template import format_signal_message

async def main():
    scanner = ScannerEngine()
    print("Testing pure technical scan on BBCA (interval=60m)...")
    sig = await scanner.scan_single("BBCA", run_llm=False, override_interval="60m", pure_technical=True)
    if not sig:
        print("Error: scan_single returned None")
        return False

    print(f"Ticker: {sig.ticker}")
    print(f"Signal: {sig.signal}, Score: {sig.raw_score}, Confidence: {sig.confidence_score}")
    print(f"Category Scores: {sig.category_scores}")
    
    # Assert category weights in pure technical mode
    assert sig.category_scores.get("bandarmology", 0) == 0, "Bandarmology score must be 0"
    assert sig.category_scores.get("foreign_flow", 0) == 0, "Foreign Flow score must be 0"

    sig_dict = scanner.signal_to_dict(sig)
    msg = format_signal_message(sig_dict)
    
    assert "Saham: BBCA 🔴 NON-SYARIAH" in msg
    assert "Signal:" in msg
    assert "📊 Technical:" in msg
    assert "- MACD:" in msg
    assert "- RSI (14):" in msg
    assert "🏦 Bandarmology: Data sedang maintenance" in msg
    assert "📈 Beta:" in msg

    print("\n--- FORMATTED MESSAGE PREVIEW ---")
    # Clean print without console encoding crash
    print(msg.encode("ascii", errors="replace").decode("ascii"))
    print("\n[PASS] All pure technical test assertions succeeded!")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        sys.exit(1)
