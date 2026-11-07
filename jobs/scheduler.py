"""
IDX AI Signal Bot - Scheduler
Defines all scheduled tasks using APScheduler.

v2 Improvements:
- Telegram retry with exponential backoff
- Delay between messages to avoid rate limit
- Signal tracking job (auto follow-up at 16:30 WIB)
- Bullish-only signal filtering
"""

import logging
import asyncio
import os
import json
import socket
from datetime import datetime

# Force IPv4 untuk bypass issue blackhole IPv6 di VPS Biznet / ISP Indonesia
try:
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = _ipv4_getaddrinfo
except Exception:
    pass

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.scanner_engine import ScannerEngine
from services.data_provider_service import DataProviderService
from services.outcome_tracker import (
    migrate_add_outcome_columns, get_pending_signals,
    update_signal_outcome, get_winrate_stats, expire_old_pending_signals
)
from templates.telegram_signal_template import format_scan_summary

logger = logging.getLogger(__name__)


# ================================================================== #
#  Telegram Send Helper — with requests & retry
# ================================================================== #

def send_telegram_direct_requests(token, chat_id, text=None, photo=None, caption=None,
                                   parse_mode="HTML", message_thread_id=None, timeout=25):
    """Kirim pesan Telegram via library requests yang stabil menangani TLS renegotiation."""
    import requests
    try:
        if photo:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            data = {"chat_id": chat_id, "caption": caption or "", "parse_mode": parse_mode}
            if message_thread_id:
                data["message_thread_id"] = int(message_thread_id)
            if isinstance(photo, str) and os.path.exists(photo):
                with open(photo, "rb") as f:
                    r = requests.post(url, data=data, files={"photo": f}, timeout=timeout)
            else:
                data["photo"] = photo
                r = requests.post(url, data=data, timeout=timeout)
            return r.status_code == 200
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
            if message_thread_id:
                payload["message_thread_id"] = int(message_thread_id)
            r = requests.post(url, json=payload, timeout=timeout)
            return r.status_code == 200
    except Exception as ex:
        logger.warning(f"[Telegram Direct Requests] error: {ex}")
        return False


