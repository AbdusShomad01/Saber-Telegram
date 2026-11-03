"""
IDX AI Signal Bot - Telegram Bot
Handles all Telegram bot commands and message delivery.
"""

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from app.config import get_settings
from services.scanner_engine import ScannerEngine
from services.backtest_engine import BacktestEngine
from services.data_provider_service import DataProviderService
from services.stock_universe_service import validate_ticker, get_all_sectors
from templates.telegram_signal_template import (
    format_signal_message,
    format_scan_summary,
    format_backtest_report,
)

logger = logging.getLogger(__name__)
settings = get_settings()

scanner = ScannerEngine()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    msg = """
🤖 <b>Saber Trader — AI Stock Signal Bot</b>

Selamat datang! Saya adalah bot sinyal saham IDX yang menggunakan scoring engine deterministik.

Gunakan tombol di bawah ini atau ketik perintah seperti <code>/signal BBCA</code> atau <code>/scan</code>.

⚠️ <i>Disclaimer: Bukan ajakan beli/jual saham. Selalu DYOR.</i>
"""
    keyboard = [
        [InlineKeyboardButton("🔍 Full Scan", callback_data="btn_scan"), InlineKeyboardButton("🏆 Top 10 Signals", callback_data="btn_top")],
        [InlineKeyboardButton("📊 Sector List", callback_data="btn_sector"), InlineKeyboardButton("❓ Help", callback_data="btn_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(msg.strip(), reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(msg.strip(), reply_markup=reply_markup, parse_mode="HTML")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    msg = """
📖 <b>Panduan Saber Trader Bot</b>

<b>Perintah Utama:</b>
/scan — Scan penuh seluruh saham, tampilkan top signals
/signal [TICKER] — Analisis detail untuk 1 saham
/top — Top 10 sinyal terbaik hari ini
/sector [NAMA] — Scan per sektor (Financials, Energy, dll)
/backtest [TICKER] — Backtest performa sinyal

<b>Contoh:</b>
<code>/signal BBCA</code>
<code>/sector Financials</code>
<code>/backtest BMRI</code>

<b>Cara Baca Signal:</b>
🟢🟢 STRONG BUY — Setup sangat kuat
🟢 BUY — Setup solid untuk entry
🟡 WATCHLIST — Menarik, pantau dulu
🟠 AVOID — Kurang mendukung
🔴 SELL — Bearish, keluar posisi

<b>Scoring Engine:</b>
Score berbasis 100 poin dari 7 kategori deterministik.
AI hanya digunakan untuk menulis opini, BUKAN keputusan.
"""
    await update.message.reply_text(msg.strip(), parse_mode="HTML")


async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /signal TICKER command."""
    import os
    if not context.args:
        await update.message.reply_text("❌ Usage: <code>/signal BBCA</code>", parse_mode="HTML")
        return

    ticker = context.args[0].upper().strip()
    if not validate_ticker(ticker):
        await update.message.reply_text(f"❌ Ticker <b>{ticker}</b> tidak ditemukan.", parse_mode="HTML")
        return

    await update.message.reply_text(f"⏳ Menganalisis <b>{ticker}</b>...", parse_mode="HTML")

    try:
        signal = await scanner.scan_single(ticker)
        if signal:
            signal_dict = scanner.signal_to_dict(signal)
            msg = format_signal_message(signal_dict)
            
            # Send visual chart photo if generated
            chart_path = signal_dict.get("chart_path")
            if chart_path and os.path.exists(chart_path):
                caption = f"📈 <b>Grafik Analisis Teknikal {ticker}</b> — Saber Trader"
                try:
                    with open(chart_path, "rb") as photo:
                        await update.message.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
                except Exception as photo_err:
                    logger.error(f"Failed to send chart photo: {photo_err}")
                    
            await update.message.reply_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text(
                f"⚠️ <b>{ticker}</b> gagal diproses. Kemungkinan karena data saham rusak atau error tidak terduga.",
                parse_mode="HTML",
            )
    except ValueError as ve:
        # Expected errors like data not found
        await update.message.reply_text(f"❌ <b>{ticker}</b>: {str(ve)}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Signal command error: {e}")
        await update.message.reply_text(f"❌ Error sistem: {str(e)[:200]}")


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command — full market scan."""
    await update.message.reply_text("⏳ Memulai scan seluruh saham IDX... (ini bisa memakan waktu)")

    try:
        signals = await scanner.scan_all()
        if signals:
            summary_data = [scanner.signal_to_dict(s) for s in signals]
            msg = format_scan_summary(summary_data)
            await update.message.reply_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text("📊 Tidak ada saham yang memenuhi kriteria (WATCHLIST / BUY / STRONG BUY).")
    except Exception as e:
        logger.error(f"Scan command error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /top — show top signals."""
    await update.message.reply_text("⏳ Mencari top signals...")

    try:
        signals = await scanner.scan_all()
        buy_signals = [s for s in signals if s.signal in ("BUY", "STRONG BUY")]
        if buy_signals:
            summary_data = [scanner.signal_to_dict(s) for s in buy_signals[:10]]
            msg = format_scan_summary(summary_data)
            await update.message.reply_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text("📊 Tidak ada saham yang memenuhi kriteria BUY / STRONG BUY hari ini.")
    except Exception as e:
        logger.error(f"Top command error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def cmd_sector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sector command."""
    if not context.args:
        sectors = get_all_sectors()
        msg = "📊 <b>Available Sectors:</b>\n\n"
        for s in sorted(sectors):
            msg += f"• {s}\n"
        msg += "\nUsage: <code>/sector Financials</code>"
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    sector = " ".join(context.args)
    await update.message.reply_text(f"⏳ Scanning sektor <b>{sector}</b>...", parse_mode="HTML")

    try:
        signals = await scanner.scan_sector(sector, top_n=5)
        if signals:
            summary_data = [scanner.signal_to_dict(s) for s in signals]
            msg = format_scan_summary(summary_data)
            await update.message.reply_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text(f"📊 Tidak ada sinyal untuk sektor {sector}.")
    except Exception as e:
        logger.error(f"Sector command error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def cmd_backtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /backtest TICKER command."""
    if not context.args:
        await update.message.reply_text("❌ Usage: <code>/backtest BBCA</code>", parse_mode="HTML")
        return

    ticker = context.args[0].upper().strip()
    if not validate_ticker(ticker):
        await update.message.reply_text(f"❌ Ticker <b>{ticker}</b> tidak ditemukan.", parse_mode="HTML")
        return

    await update.message.reply_text(f"⏳ Running backtest untuk <b>{ticker}</b>...", parse_mode="HTML")

    try:
        dp = DataProviderService()
        ohlcv = dp.get_ohlcv(ticker, period_days=365)

        bt = BacktestEngine()
        report = bt.run(ticker=ticker, ohlcv_df=ohlcv)
        report_dict = bt.report_to_dict(report)
        msg = format_backtest_report(report_dict)
        await update.message.reply_text(msg, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Backtest command error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button clicks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    message = query.message
    
    if data == "btn_scan":
        await message.reply_text("⏳ Memulai scan seluruh saham IDX... (ini bisa memakan waktu)")
        try:
            signals = await scanner.scan_all()
            if signals:
                summary_data = [scanner.signal_to_dict(s) for s in signals]
                msg = format_scan_summary(summary_data)
                await message.reply_text(msg, parse_mode="HTML")
            else:
                await message.reply_text("📊 Tidak ada saham yang memenuhi kriteria (WATCHLIST / BUY / STRONG BUY).")
        except Exception as e:
            logger.error(f"Scan command error: {e}")
            await message.reply_text(f"❌ Error: {str(e)[:200]}")
            
    elif data == "btn_top":
        await message.reply_text("⏳ Mencari top signals...")
        try:
            signals = await scanner.scan_all()
            buy_signals = [s for s in signals if s.signal in ("BUY", "STRONG BUY")]
            if buy_signals:
                summary_data = [scanner.signal_to_dict(s) for s in buy_signals[:10]]
                msg = format_scan_summary(summary_data)
                await message.reply_text(msg, parse_mode="HTML")
            else:
                await message.reply_text("📊 Tidak ada saham yang memenuhi kriteria BUY / STRONG BUY hari ini.")
        except Exception as e:
            logger.error(f"Top command error: {e}")
            await message.reply_text(f"❌ Error: {str(e)[:200]}")
            
    elif data == "btn_sector":
        sectors = get_all_sectors()
        msg = "📊 <b>Available Sectors:</b>\n\n"
        for s in sorted(sectors):
            msg += f"• {s}\n"
        msg += "\nKetik <code>/sector [NAMA]</code> untuk memindai."
        await message.reply_text(msg, parse_mode="HTML")
        
    elif data == "btn_help":
        # Call the existing help logic by faking the update message
        await cmd_help(update, context)

def safe_handler(handler_func):
    import functools
    @functools.wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Patch reply methods on message
        if update.message:
            orig_reply_text = update.message.reply_text
            orig_reply_photo = update.message.reply_photo
            
            async def safe_reply_text(*args_inner, **kwargs_inner):
                try:
                    return await orig_reply_text(*args_inner, **kwargs_inner)
                except Exception as e:
                    if "message to be replied not found" in str(e).lower():
                        return await context.bot.send_message(chat_id=update.effective_chat.id, *args_inner, **kwargs_inner)
                    raise e
                    
            async def safe_reply_photo(*args_inner, **kwargs_inner):
                try:
                    return await orig_reply_photo(*args_inner, **kwargs_inner)
                except Exception as e:
                    if "message to be replied not found" in str(e).lower():
                        return await context.bot.send_photo(chat_id=update.effective_chat.id, *args_inner, **kwargs_inner)
                    raise e
            
            try:
                update.message.reply_text = safe_reply_text
                update.message.reply_photo = safe_reply_photo
            except AttributeError:
                pass
                
        if update.callback_query and update.callback_query.message:
            orig_reply_text = update.callback_query.message.reply_text
            orig_reply_photo = update.callback_query.message.reply_photo
            
            async def safe_reply_text(*args_inner, **kwargs_inner):
                try:
                    return await orig_reply_text(*args_inner, **kwargs_inner)
                except Exception as e:
                    if "message to be replied not found" in str(e).lower():
                        return await context.bot.send_message(chat_id=update.effective_chat.id, *args_inner, **kwargs_inner)
                    raise e
                    
            async def safe_reply_photo(*args_inner, **kwargs_inner):
                try:
                    return await orig_reply_photo(*args_inner, **kwargs_inner)
                except Exception as e:
                    if "message to be replied not found" in str(e).lower():
                        return await context.bot.send_photo(chat_id=update.effective_chat.id, *args_inner, **kwargs_inner)
                    raise e
            
            try:
                update.callback_query.message.reply_text = safe_reply_text
                update.callback_query.message.reply_photo = safe_reply_photo
            except AttributeError:
                pass

        try:
            return await handler_func(update, context, *args, **kwargs)
        except Exception as e:
            if "message to be replied not found" in str(e).lower():
                logger.warning("Handled 'message to be replied not found' in wrapper.")
            else:
                raise e
    return wrapper

def create_bot_app() -> Application:
    """Create and configure the Telegram bot application."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", safe_handler(cmd_start)))
    app.add_handler(CommandHandler("help", safe_handler(cmd_help)))
    app.add_handler(CommandHandler("signal", safe_handler(cmd_signal)))
    app.add_handler(CommandHandler("signa", safe_handler(cmd_signal)))
    app.add_handler(CommandHandler("signals", safe_handler(cmd_signal)))
    app.add_handler(CommandHandler("scan", safe_handler(cmd_scan)))
    app.add_handler(CommandHandler("top", safe_handler(cmd_top)))
    app.add_handler(CommandHandler("sector", safe_handler(cmd_sector)))
    app.add_handler(CommandHandler("backtest", safe_handler(cmd_backtest)))
    app.add_handler(CallbackQueryHandler(safe_handler(handle_button)))

    logger.info("Telegram bot configured with all command handlers (including aliases)")
    return app


if __name__ == "__main__":
    import sys
    import os
    # Add project root to path if needed
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    logger.info("🚀 Starting Saber Trader Telegram Bot in polling mode...")
    bot_app = create_bot_app()
    bot_app.run_polling(drop_pending_updates=True)
