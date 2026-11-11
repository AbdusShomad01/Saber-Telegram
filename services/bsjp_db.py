"""
BSJP Database — tabel bsjp_signals untuk menyimpan sinyal dan rekap outcome.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Optional

import pytz

logger = logging.getLogger(__name__)
WIB = pytz.timezone("Asia/Jakarta")


def _get_db_path() -> str:
    from app.config import get_settings
    s = get_settings()
    db_url = s.DATABASE_URL_SYNC
    return db_url.replace("sqlite:///./", "./").replace("sqlite:///", "") \
                 if db_url.startswith("sqlite") else "./idx_signal_bot.db"


def migrate_bsjp_table():
    """Buat tabel bsjp_signals jika belum ada."""
    path = _get_db_path()
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bsjp_signals (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker           TEXT    NOT NULL,
                signal_date      TEXT    NOT NULL,
                score            REAL,
                close_price      REAL,
                created_at       TEXT    DEFAULT CURRENT_TIMESTAMP,
                open_next_day    REAL,
                high_next_day    REAL,
                outcome          TEXT    DEFAULT 'pending',
                pct_change       REAL
            )
        """)
        conn.commit()
    logger.info("[BSJP DB] bsjp_signals table ready.")


def save_bsjp_signals(signals: list[dict], signal_date: Optional[str] = None):
    """Simpan daftar sinyal BSJP ke database (tanggal WIB). Hindari duplikasi per ticker+tanggal."""
    path = _get_db_path()
    today_str = signal_date or datetime.now(WIB).strftime("%Y-%m-%d")
    migrate_bsjp_table()
    with sqlite3.connect(path) as conn:
        for s in signals:
            # Cek duplikasi
            cur = conn.execute(
                "SELECT id FROM bsjp_signals WHERE ticker=? AND signal_date=?",
                (s["ticker"], today_str)
            )
            if cur.fetchone():
                logger.debug(f"[BSJP DB] Skip duplicate {s['ticker']} {today_str}")
                continue
            conn.execute(
                """INSERT INTO bsjp_signals (ticker, signal_date, score, close_price)
                   VALUES (?, ?, ?, ?)""",
                (s["ticker"], today_str, s.get("score"), s.get("close_price"))
            )
        conn.commit()
    logger.info(f"[BSJP DB] Saved {len(signals)} signals for {today_str}.")


def get_pending_bsjp_signals(signal_date: str) -> list[dict]:
    """Ambil sinyal BSJP pending (belum ada outcome) untuk tanggal tertentu."""
    path = _get_db_path()
    migrate_bsjp_table()
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM bsjp_signals WHERE signal_date=? AND outcome='pending'",
            (signal_date,)
        )
        return [dict(row) for row in cur.fetchall()]


def get_latest_pending_bsjp_signals(before_date: str) -> tuple[Optional[str], list[dict]]:
    """
    Ambil semua sinyal BSJP berstatus 'pending' dari tanggal sinyal terakhir
    sebelum before_date (menangani akhir pekan Jumat -> Senin & hari libur).
    """
    path = _get_db_path()
    migrate_bsjp_table()
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """SELECT MAX(signal_date) AS target_date
               FROM bsjp_signals
               WHERE signal_date < ? AND outcome = 'pending'""",
            (before_date,)
        ).fetchone()
        target_date = row["target_date"] if row else None
        if not target_date:
            return None, []
        cur = conn.execute(
            "SELECT * FROM bsjp_signals WHERE signal_date=? AND outcome='pending'",
            (target_date,)
        )
        return target_date, [dict(r) for r in cur.fetchall()]


def update_bsjp_outcome(ticker: str, signal_date: str, open_price: float,
                         high_price: float, pct_change: float, outcome: str):
    """Update outcome rekap BSJP untuk ticker + tanggal signal."""
    path = _get_db_path()
    with sqlite3.connect(path) as conn:
        conn.execute(
            """UPDATE bsjp_signals
               SET open_next_day=?, high_next_day=?, pct_change=?, outcome=?
               WHERE ticker=? AND signal_date=?""",
            (open_price, high_price, pct_change, outcome, ticker, signal_date)
        )
        conn.commit()
    logger.debug(f"[BSJP DB] Updated outcome {ticker} {signal_date}: {outcome} {pct_change:.2%}")