async def send_telegram_with_retry(bot, chat_id, text=None, photo=None, caption=None,
                                    parse_mode="HTML", message_thread_id=None, max_retries=3):
    """
    Send a Telegram message or photo with retry logic and exponential backoff.
    Returns True if sent successfully, False otherwise.
    """
    token = getattr(bot, "token", None) if hasattr(bot, "token") else (bot if isinstance(bot, str) else None)
    for attempt in range(max_retries):
        try:
            # 1. Coba via direct requests (paling stabil terhadap TLS renegotiation)
            if token:
                success = await asyncio.to_thread(
                    send_telegram_direct_requests,
                    token=token,
                    chat_id=chat_id,
                    text=text,
                    photo=photo,
                    caption=caption,
                    parse_mode=parse_mode,
                    message_thread_id=message_thread_id,
                    timeout=25,
                )
                if success:
                    return True
                else:
                    logger.warning(f"Telegram requests attempt {attempt + 1}/{max_retries} failed, trying bot client...")

            # 2. Fallback ke async bot client
            if photo:
                await bot.send_photo(
                    chat_id=chat_id,
                    message_thread_id=message_thread_id,
                    photo=photo,
                    caption=caption,
                    parse_mode=parse_mode,
                    read_timeout=30.0,
                    write_timeout=30.0,
                    connect_timeout=30.0,
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=message_thread_id,
                    text=text,
                    parse_mode=parse_mode,
                    read_timeout=30.0,
                    write_timeout=30.0,
                    connect_timeout=30.0,
                )
            return True
        except Exception as e:
            error_str = str(e).lower()
            if "too many requests" in error_str or "retry after" in error_str or "429" in error_str:
                wait = (2 ** attempt) * 5
                logger.warning(f"Telegram rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {wait}s...")
                await asyncio.sleep(wait)
            elif "message is too long" in error_str:
                if text and len(text) > 4096:
                    text = text[:4090] + "\n..."
                    continue
                return False
            elif attempt < max_retries - 1:
                wait = (2 ** attempt) * 2
                logger.warning(f"Telegram send failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                logger.error(f"Telegram send permanently failed after {max_retries} attempts: {e}")
                return False
    return False


# ================================================================== #
#  Scheduler Setup
# ================================================================== #

def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

    from app.config import get_settings
    settings = get_settings()

    # Run DB migration for outcome columns on startup
    try:
        migrate_add_outcome_columns()
    except Exception as e:
        logger.warning(f"[Scheduler] Outcome migration warning: {e}")

    # ── Screener Pagi: Morning Pre-Market scan at 00:01 WIB (Senin-Jumat) ────
    scheduler.add_job(
        job_intraday_scan,
        CronTrigger(day_of_week="mon-fri", hour="0", minute="1", timezone="Asia/Jakarta"),
        id="morning_scan",
        name="Morning Pre-Market Scan",
        replace_existing=True,
        kwargs={"interval_override": "1d"}
    )

    # ── Screener Siang: Noon Intraday Scan (15m - Pure Teknikal) ─────────────
    # Senin - Kamis: 12:05 WIB (setelah Sesi 1 tutup jam 12:00)
    scheduler.add_job(
        job_intraday_scan,
        CronTrigger(day_of_week="mon-thu", hour=12, minute=5, timezone="Asia/Jakarta"),
        id="noon_scan_mon_thu",
        name="Noon Intraday Scan 15m (Mon-Thu 12:05 WIB)",
        replace_existing=True,
        kwargs={"interval_override": "15m", "pure_technical": True}
    )
    # Jumat: 11:35 WIB (setelah Sesi 1 Jumat tutup jam 11:30)
    scheduler.add_job(
        job_intraday_scan,
        CronTrigger(day_of_week="fri", hour=11, minute=35, timezone="Asia/Jakarta"),
        id="noon_scan_fri",
        name="Noon Intraday Scan 15m (Fri 11:35 WIB)",
        replace_existing=True,
        kwargs={"interval_override": "15m", "pure_technical": True}
    )

    # ── Real-Time TP/SL Monitor: Setiap 10 menit saat jam bursa (Senin-Jumat) ───
    scheduler.add_job(
        job_monitor_tp_sl,
        CronTrigger(day_of_week="mon-fri", hour="9-16", minute="*/10", timezone="Asia/Jakarta"),
        id="tp_sl_monitor",
        name="Real-Time TP/SL Monitor (Every 10 min)",
        replace_existing=True,
    )

    # Signal tracking follow-up at 16:30 WIB (before market close)
    scheduler.add_job(
        job_signal_followup,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=30, timezone="Asia/Jakarta"),
        id="signal_followup",
        name="Signal Performance Follow-Up",
        replace_existing=True,
    )

    # Fetch daily data at 16:45 WIB
    scheduler.add_job(
        job_fetch_daily_data,
        CronTrigger(hour=16, minute=45, timezone="Asia/Jakarta"),
        id="fetch_daily",
        name="Fetch Daily OHLCV Data",
        replace_existing=True,
    )

    # Daily SPS signal recap to Google Sheets at 17:02 WIB (Senin-Jumat)
    scheduler.add_job(
        job_sps_recap,
        CronTrigger(day_of_week="mon-fri", hour=17, minute=2, timezone="Asia/Jakarta"),
        id="sps_recap",
        name="Daily SPS Signal Recap to Google Sheets",
        replace_existing=True,
    )

    # Expire old pending signals every night at 20:00 WIB
    scheduler.add_job(
        job_expire_old_signals,
        CronTrigger(hour=20, minute=0, timezone="Asia/Jakarta"),
        id="expire_signals",
        name="Expire Old Pending Signals",
        replace_existing=True,
    )

    # Weekly backtest on Sunday at 08:00 WIB
    scheduler.add_job(
        job_weekly_backtest,
        CronTrigger(day_of_week="sun", hour=8, minute=0, timezone="Asia/Jakarta"),
        id="weekly_backtest",
        name="Weekly Backtest Validation",
        replace_existing=True,
    )

    # Weekly adaptive threshold job (Senin 07:30 WIB) — Fix #6 & #10
    scheduler.add_job(
        job_adaptive_threshold,
        CronTrigger(day_of_week="mon", hour=7, minute=30, timezone="Asia/Jakarta"),
        id="adaptive_threshold",
        name="Adaptive Scoring Threshold Calibration",
        replace_existing=True,
    )

    # Weekly scoring weights optimization job (Minggu 09:00 WIB)
    scheduler.add_job(
        job_optimize_weights,
        CronTrigger(day_of_week="sun", hour=9, minute=0, timezone="Asia/Jakarta"),
        id="scoring_weights_optimization",
        name="Scoring Weights Optimization",
        replace_existing=True,
    )

    # ── BSJP Screener: 15:45 WIB setiap hari bursa ───────────────────────
    scheduler.add_job(
        job_bsjp_scan,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=45, timezone="Asia/Jakarta"),
        id="bsjp_scan",
        name="BSJP Screener 15:45 WIB",
        replace_existing=True,
    )

    # ── BSJP Rekap: 09:30 WIB setiap hari bursa ─────────────────────────
    scheduler.add_job(
        job_bsjp_rekap,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=30, timezone="Asia/Jakarta"),
        id="bsjp_rekap",
        name="BSJP Rekap Pagi 09:30 WIB",
        replace_existing=True,
    )

    logger.info("Scheduler configured with all jobs")
    return scheduler


# ================================================================== #
#  Job: Daily Scan
# ================================================================== #

async def job_daily_scan():
    """Run daily full market scan and send top signals to Telegram."""
    logger.info(f"[Scheduler] Starting daily scan at {datetime.now()}")

    try:
        scanner = ScannerEngine()
        signals = await scanner.scan_all()  # Unlimited quota: kirim semua sinyal bullish yang lolos

        from app.config import get_settings
        settings = get_settings()

        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            import os
            from telegram import Bot

            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            thread_id = getattr(settings, "TELEGRAM_MESSAGE_THREAD_ID", None)
            thread_id = int(thread_id) if thread_id else None

            # Filter: hanya kirim sinyal bullish
            BULLISH_SIGNALS = {"STRONG BUY", "BUY", "WATCHLIST"}
            bullish_signals = [s for s in signals if s.signal in BULLISH_SIGNALS] if signals else []

            if not bullish_signals:
                await send_telegram_with_retry(
                    bot, settings.TELEGRAM_CHAT_ID, message_thread_id=thread_id,
                    text="🌅 <b>DAILY MARKET SCAN</b>\n\n⚠️ Tidak ada saham yang memenuhi kriteria (WATCHLIST / BUY / STRONG BUY).\nMarket sedang lemah, disarankan wait &amp; see.",
                )
                return

            header_msg = f"🌅 <b>DAILY MARKET SCAN COMPLETED</b>\nBerikut adalah {len(bullish_signals)} sinyal bullish terbaik hari ini:"
            await send_telegram_with_retry(bot, settings.TELEGRAM_CHAT_ID, text=header_msg, message_thread_id=thread_id)

            from templates.telegram_signal_template import format_signal_message

            for s in bullish_signals:
                signal_dict = scanner.signal_to_dict(s)
                full_msg = format_signal_message(signal_dict)

                chart_path = getattr(s, 'chart_path', None)
                if chart_path and os.path.exists(chart_path):
                    caption_text = f"📈 <b>Grafik Analisis Teknikal {s.ticker}</b> — Saber Trader"
                    with open(chart_path, "rb") as photo:
                        await send_telegram_with_retry(
                            bot, settings.TELEGRAM_CHAT_ID, photo=photo,
                            caption=caption_text, message_thread_id=thread_id
                        )

                await send_telegram_with_retry(bot, settings.TELEGRAM_CHAT_ID, text=full_msg, message_thread_id=thread_id)

                # Delay between messages to avoid Telegram rate limit
                await asyncio.sleep(1.5)

            logger.info(f"[Scheduler] Sent {len(bullish_signals)} bullish signals with charts to Telegram")
        else:
            logger.warning("[Scheduler] Telegram not configured — skipping send")

    except Exception as e:
        logger.error(f"[Scheduler] Daily scan error: {e}", exc_info=True)


