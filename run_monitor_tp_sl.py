"""
Saber Trader — Real-Time TP / SL Signal Monitor
Memantau sinyal saham berstatus PENDING setiap 10 menit saat jam bursa IDX.
Jika harga menyentuh TP1 atau Stop Loss, bot akan mengirim notifikasi ke Telegram
dan langsung mengunci status di database agar tidak pernah dikirim ulang.
"""

import os
import sys
import asyncio
import logging
import sqlite3
from datetime import datetime, date, time as dtime
from typing import Dict, List, Optional

# Tambahkan path root proyek
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from app.config import get_settings
from services.data_provider_service import DataProviderService
from services.outcome_tracker import _get_db_path, update_signal_outcome
from jobs.scheduler import send_telegram_with_retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("TP_SL_Monitor")


def is_market_open(now: Optional[datetime] = None) -> bool:
    """
    Cek apakah waktu saat ini berada dalam jam perdagangan bursa IDX (Senin - Jumat WIB).
    Sesi 1: 09:00 - 12:00 (Jumat: 09:00 - 11:30)
    Sesi 2: 13:30 - 16:05 (Jumat: 14:00 - 16:05)
    """
    if now is None:
        now = datetime.now()

    # Cek hari (Senin=0, ..., Jumat=4, Sabtu=5, Minggu=6)
    if now.weekday() > 4:
        return False

    current_time = now.time()
    is_friday = (now.weekday() == 4)

    # Jam sesi 1
    session1_start = dtime(9, 0)
    session1_end = dtime(11, 30) if is_friday else dtime(12, 0)

    # Jam sesi 2
    session2_start = dtime(14, 0) if is_friday else dtime(13, 30)
    session2_end = dtime(16, 5)

    in_session1 = session1_start <= current_time <= session1_end
    in_session2 = session2_start <= current_time <= session2_end

    return in_session1 or in_session2


def format_duration(start_dt: datetime, end_dt: datetime) -> str:
    """Format selisih waktu menjadi string yang mudah dibaca (contoh: 4 jam 26 mnt)."""
    delta = end_dt - start_dt
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = 0

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    if days > 0:
        return f"{days} hari {hours} jam {minutes} mnt"
    elif hours > 0:
        return f"{hours} jam {minutes} mnt"
    else:
        return f"{minutes} mnt"


def parse_datetime(dt_val) -> datetime:
    """Parse string datetime dari SQLite."""
    if isinstance(dt_val, datetime):
        return dt_val
    if not dt_val:
        return datetime.now()
    
    # Hapus spasi dan bersihkan
    s = str(dt_val).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.split(".")[0], fmt)
        except ValueError:
            continue
    return datetime.now()


def get_pending_signals() -> List[Dict]:
    """Ambil semua sinyal berstatus PENDING dari database."""
    db_path = _get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, ticker, signal, timeframe, entry_price, tp1, tp2, tp3,
                   stop_loss_atr, stop_loss_moderate, stop_loss_conservative,
                   created_at, outcome_status, max_price_seen, min_price_seen
            FROM signals
            WHERE (outcome_status IS NULL OR outcome_status = 'PENDING')
              AND signal IN ('STRONG BUY', 'BUY', 'WATCHLIST')
              AND created_at >= datetime('now', '-7 days')
            ORDER BY created_at ASC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Gagal mengambil sinyal pending: {e}")
        return []


