"""
Saber Trader — Google Spreadsheet (SPS) Service
Handles generation of comprehensive signal recap (sorted newest to oldest),
computing outcome status (TP Hit, SL Hit, Floating Profit, Floating Loss),
syncing data to Google Sheets via Webhook (Google Apps Script),
and formatting Telegram notification messages.
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_db_path() -> str:
    db_url = settings.DATABASE_URL_SYNC
    return db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "./idx_signal_bot.db"


def fetch_all_signals_recap() -> Tuple[List[Dict], Dict]:
    """
    Fetch all trading signals from DB sorted from newest to oldest (created_at DESC).
    Computes status: TP Hit, SL Hit, Floating Profit, or Floating Loss.
    Returns:
        (signals_list, summary_dict)
    """
    db_path = _get_db_path()
    signals: List[Dict] = []
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, ticker, timeframe, signal, raw_score, confidence_score,
                   entry_price, tp1, tp2, tp3, stop_loss_atr, stop_loss_conservative,
                   outcome_status, outcome_price, outcome_pnl_pct, tp_hit, sl_hit, tp2_hit,
                   max_price_seen, min_price_seen, created_at
            FROM signals
            WHERE UPPER(signal) IN ('STRONG BUY', 'BUY', 'WATCHLIST')
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        for idx, row in enumerate(rows, start=1):
            entry_price = float(row["entry_price"]) if row["entry_price"] else 0.0
            tp1 = float(row["tp1"]) if row["tp1"] else 0.0
            tp2 = float(row["tp2"]) if row["tp2"] else 0.0
            stop_loss = float(row["stop_loss_atr"] or row["stop_loss_conservative"] or 0.0)
            
            outcome_status = (row["outcome_status"] or "PENDING").upper()
            tp_hit = bool(row["tp_hit"])
            tp2_hit = bool(row["tp2_hit"])
            sl_hit = bool(row["sl_hit"])
            
            # Determine current / outcome price
            if row["outcome_price"] and float(row["outcome_price"]) > 0:
                current_price = float(row["outcome_price"])
            elif entry_price > 0:
                current_price = entry_price
            else:
                current_price = 0.0

            # Calculate PnL percentage
            if row["outcome_pnl_pct"] is not None:
                pnl_pct = round(float(row["outcome_pnl_pct"]), 2)
            elif entry_price > 0 and current_price > 0:
                pnl_pct = round(((current_price - entry_price) / entry_price) * 100.0, 2)
            else:
                pnl_pct = 0.0

            # Determine human-readable status
            if tp2_hit or outcome_status == "TP2_HIT":
                status = "TP2 Hit"
            elif tp_hit or outcome_status == "TP_HIT":
                status = "TP Hit"
            elif sl_hit or outcome_status == "SL_HIT":
                status = "SL Hit"
            elif outcome_status == "EXPIRED":
                status = "Expired"
            else:
                # Active / Floating signal
                if pnl_pct > 0.05:
                    status = "Floating Profit"
                elif pnl_pct < -0.05:
                    status = "Floating Loss"
                else:
                    status = "Floating BEP"

            created_at_str = str(row["created_at"])[:16] if row["created_at"] else ""

            signals.append({
                "no": idx,
                "id": row["id"],
                "date": created_at_str,
                "ticker": row["ticker"],
                "timeframe": (row["timeframe"] or "1d").upper(),
                "signal": row["signal"],
                "score": round(float(row["raw_score"]), 1) if row["raw_score"] is not None else 0.0,
                "entry_price": entry_price,
                "current_price": current_price,
                "tp1": tp1,
                "tp2": tp2,
                "stop_loss": stop_loss,
                "pnl_pct": pnl_pct,
                "status": status,
            })

    except Exception as e:
        logger.error(f"[SpreadsheetService] Error querying signals: {e}", exc_info=True)

    # Compute summary metrics
    total = len(signals)
    tp_hits = sum(1 for s in signals if "TP" in s["status"])
    sl_hits = sum(1 for s in signals if "SL" in s["status"])
    floating_profits = sum(1 for s in signals if s["status"] == "Floating Profit")
    floating_losses = sum(1 for s in signals if s["status"] == "Floating Loss")
    expired = sum(1 for s in signals if s["status"] in ("Expired", "Floating BEP"))
    
    resolved_count = tp_hits + sl_hits
    winrate = round((tp_hits / resolved_count) * 100.0, 1) if resolved_count > 0 else 0.0

    summary = {
        "total_signals": total,
        "tp_hits": tp_hits,
        "sl_hits": sl_hits,
        "floating_profits": floating_profits,
        "floating_losses": floating_losses,
        "expired": expired,
        "resolved_winrate": winrate,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M WIB"),
    }

    return signals, summary


async def sync_signals_to_google_sheet(signals: List[Dict], summary: Dict) -> bool:
    """
    Sends signal recap data to Google Apps Script Webhook.
    Note: follow_redirects=True is required because Google Apps Script responds with 302 redirect.
    """
    settings = get_settings()
    webhook_url = getattr(settings, "GOOGLE_SHEET_WEBHOOK_URL", "")

    if not webhook_url:
        logger.warning("[SpreadsheetService] GOOGLE_SHEET_WEBHOOK_URL is not set in .env. Skipping Google Sheets push.")
        return False

    payload = {
        "updated_at": summary.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M WIB")),
        "summary": summary,
        "signals": signals,
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code == 200:
                logger.info(f"[SpreadsheetService] Successfully synced {len(signals)} signals to Google Sheets.")
                return True
            else:
                logger.error(f"[SpreadsheetService] Failed to sync to Google Sheets: HTTP {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        logger.error(f"[SpreadsheetService] Error syncing to Google Sheets: {e}", exc_info=True)
        return False


def format_sps_recap_message(summary: Dict, sheet_url: Optional[str] = None) -> str:
    """
    Formats Telegram message for the 17:09 WIB SPS Signal Recap.
    """
    time_str = summary.get("generated_at", datetime.now().strftime("%d %b %Y %H:%M WIB"))
    total = summary.get("total_signals", 0)
    tp_hits = summary.get("tp_hits", 0)
    sl_hits = summary.get("sl_hits", 0)
    floating_profits = summary.get("floating_profits", 0)
    floating_losses = summary.get("floating_losses", 0)
    expired = summary.get("expired", 0)
    winrate = summary.get("resolved_winrate", 0.0)

    # Link section
    if sheet_url and sheet_url.strip():
        link_line = f'🔗 <b>Buka Spreadsheet Lengkap:</b>\n👉 <a href="{sheet_url.strip()}">Klik Di Sini untuk Membuka SPS Sinyal</a>'
    else:
        link_line = '🔗 <b>Spreadsheet (SPS):</b> <i>URL belum diatur di .env (GOOGLE_SHEET_VIEW_URL)</i>'

    msg = f"""📊 <b>REKAPITULASI SINYAL SAHAM (SPS)</b>
━━━━━━━━━━━━━━━━━━━━━━
📅 Update: <b>{time_str}</b>
📈 Total Sinyal: <b>{total}</b>
🎯 Winrate Sinyal Selesai: <b>{winrate:.1f}%</b>

📋 <b>Ringkasan Status:</b>
├─ 🟢 TP Hit           : <b>{tp_hits}</b>
├─ 🔴 SL Hit           : <b>{sl_hits}</b>
├─ 📈 Floating Profit  : <b>{floating_profits}</b>
├─ 📉 Floating Loss    : <b>{floating_losses}</b>
└─ ⚪ BEP / Expired    : <b>{expired}</b>

{link_line}
━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>Saber Trader — Rekapitulasi Sinyal Otomatis</i>"""

    return msg