# ================================================================== #
#  Job: Fetch Daily Data
# ================================================================== #

async def job_fetch_daily_data():
    """Fetch and store daily OHLCV data."""
    logger.info(f"[Scheduler] Fetching daily data at {datetime.now()}")

    try:
        from services.stock_universe_service import get_stock_universe

        dp = DataProviderService()
        universe = get_stock_universe()

        for stock in universe:
            try:
                dp.get_ohlcv(stock["ticker"], period_days=5)
            except Exception as e:
                logger.error(f"[Scheduler] Fetch error for {stock['ticker']}: {e}")

        logger.info(f"[Scheduler] Fetched data for {len(universe)} stocks")

    except Exception as e:
        logger.error(f"[Scheduler] Data fetch error: {e}", exc_info=True)


# ================================================================== #
#  Job: Weekly Backtest
# ================================================================== #

async def job_weekly_backtest():
    """Run weekly backtest validation."""
    logger.info(f"[Scheduler] Starting weekly backtest at {datetime.now()}")

    try:
        from services.stock_universe_service import get_stock_universe
        from services.backtest_engine import BacktestEngine

        dp = DataProviderService()
        bt = BacktestEngine()
        universe = get_stock_universe()

        results = []
        for stock in universe[:10]:  # Top 10 stocks only for weekly
            try:
                ohlcv = dp.get_ohlcv(stock["ticker"], period_days=365)
                if len(ohlcv) >= 100:
                    report = bt.run(ticker=stock["ticker"], ohlcv_df=ohlcv)
                    results.append(bt.report_to_dict(report))
            except Exception as e:
                logger.error(f"Backtest error for {stock['ticker']}: {e}")

        logger.info(f"[Scheduler] Completed backtest for {len(results)} stocks")

    except Exception as e:
        logger.error(f"[Scheduler] Weekly backtest error: {e}", exc_info=True)


# ================================================================== #
#  Job: Intraday Scan
# ================================================================== #

async def job_intraday_scan(interval_override: str | None = None, pure_technical: bool | None = None):
    """Run morning pre-market / noon scan and send top signals to Telegram."""
    from app.config import get_settings
    settings = get_settings()

    interval_used = interval_override if interval_override else settings.CHART_INTERVAL
    if pure_technical is None:
        pure_technical = (interval_used in ["60m", "15m", "1h", "30m"])

    mode_str = "PURE TEKNIKAL" if pure_technical else "STANDARD (Teknikal + Bandar + Asing)"
    logger.info(f"[Scheduler] Starting intraday scan at {datetime.now()} with interval {interval_used} [Mode: {mode_str}]")

    try:
        scanner = ScannerEngine()
        signals = await scanner.scan_all(override_interval=interval_override, pure_technical=pure_technical)  # Unlimited quota

        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            import os
            from telegram import Bot

            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            thread_id = getattr(settings, "TELEGRAM_MESSAGE_THREAD_ID", None)
            thread_id = int(thread_id) if thread_id else None

            # Filter: hanya kirim sinyal bullish (STRONG BUY, BUY, WATCHLIST)
            BULLISH_SIGNALS = {"STRONG BUY", "BUY", "WATCHLIST"}
            bullish_signals = [s for s in signals if s.signal in BULLISH_SIGNALS] if signals else []

            if pure_technical:
                scan_name = f"NOON INTRADAY SCAN ({interval_used} — PURE TEKNIKAL)"
                scan_emoji = "☀️"
            else:
                scan_name = "MORNING PRE-MARKET SCAN" if interval_used == "1d" else f"NOON INTRADAY SCAN ({interval_used})"
                scan_emoji = "🌅"

            if not bullish_signals:
                await send_telegram_with_retry(
                    bot, settings.TELEGRAM_CHAT_ID, message_thread_id=thread_id,
                    text=f"{scan_emoji} <b>{scan_name}</b>\n\n⚠️ Tidak ada saham yang memenuhi kriteria (WATCHLIST / BUY / STRONG BUY).\nMarket sedang lemah atau konsolidasi, disarankan wait &amp; see.",
                )
                return

            header_msg = f"{scan_emoji} <b>{scan_name}</b>\nBerikut adalah <b>{len(bullish_signals)} sinyal bullish</b> terbaik:"
            await send_telegram_with_retry(bot, settings.TELEGRAM_CHAT_ID, text=header_msg, message_thread_id=thread_id)

            from templates.telegram_signal_template import format_signal_message

            for s in bullish_signals:
                signal_dict = scanner.signal_to_dict(s)
                signal_dict["pure_technical"] = pure_technical
                full_msg = format_signal_message(signal_dict)

                chart_path = getattr(s, 'chart_path', None)
                if chart_path and os.path.exists(chart_path):
                    caption_text = f"📈 <b>Grafik Analisis Teknikal {s.ticker}</b> — Saber Trader"
                    with open(chart_path, "rb") as photo:
                        await send_telegram_with_retry(
                            bot, settings.TELEGRAM_CHAT_ID, photo=photo,
                            caption=caption_text, message_thread_id=thread_id
                        )

                await send_telegram_with_retry(bot, settings.TELEGRAM_CHAT_ID, text=full_msg, message_thread_id=thread_id)

                # Delay between messages to avoid Telegram rate limit
                await asyncio.sleep(1.5)

            logger.info(f"[Scheduler] Sent {len(bullish_signals)} bullish signals ({'pure technical' if pure_technical else 'standard'}) with charts to Telegram")
        else:
            logger.warning("[Scheduler] Telegram not configured — skipping send")

    except Exception as e:
        logger.error(f"[Scheduler] Intraday scan error: {e}", exc_info=True)