def update_tracked_prices(signal_id: int, max_price: float, min_price: float):
    """Update peak dan low harga berjalan untuk sinyal pending."""
    db_path = _get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE signals
            SET max_price_seen = ?, min_price_seen = ?, outcome_checked_at = datetime('now')
            WHERE id = ?
        """, (max_price, min_price, signal_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Gagal update tracked prices ID {signal_id}: {e}")


async def monitor_signals(force: bool = False):
    """Proses utama pemantauan TP dan SL sinyal saham."""
    now = datetime.now()
    logger.info(f"🔍 Menjalankan Real-Time TP/SL Monitor pada {now.strftime('%Y-%m-%d %H:%M:%S')} WIB")

    if not force and not is_market_open(now):
        logger.info("⏸️ Pasar bursa IDX sedang tutup (di luar jam bursa / libur). Pemantauan dilewati.")
        return

    pending_signals = get_pending_signals()
    if not pending_signals:
        logger.info("ℹ️ Tidak ada sinyal aktif (PENDING) untuk dipantau.")
        return

    logger.info(f"📊 Ditemukan {len(pending_signals)} sinyal aktif yang akan dipantau...")

    settings = get_settings()
    bot = None
    thread_id = getattr(settings, "TELEGRAM_MESSAGE_THREAD_ID", None)
    thread_id = int(thread_id) if thread_id else None

    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        from telegram import Bot
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    dp = DataProviderService()

    for s in pending_signals:
        signal_id = s["id"]
        ticker = s["ticker"]
        entry_price = float(s.get("entry_price") or 0)
        tp1 = float(s.get("tp1") or 0)
        # Prioritas Stop Loss: ATR -> Moderate -> Conservative
        sl = float(s.get("stop_loss_atr") or s.get("stop_loss_moderate") or s.get("stop_loss_conservative") or 0)

        if entry_price <= 0:
            continue

        try:
            # Ambil pergerakan harga hari ini
            ohlcv = dp.get_ohlcv(ticker, period_days=1, interval="5m")
            if ohlcv.empty:
                # Fallback ke 1d jika intraday 5m belum update
                ohlcv = dp.get_ohlcv(ticker, period_days=2, interval="1d")
                if ohlcv.empty:
                    logger.warning(f"Data harga untuk {ticker} kosong, dilewati.")
                    continue

            current_price = float(ohlcv["close"].iloc[-1])
            intraday_high = float(ohlcv["high"].max())
            intraday_low = float(ohlcv["low"].min())

            prev_max = float(s.get("max_price_seen") or 0)
            prev_min = float(s.get("min_price_seen") or 999999999)

            max_seen = max(intraday_high, current_price, prev_max)
            min_seen = min(intraday_low, current_price, prev_min) if prev_min > 0 else min(intraday_low, current_price)

            created_dt = parse_datetime(s.get("created_at"))
            duration_str = format_duration(created_dt, now)
            call_date_str = created_dt.strftime("%d %b %Y, %H:%M WIB")

            # Evaluasi TP1 & SL
            tp_hit = (max_seen >= tp1) if tp1 > 0 else False
            sl_hit = (min_seen <= sl) if sl > 0 else False

            # Jika keduanya hit dalam periode pengamatan, beri prioritas TP hit lebih dulu
            if tp_hit and sl_hit:
                tp_pct = (max_seen - entry_price) / entry_price
                sl_pct = (entry_price - min_seen) / entry_price
                if tp_pct >= sl_pct:
                    sl_hit = False
                else:
                    tp_hit = False

            # --- Skenario 1: TP1 TERCAPAI (PROFIT) ---
            if tp_hit:
                profit_pct = ((tp1 - entry_price) / entry_price) * 100
                peak_pct = ((max_seen - entry_price) / entry_price) * 100

                msg = (
                    "🏆 <b>SIGNAL CONFIRMED — PROFIT!</b> 🏆\n\n"
                    f"<b>Symbol:</b> {ticker}\n"
                    f"<b>Status:</b> ✅ TP1 HIT\n"
                    f"📅 <b>Call Watchlist:</b> {call_date_str}\n"
                    f"⏱️ <b>Durasi:</b> {duration_str} (call → profit)\n"
                    f"<b>Entry:</b> Rp{entry_price:,.0f} → <b>TP1:</b> Rp{tp1:,.0f} (+{profit_pct:.1f}%)\n"
                    f"<b>Peak Tertinggi:</b> Rp{max_seen:,.0f} (+{peak_pct:.1f}%)\n"
                    f"<b>Profit Terkunci:</b> +{profit_pct:.1f}%\n\n"
                    "<i>Saber Trader</i>"
                )

                logger.info(f"🎯 [TP1 HIT] {ticker} kena TP1 di Rp{tp1:,.0f} (+{profit_pct:.1f}%)")

                # Kirim ke Telegram
                if bot:
                    await send_telegram_with_retry(
                        bot, settings.TELEGRAM_CHAT_ID,
                        text=msg, message_thread_id=thread_id
                    )

                # Kunci status di database (Terkunci permanen, tidak dikirim lagi)
                update_signal_outcome(
                    signal_id=signal_id,
                    status="TP1_HIT",
                    outcome_price=tp1,
                    pnl_pct=round(profit_pct, 2),
                    tp_hit=True,
                    sl_hit=False,
                    max_price=max_seen,
                    min_price=min_seen,
                )

                # Delay anti-flood Telegram
                await asyncio.sleep(1.0)
                continue

            # --- Skenario 2: STOP LOSS TERCAPAI (LOSS) ---
            elif sl_hit:
                loss_pct = ((sl - entry_price) / entry_price) * 100
                low_pct = ((min_seen - entry_price) / entry_price) * 100

                msg = (
                    "⚠️ <b>SIGNAL STOP LOSS HIT</b> ⚠️\n\n"
                    f"<b>Symbol:</b> {ticker}\n"
                    f"<b>Status:</b> ❌ SL HIT\n"
                    f"📅 <b>Call Watchlist:</b> {call_date_str}\n"
                    f"⏱️ <b>Durasi:</b> {duration_str} (call → stop loss)\n"
                    f"<b>Entry:</b> Rp{entry_price:,.0f} → <b>SL:</b> Rp{sl:,.0f} ({loss_pct:.1f}%)\n"
                    f"<b>Low Terendah:</b> Rp{min_seen:,.0f} ({low_pct:.1f}%)\n"
                    f"<b>Loss Terproteksi:</b> {loss_pct:.1f}%\n\n"
                    "<i>Saber Trader</i>"
                )

                logger.info(f"🛑 [SL HIT] {ticker} kena SL di Rp{sl:,.0f} ({loss_pct:.1f}%)")

                # Kirim ke Telegram
                if bot:
                    await send_telegram_with_retry(
                        bot, settings.TELEGRAM_CHAT_ID,
                        text=msg, message_thread_id=thread_id
                    )

                # Kunci status di database (Terkunci permanen, tidak dikirim lagi)
                update_signal_outcome(
                    signal_id=signal_id,
                    status="SL_HIT",
                    outcome_price=sl,
                    pnl_pct=round(loss_pct, 2),
                    tp_hit=False,
                    sl_hit=True,
                    max_price=max_seen,
                    min_price=min_seen,
                )

                # Delay anti-flood Telegram
                await asyncio.sleep(1.0)
                continue

            # --- Skenario 3: Belum Kena TP / SL ---
            else:
                # Update peak dan low saja secara silent, status tetap PENDING
                update_tracked_prices(signal_id, max_seen, min_seen)
                pnl_now = ((current_price - entry_price) / entry_price) * 100
                logger.debug(f"⏳ {ticker} masih PENDING | Harga: Rp{current_price:,.0f} ({pnl_now:+.1f}%) | Peak: {max_seen} | Low: {min_seen}")

        except Exception as err:
            logger.error(f"Error memantau saham {ticker}: {err}")


if __name__ == "__main__":
    force_run = "--force" in sys.argv
    asyncio.run(monitor_signals(force=force_run))

