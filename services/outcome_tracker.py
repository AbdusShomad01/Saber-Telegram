"""
Saber Trader — Signal Outcome Tracker
Handles persistence of signal performance outcomes (TP hit, SL hit, P&L)
into the SQLite database for historical winrate tracking.
"""

import sqlite3
import logging
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_db_path() -> str:
    db_url = settings.DATABASE_URL_SYNC
    return db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "./idx_signal_bot.db"


def migrate_add_outcome_columns():
    """
    Add outcome tracking columns to the signals table if not already present.
    Safe to run multiple times (idempotent).
    """
    db_path = _get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check which columns already exist
        cursor.execute("PRAGMA table_info(signals)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        new_columns = [
            ("outcome_status", "VARCHAR(20) DEFAULT 'PENDING'"),  # PENDING, TP_HIT, SL_HIT, EXPIRED, PROFIT, LOSS
            ("outcome_price", "FLOAT"),           # Closing/exit price when outcome was determined
            ("outcome_pnl_pct", "FLOAT"),         # Realized P&L percentage
            ("outcome_checked_at", "DATETIME"),   # When was the outcome last checked
            ("outcome_date", "DATE"),             # The date the outcome was determined
            ("tp_hit", "BOOLEAN DEFAULT 0"),
            ("sl_hit", "BOOLEAN DEFAULT 0"),
            ("max_price_seen", "FLOAT"),          # Highest price seen since signal
            ("min_price_seen", "FLOAT"),          # Lowest price seen since signal
            ("tp2", "FLOAT"),
            ("tp3", "FLOAT"),
            ("bandarmology_json", "JSON"),
            ("foreign_flow_json", "JSON"),
            ("category_raw_json", "JSON"),
        ]

        for col_name, col_def in new_columns:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE signals ADD COLUMN {col_name} {col_def}")
                logger.info(f"[OutcomeTracker] Added column: {col_name}")

        conn.commit()
        conn.close()
        logger.info("[OutcomeTracker] Migration complete — outcome and optimization columns ready")
    except Exception as e:
        logger.error(f"[OutcomeTracker] Migration failed: {e}")


def get_pending_signals(days_back: int = 7, timeframe: Optional[str] = None) -> List[Dict]:
    """
    Fetch all signals with PENDING outcome status from the last N days.
    Jika timeframe diberikan (mis: '60m', '1d'), hanya ambil sinyal dari timeframe tersebut.
    """
    db_path = _get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        timeframe_filter = "AND timeframe = ?" if timeframe else ""
        params = [f"-{days_back} days"]
        if timeframe:
            params.append(timeframe)

        cursor.execute(f"""
            SELECT id, ticker, timeframe, signal, entry_price, tp1, tp2,
                   stop_loss_atr, stop_loss_conservative, raw_score,
                   confidence_score, created_at, outcome_status, outcome_pnl_pct
            FROM signals
            WHERE (outcome_status IS NULL OR outcome_status = 'PENDING')
              AND created_at >= datetime('now', ?)
              AND signal IN ('STRONG BUY', 'BUY', 'WATCHLIST')
              {timeframe_filter}
            ORDER BY created_at DESC
        """, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"[OutcomeTracker] get_pending_signals error: {e}")
        return []