# ================================================================== #
#  Job: Signal Follow-Up (16:30 WIB — Track Performance)
# ================================================================== #

async def job_expire_old_signals():
    """Expire old pending signals every night."""
    logger.info(f"[Scheduler] Expiring old pending signals at {datetime.now()}")
    try:
        from app.config import get_settings
        settings = get_settings()
        max_days = settings.MAX_HOLDING_PERIOD if not settings.DAY_TRADE_MODE else 1
        expire_old_pending_signals(max_hold_days=max_days)
    except Exception as e:
        logger.error(f"[Scheduler] Expire signals error: {e}")


async def job_signal_followup():
    """
    Auto follow-up on today's morning signals.
    Checks current price vs entry price, SAVES outcome to DB, and sends Telegram summary.
    Runs at 16:30 WIB (before market close).
    """
    logger.info(f"[Scheduler] Starting signal follow-up at {datetime.now()}")

    try:
        from datetime import date
        from app.config import get_settings

        settings = get_settings()
        today = date.today().isoformat()
        
        timeframes_to_check = ["1d", "60m"] if settings.DAY_TRADE_MODE else [settings.CHART_INTERVAL]
        
        for current_timeframe in timeframes_to_check:
            # Fix #8: Fetch pending signals dari timeframe yang sedang aktif
            pending = get_pending_signals(days_back=1, timeframe=current_timeframe)
            if not pending:
                logger.info(f"[Scheduler] No pending signals to follow up today for {current_timeframe}.")
                continue

            # Fetch current prices
            dp = DataProviderService()
            results = []
            total_pnl = 0
            wins = 0
            losses = 0

            follow_up_interval = current_timeframe
            follow_up_days = 1 if current_timeframe != "1d" else 2

            for row in pending:
                signal_id = row["id"]
                ticker = row["ticker"]
                signal = row["signal"]
                entry_price = row["entry_price"] or 0
                tp1 = row["tp1"] or 0
                sl_atr = row["stop_loss_atr"] or 0

                # Fix #8: Ambil tp2 dari DB jika ada (kolom mungkin belum ada di data lama)
                tp2 = row.get("tp2", 0) or 0

                try:
                    ohlcv = dp.get_ohlcv(ticker, period_days=follow_up_days, interval=follow_up_interval)
                    if ohlcv.empty:
                        continue

                    current_price = float(ohlcv["close"].iloc[-1])
                    intraday_high = float(ohlcv["high"].max())
                    intraday_low = float(ohlcv["low"].min())
                    
                    # Fix: Ensure entry price was actually hit, especially for WATCHLIST (Buy on Weakness)
                    entry_hit = True
                    if signal == "WATCHLIST" and intraday_low > entry_price:
                        entry_hit = False
                        
                    if not entry_hit:
                        db_status = "PENDING"
                        tg_status = "WAITING ENTRY"
                        pnl_pct = 0.0
                        tp_hit = False
                        tp2_hit = False
                        sl_hit = False
                    else:
                        pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

                        tp_hit = intraday_high >= tp1 if tp1 > 0 else False
                        tp2_hit = intraday_high >= tp2 if tp2 > 0 else False  # Fix #2: cek TP2
                        sl_hit = intraday_low <= sl_atr if sl_atr > 0 else False

                        if tp2_hit and tp_hit:
                            db_status = "TP2_HIT"
                            tg_status = "TP1 + TP2 HIT 💥"
                            pnl_pct = ((tp2 - entry_price) / entry_price) * 100
                            wins += 1
                        elif tp_hit:
                            db_status = "TP_HIT"
                            tg_status = "TP1 HIT"
                            pnl_pct = ((tp1 - entry_price) / entry_price) * 100
                            wins += 1
                        elif sl_hit:
                            db_status = "SL_HIT"
                            tg_status = "SL HIT"
                            pnl_pct = ((sl_atr - entry_price) / entry_price) * 100
                            losses += 1
                        elif pnl_pct > 0:
                            db_status = "PROFIT"
                            tg_status = "PROFIT"
                            wins += 1
                        elif pnl_pct < 0:
                            db_status = "LOSS"
                            tg_status = "LOSS"
                            losses += 1
                        else:
                            db_status = "PENDING"
                            tg_status = "FLAT"

                    # ✅ SAVE OUTCOME TO DATABASE (dengan tp2_hit)
                    update_signal_outcome(
                        signal_id=signal_id,
                        status=db_status,
                        outcome_price=current_price,
                        pnl_pct=pnl_pct,
                        tp_hit=tp_hit,
                        sl_hit=sl_hit,
                        max_price=intraday_high,
                        min_price=intraday_low,
                        tp2_hit=tp2_hit,
                    )

                    total_pnl += pnl_pct
                    results.append({
                        "ticker": ticker, "signal": signal,
                        "entry": entry_price, "current": current_price,
                        "pnl_pct": pnl_pct, "status": tg_status,
                        "tp_hit": tp_hit, "tp2_hit": tp2_hit, "sl_hit": sl_hit,
                    })
                except Exception as e:
                    logger.error(f"[Follow-up] Error checking {ticker}: {e}")

            if not results:
                logger.info("[Scheduler] No follow-up data available.")
                continue

            # Fix #8: Fetch winrate stats filter by timeframe
            stats = get_winrate_stats(days_back=30, timeframe=current_timeframe)
            summary = stats.get("summary", {})
            cumulative_winrate = summary.get("winrate", 0)
            cumulative_total = summary.get("resolved_signals", 0)

            total_signals = len(results)
            avg_pnl = total_pnl / total_signals if total_signals > 0 else 0
            today_winrate = (wins / total_signals * 100) if total_signals > 0 else 0
            overall_emoji = "🟢" if avg_pnl > 0 else ("🔴" if avg_pnl < 0 else "⚪")

            # Timeframe label untuk header
            tf_label = f" [{current_timeframe.upper()}]" if current_timeframe else ""

            msg = f"""📊 <b>SIGNAL PERFORMANCE REPORT{tf_label}</b>
    ━━━━━━━━━━━━━━━━━━━━━━
    📅 Tanggal: <b>{today}</b>
    {overall_emoji} P&amp;L Hari Ini: <b>{avg_pnl:+.2f}%</b>
    🎯 Winrate Hari Ini: <b>{today_winrate:.0f}%</b> ({wins}W / {losses}L)
    📈 Winrate 30 Hari [{current_timeframe}]: <b>{cumulative_winrate:.1f}%</b> ({cumulative_total} sinyal resolved)
    ━━━━━━━━━━━━━━━━━━━━━━
    """
            for r in results:
                if r["tp2_hit"]:
                    emoji = "💥"  # TP1 + TP2 hit
                elif r["tp_hit"]:
                    emoji = "✅"
                elif r["sl_hit"]:
                    emoji = "❌"
                else:
                    emoji = "🟢" if r["pnl_pct"] > 0 else "🔴"
                msg += f"\n{emoji} <b>{r['ticker']}</b> ({r['signal']}) — {r['status']}"
                msg += f"\n   Entry: Rp{r['entry']:,.0f} → Now: Rp{r['current']:,.0f} <b>({r['pnl_pct']:+.2f}%)</b>"

            msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━"
            msg += "\n🤖 <i>Saber Trader AI Signal Bot — Auto Follow-Up</i>"
            msg += f"\n📊 <i>Data disimpan ke database untuk tracking historis [{current_timeframe}]</i>"

            if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
                from telegram import Bot
                bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                thread_id = getattr(settings, "TELEGRAM_MESSAGE_THREAD_ID", None)
                thread_id = int(thread_id) if thread_id else None
                await send_telegram_with_retry(bot, settings.TELEGRAM_CHAT_ID, text=msg, message_thread_id=thread_id)
                logger.info(f"[Scheduler] Sent follow-up + saved outcomes. Avg P&L: {avg_pnl:+.2f}%, Winrate: {today_winrate:.0f}%")
            else:
                logger.warning("[Scheduler] Telegram not configured — skipping follow-up send")

    except Exception as e:
        logger.error(f"[Scheduler] Signal follow-up error: {e}", exc_info=True)


