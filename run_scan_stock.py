import asyncio
import argparse
import sys
import os
from dotenv import load_dotenv

# Add current path to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from services.scanner_engine import ScannerEngine
from templates.telegram_signal_template import format_signal_message
from app.config import get_settings
from services.stock_universe_service import get_stock_by_ticker

async def main():
    parser = argparse.ArgumentParser(description="Scan a specific stock ticker using Saber Trader Scanner Engine")
    parser.add_argument("ticker", nargs="?", type=str, help="Stock ticker symbol (e.g., BBCA, TLKM, ASII)")
    parser.add_argument("-i", "--interval", type=str, default=None, help="OHLCV interval override (e.g., 1d, 60m, 15m)")
    parser.add_argument("-t", "--telegram", action="store_true", help="Send signal result to Telegram")
    parser.add_argument("--no-llm", action="store_true", help="Skip Gemini LLM analysis for faster scan")
    
    args = parser.parse_args()
    
    ticker = args.ticker
    if not ticker:
        ticker = input("Masukkan kode saham (ticker) yang ingin di-scan (contoh: BBCA): ").strip().upper()
    else:
        ticker = ticker.upper()
        
    if not ticker:
        print("Error: Kode saham tidak boleh kosong.")
        return

    # Check if stock exists in universe or list
    stock_info = get_stock_by_ticker(ticker)
    if not stock_info:
        print(f"Peringatan: Saham {ticker} tidak ditemukan di daftar universe standard. Mencoba scan langsung...")

    print(f"\n[SCAN] Memulai pemindaian untuk saham: {ticker} ...")
    
    settings = get_settings()
    interval = args.interval if args.interval else settings.CHART_INTERVAL
    print(f"[INFO] Interval: {interval}")
    print(f"[INFO] LLM Analysis (Gemini): {'OFF' if args.no_llm else 'ON'}")
    
    scanner = ScannerEngine()
    
    try:
        # scan_single returns SignalOutput or raises ValueError
        res = await scanner.scan_single(ticker, run_llm=not args.no_llm, override_interval=interval)
        
        if not res:
            print(f"[ERROR] Gagal memindai {ticker}. Silakan periksa log atau pastikan kode saham benar.")
            return
            
        print("\n" + "="*50)
        print(f"HASIL SCANNING UNTUK {ticker} ({res.name})")
        print("="*50)
        print(f"SIGNAL          : {res.signal}")
        print(f"RAW SCORE       : {res.raw_score}/100")
        print(f"CONFIDENCE SCORE: {res.confidence_score}/10 ({res.confidence_label})")
        print(f"ENTRY PRICE     : Rp{res.entry_price:,.0f}")
        print(f"TARGET PRICE 1  : Rp{res.tp1:,.0f}")
        print(f"TARGET PRICE 2  : Rp{res.tp2:,.0f}")
        print(f"TARGET PRICE 3  : Rp{res.tp3:,.0f}")
        print(f"STOP LOSS ATR   : Rp{res.stop_loss_atr:,.0f}")
        print(f"STOP LOSS MOD   : Rp{res.stop_loss_moderate:,.0f}")
        print(f"RISK-REWARD RATIO: {res.risk_reward_ratio:.2f}")
        print("-"*50)
        
        # Print breakdown
        print("SCORE BREAKDOWN:")
        cat_scores = res.category_scores or {}
        for cat, score in cat_scores.items():
            print(f"  - {cat.replace('_', ' ').title()}: {score:.1f}")
            
        # Bandarmology & Foreign flow
        bandar_sig = res.bandarmology_summary.get("bandar_signal", "neutral")
        ff_sig = res.foreign_flow_summary.get("ff_signal", "neutral")
        print(f"\nBANDARMOLOGY    : {bandar_sig.upper()}")
        print(f"FOREIGN FLOW    : {ff_sig.upper()}")
        
        # Patterns
        patterns = res.pattern_summary.get("patterns", [])
        candles = res.candle_summary.get("candle_patterns", [])
        if patterns:
            print(f"CHART PATTERNS  : {', '.join(patterns)}")
        if candles:
            print(f"CANDLE PATTERNS : {', '.join(candles)}")
            
        # Analyst Opinion
        if res.analyst_opinion:
            print("\nOPINI ANALIS / FINAL REASONING:")
            # Use safe printing for Windows console to handle any emoji/unicode in Gemini response
            try:
                print(res.analyst_opinion)
            except UnicodeEncodeError:
                print(res.analyst_opinion.encode('ascii', 'ignore').decode('ascii'))
            
        print("="*50)
        
        # Save to DB info
        if not args.no_llm:
            print("[INFO] Data hasil analisis visual telah disimpan ke database (idx_signal_bot.db).")
            
        # Telegram dispatch
        if args.telegram:
            if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
                print("\n[TELEGRAM] Mengirim sinyal ke Telegram...")
                from telegram import Bot
                from jobs.scheduler import send_telegram_with_retry
                
                bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                thread_id = getattr(settings, "TELEGRAM_MESSAGE_THREAD_ID", None)
                thread_id = int(thread_id) if thread_id else None
                
                signal_dict = scanner.signal_to_dict(res)
                full_msg = format_signal_message(signal_dict)
                
                chart_path = getattr(res, 'chart_path', None)
                if chart_path and os.path.exists(chart_path):
                    caption_text = f"📈 <b>Grafik Analisis Teknikal {res.ticker}</b> — Saber Trader"
                    with open(chart_path, "rb") as photo:
                        await send_telegram_with_retry(
                            bot, settings.TELEGRAM_CHAT_ID, photo=photo,
                            caption=caption_text, message_thread_id=thread_id
                        )
                
                sent = await send_telegram_with_retry(bot, settings.TELEGRAM_CHAT_ID, text=full_msg, message_thread_id=thread_id)
                if sent:
                    print("[TELEGRAM] Sinyal berhasil dikirim ke Telegram!")
                else:
                    print("[TELEGRAM] Gagal mengirim sinyal ke Telegram.")
            else:
                print("\n[WARNING] Telegram tidak terkonfigurasi di file .env. Lewati pengiriman Telegram.")
                
    except ValueError as ve:
        print(f"\n[ERROR] ValueError: {ve}")
    except Exception as e:
        print(f"\n[ERROR] Terjadi kesalahan saat memproses: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