def evaluate_outcome_from_ohlcv(
    signal: Dict,
    high_of_period: float,
    low_of_period: float,
    close_of_period: float,
) -> Dict:
    """
    Evaluasi outcome sinyal berdasarkan high/low/close periode observasi.

    Menggunakan high untuk cek TP dan low untuk cek SL — BUKAN hanya close.
    Ini lebih akurat karena harga bisa hit TP intraday lalu close di bawahnya.

    Returns:
        dict dengan keys: status, pnl_pct, tp_hit, tp2_hit, sl_hit, outcome_price
    """
    entry_price = float(signal.get("entry_price") or 0)
    tp1 = float(signal.get("tp1") or 0)
    tp2 = float(signal.get("tp2") or 0)
    sl = float(signal.get("stop_loss_atr") or signal.get("stop_loss_conservative") or 0)

    if entry_price <= 0:
        return {"status": "PENDING", "pnl_pct": 0, "tp_hit": False, "tp2_hit": False,
                "sl_hit": False, "outcome_price": close_of_period}

    # Gunakan HIGH untuk cek TP (bisa hit TP di siang hari meski close di bawahnya)
    tp_hit  = (high_of_period >= tp1)  if tp1 > 0 else False
    tp2_hit = (high_of_period >= tp2)  if tp2 > 0 else False
    # Gunakan LOW untuk cek SL (kena stop di siang hari meski close di atasnya)
    sl_hit  = (low_of_period  <= sl)   if sl  > 0 else False

    # Jika TP dan SL keduanya hit di hari yang sama,
    # beri benefit of the doubt: TP hit lebih dulu (harga naik dulu baru turun)
    # karena urutan TP/SL dalam satu bar tidak bisa diketahui pasti dari OHLC
    # → Ini konservatif tapi lebih adil daripada selalu anggap SL dulu
    if tp_hit and sl_hit:
        # Cek apakah high lebih dekat ke entry atau low yang lebih dekat ke entry
        # Jika high lebih besar persentasenya → kemungkinan TP hit dulu
        tp_pct = (high_of_period - entry_price) / entry_price
        sl_pct = (entry_price - low_of_period)  / entry_price
        if tp_pct >= sl_pct:
            sl_hit = False  # TP hit dulu
        else:
            tp_hit = False  # SL hit dulu
            tp2_hit = False

    # Hitung P&L berdasarkan outcome
    if tp2_hit:
        pnl_pct = ((tp2 - entry_price) / entry_price) * 100
        status = "TP2_HIT"
    elif tp_hit:
        pnl_pct = ((tp1 - entry_price) / entry_price) * 100
        status = "TP_HIT"
    elif sl_hit:
        pnl_pct = ((sl - entry_price) / entry_price) * 100
        status = "SL_HIT"
    else:
        pnl_pct = ((close_of_period - entry_price) / entry_price) * 100
        if pnl_pct > 0.5:
            status = "PROFIT"
        elif pnl_pct < -0.5:
            status = "LOSS"
        else:
            status = "PENDING"  # Terlalu kecil untuk dihitung

    return {
        "status": status,
        "pnl_pct": round(pnl_pct, 4),
        "tp_hit": tp_hit,
        "tp2_hit": tp2_hit,
        "sl_hit": sl_hit,
        "outcome_price": close_of_period,
    }


def update_signal_outcome(
    signal_id: int,
    status: str,
    outcome_price: float,
    pnl_pct: float,
    tp_hit: bool,
    sl_hit: bool,
    max_price: float = 0,
    min_price: float = 0,
    tp2_hit: bool = False,
):
    """
    Persist the outcome of a signal to the database.
    status: 'TP_HIT' | 'TP2_HIT' | 'SL_HIT' | 'PROFIT' | 'LOSS' | 'EXPIRED' | 'PENDING'
    """
    db_path = _get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Tambah kolom tp2_hit jika belum ada (idempotent)
        try:
            cursor.execute("ALTER TABLE signals ADD COLUMN tp2_hit BOOLEAN DEFAULT 0")
            conn.commit()
        except Exception:
            pass  # Kolom sudah ada

        cursor.execute("""
            UPDATE signals SET
                outcome_status = ?,
                outcome_price = ?,
                outcome_pnl_pct = ?,
                outcome_checked_at = CURRENT_TIMESTAMP,
                outcome_date = DATE('now'),
                tp_hit = ?,
                sl_hit = ?,
                max_price_seen = ?,
                min_price_seen = ?,
                tp2_hit = ?
            WHERE id = ?
        """, (status, outcome_price, round(pnl_pct, 4), 1 if tp_hit else 0, 1 if sl_hit else 0,
              max_price, min_price, 1 if tp2_hit else 0, signal_id))
        conn.commit()
        conn.close()
        tp2_info = " (TP2 juga hit!" + ")" if tp2_hit else ""
        logger.info(f"[OutcomeTracker] Signal ID {signal_id} → {status} ({pnl_pct:+.2f}%){tp2_info}")
    except Exception as e:
        logger.error(f"[OutcomeTracker] update_signal_outcome error: {e}")