# ================================================================== #
#  Job: Adaptive Threshold Calibration — Fix #6 & #10
# ================================================================== #

async def job_adaptive_threshold():
    """
    Setiap Senin pagi, analisis winrate 30 hari terakhir dari DB.
    Jika winrate terlalu rendah → naikkan threshold BUY (lebih selektif).
    Jika winrate sangat tinggi → bisa sedikit turunkan threshold.
    Hasilnya disimpan ke threshold_config.json & dilaporkan ke Telegram.

    Integrasi dengan scoring_engine.py: ScoringEngine membaca file ini
    untuk menggunakan threshold yang sudah dikalibrasi.
    """
    logger.info(f"[AdaptiveThreshold] Running calibration at {datetime.now()}")

    try:
        import json
        import os
        from app.config import get_settings

        import json
        settings = get_settings()
        
        timeframes_to_check = ["1d", "60m"] if settings.DAY_TRADE_MODE else [settings.CHART_INTERVAL]
        
        config_path = "./threshold_config.json"
        existing_config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    existing_config = json.load(f)
            except Exception:
                pass

        for current_timeframe in timeframes_to_check:
            # Ambil statistik per timeframe
            stats = get_winrate_stats(days_back=30, timeframe=current_timeframe)
            summary = stats.get("summary", {})

            resolved = summary.get("resolved_signals", 0)
            winrate = summary.get("winrate", 0)
            avg_pnl = summary.get("avg_pnl", 0)
            profit_factor = summary.get("profit_factor", 0)

            # Threshold default (diselaraskan dengan scoring_engine.py: 75 Buy, 90 Strong Buy)
            DEFAULT_BUY_THRESHOLD = 75.0
            DEFAULT_STRONG_BUY_THRESHOLD = 90.0

            # Hitung threshold baru berdasarkan winrate
            if resolved < 10:
                # Data terlalu sedikit, jangan ubah threshold
                new_buy_threshold = DEFAULT_BUY_THRESHOLD
                new_strong_threshold = DEFAULT_STRONG_BUY_THRESHOLD
                calibration_action = "HOLD (data < 10 sinyal, belum cukup untuk kalibrasi)"
                threshold_emoji = "⚪"
            elif winrate < 45:
                # Winrate sangat buruk → naik (+5)
                new_buy_threshold = min(DEFAULT_BUY_THRESHOLD + 5, 85)
                new_strong_threshold = min(DEFAULT_STRONG_BUY_THRESHOLD + 3, 95)
                calibration_action = f"RAISED DRASTICALLY (winrate {winrate:.1f}% < 45%)"
                threshold_emoji = "🔴"
            elif winrate < 55:
                # Winrate buruk → naik sedang (+3)
                new_buy_threshold = min(DEFAULT_BUY_THRESHOLD + 3, 80)
                new_strong_threshold = min(DEFAULT_STRONG_BUY_THRESHOLD + 2, 93)
                calibration_action = f"RAISED (winrate {winrate:.1f}% < 55%)"
                threshold_emoji = "🟠"
            elif winrate < 65:
                # Winrate cukup → threshold normal
                new_buy_threshold = DEFAULT_BUY_THRESHOLD
                new_strong_threshold = DEFAULT_STRONG_BUY_THRESHOLD
                calibration_action = f"NORMAL (winrate {winrate:.1f}% dalam range 55-65%)"
                threshold_emoji = "🟡"
            elif winrate >= 75:
                # Winrate sangat bagus → bisa sedikit turunkan threshold (-3, lebih banyak sinyal)
                new_buy_threshold = max(DEFAULT_BUY_THRESHOLD - 3, 70)
                new_strong_threshold = max(DEFAULT_STRONG_BUY_THRESHOLD - 2, 88)
                calibration_action = f"LOWERED (winrate {winrate:.1f}% >= 75%, lebih banyak sinyal)"
                threshold_emoji = "🟢"
            else:
                # Winrate bagus → threshold normal
                new_buy_threshold = DEFAULT_BUY_THRESHOLD
                new_strong_threshold = DEFAULT_STRONG_BUY_THRESHOLD
                calibration_action = f"NORMAL (winrate {winrate:.1f}%)"
                threshold_emoji = "🟢"

            # Simpan threshold ke file JSON (dibaca oleh ScoringEngine)
            threshold_config = {
                "timeframe": current_timeframe,
                "buy_threshold": new_buy_threshold,
                "strong_buy_threshold": new_strong_threshold,
                "winrate_basis": winrate,
                "resolved_signals": resolved,
                "avg_pnl": avg_pnl,
                "profit_factor": profit_factor,
                "calibrated_at": datetime.now().isoformat(),
                "action": calibration_action,
            }

            existing_config[current_timeframe] = threshold_config
            logger.info(f"[AdaptiveThreshold] Saved threshold config: BUY={new_buy_threshold}, STRONG_BUY={new_strong_threshold}")

            # Kirim laporan ke Telegram
            msg = f"""🎯 <b>ADAPTIVE THRESHOLD CALIBRATION</b>
    ━━━━━━━━━━━━━━━━━━━━━━
    📊 Timeframe: <b>{current_timeframe.upper()}</b>
    📅 Data Basis: 30 hari terakhir ({resolved} sinyal resolved)

    {threshold_emoji} Winrate    : <b>{winrate:.1f}%</b>
    📈 Avg P&amp;L  : <b>{avg_pnl:+.2f}%</b>
    💹 Profit Factor: <b>{profit_factor:.2f}</b>

    🔧 <b>Kalibrasi Threshold:</b>
    ├─ BUY Threshold      : <code>{new_buy_threshold:.0f}/100</code> (sebelumnya: {DEFAULT_BUY_THRESHOLD:.0f})
    └─ STRONG BUY Threshold: <code>{new_strong_threshold:.0f}/100</code> (sebelumnya: {DEFAULT_STRONG_BUY_THRESHOLD:.0f})

    📝 Action: <i>{calibration_action}</i>
    ━━━━━━━━━━━━━━━━━━━━━━
    🤖 <i>Saber Trader — Auto Threshold Calibration</i>"""

            if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
                from telegram import Bot
                bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                thread_id = getattr(settings, "TELEGRAM_MESSAGE_THREAD_ID", None)
                thread_id = int(thread_id) if thread_id else None
                await send_telegram_with_retry(bot, settings.TELEGRAM_CHAT_ID, text=msg, message_thread_id=thread_id)
                logger.info(f"[AdaptiveThreshold] Sent calibration report to Telegram.")


        # Simpan semua konfigurasi
        with open(config_path, "w") as f:
            json.dump(existing_config, f, indent=2)
        logger.info(f"[AdaptiveThreshold] Saved threshold config to {config_path}")
    except Exception as e:
        logger.error(f"[AdaptiveThreshold] Calibration error: {e}", exc_info=True)


async def job_optimize_weights():
    """Run weekly weight optimization based on historical signal performance."""
    logger.info(f"[Scheduler] Starting scoring weights optimization at {datetime.now()}")
    try:
        from jobs.optimize_weights import run_optimization_job
        from app.config import get_settings
        settings = get_settings()
        db_url = settings.DATABASE_URL_SYNC
        path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "./idx_signal_bot.db"

        # Run sync optimization function in a separate thread to prevent blocking
        await asyncio.to_thread(run_optimization_job, db_path=path)
        logger.info("[Scheduler] Scoring weights optimized successfully.")

        # Read the newly saved weights
        config_path = "./weights_config.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                weights = json.load(f)

            # Format message
            msg = "⚖️ <b>SCORING WEIGHTS OPTIMIZATION COMPLETED</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "Sistem telah mengoptimalkan bobot indikator berdasarkan kinerja perdagangan historis:\n\n"
            for cat, w_val in weights.items():
                cat_name = cat.replace('_', ' ').title()
                msg += f"├─ <b>{cat_name}</b>: <code>{w_val}%</code>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🤖 <i>Saber Trader — Auto Weight Optimization</i>"

            if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
                from telegram import Bot
                bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                thread_id = getattr(settings, "TELEGRAM_MESSAGE_THREAD_ID", None)
                thread_id = int(thread_id) if thread_id else None
                await send_telegram_with_retry(bot, settings.TELEGRAM_CHAT_ID, text=msg, message_thread_id=thread_id)
                logger.info("[Scheduler] Sent weight optimization report to Telegram.")
    except Exception as e:
        logger.error(f"[Scheduler] Weight optimization job failed: {e}", exc_info=True)


# ================================================================== #
#  Job: Daily SPS Signal Recap (17:09 WIB — Google Sheets & Telegram)
# ================================================================== #