def get_winrate_stats(days_back: int = 30, timeframe: Optional[str] = None) -> Dict:
    """
    Calculate winrate, avg P&L, and signal distribution from the DB.
    Jika timeframe diberikan, filter hanya untuk timeframe tersebut.
    Returns a dict with full stats for the dashboard.
    """
    db_path = _get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build timeframe filter
        tf_filter = "AND timeframe = ?" if timeframe else ""
        base_params = [f"-{days_back} days"]
        if timeframe:
            base_params.append(timeframe)

        # Overall stats for resolved signals
        cursor.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN outcome_status IN ('TP_HIT', 'TP2_HIT', 'PROFIT') THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome_status IN ('SL_HIT', 'LOSS') THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome_status = 'PENDING' OR outcome_status IS NULL THEN 1 ELSE 0 END) as pending,
                AVG(CASE WHEN outcome_pnl_pct IS NOT NULL THEN outcome_pnl_pct END) as avg_pnl,
                AVG(CASE WHEN outcome_status IN ('TP_HIT', 'TP2_HIT', 'PROFIT') AND outcome_pnl_pct IS NOT NULL THEN outcome_pnl_pct END) as avg_win,
                AVG(CASE WHEN outcome_status IN ('SL_HIT', 'LOSS') AND outcome_pnl_pct IS NOT NULL THEN outcome_pnl_pct END) as avg_loss,
                MAX(outcome_pnl_pct) as best_trade,
                MIN(outcome_pnl_pct) as worst_trade
            FROM signals
            WHERE created_at >= datetime('now', ?)
              AND signal IN ('STRONG BUY', 'BUY', 'WATCHLIST')
              {tf_filter}
        """, base_params)
        row = dict(cursor.fetchone())

        total = row["total"] or 0
        wins = row["wins"] or 0
        losses = row["losses"] or 0
        resolved = wins + losses
        winrate = round((wins / resolved * 100), 1) if resolved > 0 else 0

        profit_factor = 0
        if row["avg_loss"] and row["avg_loss"] != 0 and row["avg_win"]:
            profit_factor = round(abs(row["avg_win"] / row["avg_loss"]), 2)

        # Daily P&L for chart (last 30 days)
        cursor.execute(f"""
            SELECT DATE(outcome_date) as day, 
                   SUM(outcome_pnl_pct) as daily_pnl,
                   COUNT(*) as count
            FROM signals
            WHERE outcome_date IS NOT NULL
              AND created_at >= datetime('now', ?)
              {tf_filter}
            GROUP BY DATE(outcome_date)
            ORDER BY day ASC
        """, base_params)
        daily_pnl = [{"date": r["day"], "pnl": round(r["daily_pnl"] or 0, 2), "count": r["count"]}
                     for r in cursor.fetchall()]

        # Signal type distribution
        cursor.execute(f"""
            SELECT signal, COUNT(*) as cnt
            FROM signals
            WHERE created_at >= datetime('now', ?)
              {tf_filter}
            GROUP BY signal
        """, base_params)
        signal_dist = {r["signal"]: r["cnt"] for r in cursor.fetchall()}

        # Recent signals with outcome (last 50)
        cursor.execute("""
            SELECT id, ticker, timeframe, signal, raw_score, confidence_score, confidence_label,
                   entry_price, tp1, stop_loss_atr, stop_loss_conservative,
                   outcome_status, outcome_price, outcome_pnl_pct, tp_hit, sl_hit,
                   created_at, outcome_date
            FROM signals
            ORDER BY created_at DESC
            LIMIT 50
        """)
        recent = [dict(r) for r in cursor.fetchall()]

        conn.close()

        return {
            "summary": {
                "total_signals": total,
                "resolved_signals": resolved,
                "wins": wins,
                "losses": losses,
                "pending": row["pending"] or 0,
                "winrate": winrate,
                "profit_factor": profit_factor,
                "avg_pnl": round(row["avg_pnl"] or 0, 2),
                "avg_win": round(row["avg_win"] or 0, 2),
                "avg_loss": round(row["avg_loss"] or 0, 2),
                "best_trade": round(row["best_trade"] or 0, 2),
                "worst_trade": round(row["worst_trade"] or 0, 2),
                "days_back": days_back,
                "timeframe_filter": timeframe or "all",
            },
            "daily_pnl": daily_pnl,
            "signal_distribution": signal_dist,
            "recent_signals": recent,
        }
    except Exception as e:
        logger.error(f"[OutcomeTracker] get_winrate_stats error: {e}")
        return {"summary": {}, "daily_pnl": [], "signal_distribution": {}, "recent_signals": []}


def expire_old_pending_signals(max_hold_days: int = 5):
    """
    Mark signals older than max_hold_days as EXPIRED if still PENDING.
    Called daily to clean up stale signals.
    """
    db_path = _get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE signals SET
                outcome_status = 'EXPIRED',
                outcome_checked_at = CURRENT_TIMESTAMP,
                outcome_date = DATE('now')
            WHERE (outcome_status IS NULL OR outcome_status = 'PENDING')
              AND created_at < datetime('now', ?)
              AND signal IN ('STRONG BUY', 'BUY', 'WATCHLIST')
        """, (f"-{max_hold_days} days",))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        if affected > 0:
            logger.info(f"[OutcomeTracker] Expired {affected} old pending signals (>{max_hold_days} days)")
    except Exception as e:
        logger.error(f"[OutcomeTracker] expire_old_signals error: {e}")