async def job_sps_recap():
    """
    Daily Signal Recap at 17:09 WIB.
    Syncs all signals (sorted newest to oldest) with their status (TP, SL, Floating Profit/Loss)
    to Google Sheets (SPS), and sends a summary report with the SPS link to Telegram.
    """
    logger.info(f"[Scheduler] Starting daily SPS signal recap at {datetime.now()}")
    try:
        from services.spreadsheet_service import (
            fetch_all_signals_recap,
            sync_signals_to_google_sheet,
            format_sps_recap_message,
        )
        from app.config import get_settings
        settings = get_settings()

        # 1. Ambil data rekapitulasi dari database (terbaru ke terlama)
        signals, summary = await asyncio.to_thread(fetch_all_signals_recap)
        logger.info(f"[Scheduler] Fetched {len(signals)} signals for SPS recap.")

        # 2. Sinkronisasi data ke Google Spreadsheet via Webhook (Google Apps Script)
        synced = await sync_signals_to_google_sheet(signals, summary)
        if synced:
            logger.info("[Scheduler] Google Sheet successfully updated via webhook.")
        else:
            logger.info("[Scheduler] Google Sheet webhook sync skipped or not yet configured in GOOGLE_SHEET_WEBHOOK_URL.")

        # 3. Kirim pesan ringkasan dan tautan link Spreadsheet ke Telegram
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            from telegram import Bot
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            thread_id = getattr(settings, "TELEGRAM_MESSAGE_THREAD_ID", None)
            thread_id = int(thread_id) if thread_id else None

            sheet_url = getattr(settings, "GOOGLE_SHEET_VIEW_URL", "")
            msg = format_sps_recap_message(summary, sheet_url=sheet_url)

            await send_telegram_with_retry(
                bot,
                settings.TELEGRAM_CHAT_ID,
                text=msg,
                message_thread_id=thread_id
            )
            logger.info("[Scheduler] Sent SPS recap report with link to Telegram.")
        else:
            logger.warning("[Scheduler] Telegram not configured — skipping SPS recap notification")

    except Exception as e:
        logger.error(f"[Scheduler] Error running SPS recap job: {e}", exc_info=True)



# ==================================================================

# ================================================================== #

# ================================================================== #
#  Job: Real-Time TP/SL Signal Monitor (Setiap 10 menit saat bursa buka)
# ================================================================== #

async def job_monitor_tp_sl():
    """Real-Time TP/SL Signal Monitor during market hours."""
    try:
        from run_monitor_tp_sl import monitor_signals
        await monitor_signals(force=False)
    except Exception as e:
        logger.error(f"[Scheduler] Error running TP/SL monitor: {e}", exc_info=True)


# ================================================================== #
#  Job: BSJP Scan — Beli Sore Jual Profit (15:45 WIB)
# ================================================================== #

async def job_bsjp_scan():
    """
    BSJP Screener: jalankan pukul 15:45 WIB setiap hari bursa.
    Ambil universe, scoring tiap saham, kirim sinyal ke Telegram.
    """
    logger.info(f"[BSJP] Starting BSJP scan at {datetime.now()}")
    try:
        from services.bsjp_engine import run_bsjp_screener
        from services.bsjp_db import save_bsjp_signals, migrate_bsjp_table
        from services.stock_universe_service import get_stock_universe
        from services.idx_full_universe_service import get_full_idx_universe, is_fca_stock
        from app.config import get_settings
        import os

        settings_obj = get_settings()
        bsjp_token = os.getenv("BSJP_BOT_TOKEN", getattr(settings_obj, "BSJP_BOT_TOKEN", "9261989934:AAFO3q5Bs32pp4ElVyxYf-VufWaYj66rwPo"))
        bsjp_chat = os.getenv("BSJP_CHAT_ID", getattr(settings_obj, "BSJP_CHAT_ID", "-1004302595573"))
        bsjp_thread = int(os.getenv("BSJP_THREAD_ID", str(getattr(settings_obj, "BSJP_THREAD_ID", 107) or 107)))

        # Migrate tabel jika belum ada
        await asyncio.to_thread(migrate_bsjp_table)

        # Ambil universe: gunakan full universe jika tersedia, fallback default
        try:
            universe_raw = await asyncio.to_thread(get_full_idx_universe)
            universe = [t for t in universe_raw if not is_fca_stock(t)]
        except Exception:
            universe_data = get_stock_universe()
            universe = [s["ticker"] for s in universe_data]

        logger.info(f"[BSJP] Universe size: {len(universe)}")

        # Jalankan screener
        signals = await asyncio.to_thread(run_bsjp_screener, universe)
        logger.info(f"[BSJP] Candidates found: {len(signals)}")

        # Simpan ke DB
        await asyncio.to_thread(save_bsjp_signals, signals)

        # Format pesan Telegram
        if signals:
            ticker_lines = "\n".join(s["ticker"] for s in signals)
        else:
            ticker_lines = "(tidak ada kandidat hari ini)"

        msg_lines = [
            "BSJP SABER TRADER",
            "Beli di lelang pre-closing · JUAL BESOK PAGI sebelum jam 9.30",
            "",
            ticker_lines,
            "",
            "⚠️ Ini pemantauan pola, BUKAN rekomendasi beli/jual. Keputusan, ukuran posisi, dan risiko sepenuhnya di tangan Anda.",
            "🤖 Powered by Bot Saber Trader— BSJP"
        ]
        msg = "\n".join(msg_lines)

        from telegram import Bot
        from telegram.request import HTTPXRequest
        req_client = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0)
        bot = Bot(token=bsjp_token, request=req_client)
        await send_telegram_with_retry(
            bot, bsjp_chat, text=msg, message_thread_id=bsjp_thread
        )
        logger.info(f"[BSJP] Sent {len(signals)} candidates to Telegram.")

    except Exception as e:
        logger.error(f"[BSJP] job_bsjp_scan failed: {e}", exc_info=True)


# ================================================================== #
#  Job: BSJP Rekap Pagi (09:30 WIB)
# ================================================================== #

async def job_bsjp_rekap():
    """
    BSJP Rekap: pukul 09:30 WIB, hitung outcome sinyal BSJP kemarin.
    Profit = high sebelum 09:30 hari ini > close sinyal kemarin.
    """
    from datetime import timedelta
    logger.info(f"[BSJP] Starting BSJP rekap at {datetime.now()}")
    try:
        from services.bsjp_db import get_pending_bsjp_signals, update_bsjp_outcome
        from app.config import get_settings
        import yfinance as yf
        import pytz
        import os

        settings_obj = get_settings()
        bsjp_token = os.getenv("BSJP_BOT_TOKEN", getattr(settings_obj, "BSJP_BOT_TOKEN", "9261989934:AAFO3q5Bs32pp4ElVyxYf-VufWaYj66rwPo"))
        bsjp_chat = os.getenv("BSJP_CHAT_ID", getattr(settings_obj, "BSJP_CHAT_ID", "-1004302595573"))
        bsjp_thread = int(os.getenv("BSJP_THREAD_ID", str(getattr(settings_obj, "BSJP_THREAD_ID", 107) or 107)))

        wib = pytz.timezone("Asia/Jakarta")
        today_wib = datetime.now(wib).date()
        yesterday_str = (today_wib - timedelta(days=1)).strftime("%Y-%m-%d")

        # Dapatkan sinyal kemarin yang masih pending
        pending = await asyncio.to_thread(get_pending_bsjp_signals, yesterday_str)
        if not pending:
            logger.info(f"[BSJP Rekap] Tidak ada pending signals untuk {yesterday_str}")
            return

        logger.info(f"[BSJP Rekap] Processing {len(pending)} pending signals from {yesterday_str}")

        recap_lines = []
        profit_count = 0
        lose_count = 0

        for sig in pending:
            ticker = sig["ticker"]
            close_signal = sig.get("close_price") or 0
            yf_ticker = ticker if ticker.endswith(".JK") else ticker + ".JK"

            try:
                # Ambil data 5M hari ini untuk mendapat high dan low sebelum 09:30
                raw = await asyncio.to_thread(
                    lambda t=yf_ticker: yf.download(
                        t, period="1d", interval="5m",
                        auto_adjust=True, progress=False, threads=False
                    )
                )
                if raw is None or raw.empty:
                    logger.warning(f"[BSJP Rekap] No data for {ticker}")
                    continue

                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                raw.columns = [c.lower() for c in raw.columns]

                if raw.index.tzinfo is None:
                    raw.index = raw.index.tz_localize("UTC")
                raw.index = raw.index.tz_convert(wib)

                # Filter candle sebelum 09:30 WIB hari ini
                cutoff = datetime.now(wib).replace(hour=9, minute=30, second=0, microsecond=0)
                df_before_930 = raw[raw.index < cutoff]

                if df_before_930.empty:
                    df_before_930 = raw.head(1)

                high_before_930 = float(df_before_930["high"].max())
                low_before_930 = float(df_before_930["low"].min())
                open_today = float(raw["open"].iloc[0]) if not raw.empty else 0.0

                # Hitung outcome
                if close_signal > 0:
                    is_profit = high_before_930 > close_signal
                    if is_profit:
                        pct_chg = (high_before_930 - close_signal) / close_signal
                        price_val = high_before_930
                    else:
                        pct_chg = (low_before_930 - close_signal) / close_signal
                        price_val = low_before_930
                else:
                    pct_chg = 0.0
                    is_profit = False
                    price_val = high_before_930

                outcome = "profit" if is_profit else "lose"
                await asyncio.to_thread(
                    update_bsjp_outcome,
                    ticker, yesterday_str, open_today, high_before_930,
                    pct_chg, outcome
                )

                emoji = "🟢" if is_profit else "🛑"
                pct_str = f"+{pct_chg:.1%}" if pct_chg >= 0 else f"{pct_chg:.1%}"
                price_display = int(price_val) if price_val >= 100 else round(price_val, 2)
                outcome_label = "Profit" if is_profit else "Lose"
                recap_lines.append(
                    f"{emoji} {ticker} | {price_display} | {pct_str} | {outcome_label}"
                )
                if is_profit:
                    profit_count += 1
                else:
                    lose_count += 1

            except Exception as e:
                logger.error(f"[BSJP Rekap] Error processing {ticker}: {e}")
                continue

        total = profit_count + lose_count
        wr = int(profit_count / total * 100) if total > 0 else 0

        if recap_lines:
            detail = "\n".join(recap_lines)
            msg_lines = [
                "Rekap BSJP kemaren",
                f"Signal:{total}  Profit:{profit_count}  Lose:{lose_count} WR:{wr}%",
                "",
                "nama saham | high/low | persen | profit/lose",
                detail,
                "",
                "🤖 Bot Saber Trader — BSJP"
            ]
            msg = "\n".join(msg_lines)
        else:
            msg_lines = [
                "Rekap BSJP kemaren",
                f"Tidak ada data rekap untuk {yesterday_str}.",
                "",
                "🤖 Bot Saber Trader — BSJP"
            ]
            msg = "\n".join(msg_lines)

        from telegram import Bot
        from telegram.request import HTTPXRequest
        req_client = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0)
        bot = Bot(token=bsjp_token, request=req_client)
        await send_telegram_with_retry(
            bot, bsjp_chat, text=msg, message_thread_id=bsjp_thread
        )
        logger.info(f"[BSJP Rekap] Sent recap: {profit_count}P / {lose_count}L / WR {wr}%")

    except Exception as e:
        logger.error(f"[BSJP] job_bsjp_rekap failed: {e}", exc_info=True)

