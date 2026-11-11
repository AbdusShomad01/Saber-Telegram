"""
BSJP Engine — Beli Sore Jual Profit
Screener yang berjalan pukul 15:45 WIB setiap hari bursa.
Menggunakan data harian (1d) terbaru dari Yahoo Finance (yfinance).

Kriteria Screening (wajib lolos semua — AND):
  1. Current Price Change >= +2%
  2. Current Price Change <= +4%
  3. Current Price >= 1 × Price MA 20
  4. Volume (Shares) Today >= 1.2 × Volume (Shares) MA 20
  5. Value (Today) >= Rp 10.000.000.000 (10 Miliar)
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Parameter Screener BSJP (sesuai spesifikasi Stockbit screener user)
BSJP_MIN_PRICE_CHANGE_PCT = 2.0
BSJP_MAX_PRICE_CHANGE_PCT = 4.0
BSJP_PRICE_MA_PERIOD = 20
BSJP_VOLUME_MA_PERIOD = 20
BSJP_MIN_VOLUME_MA_MULTIPLIER = 1.2
BSJP_MIN_VALUE_TODAY_IDR = 10_000_000_000  # Rp 10 Miliar

# Monkeypatch yfinance User-Agent agar tidak terkena blokir / HTTP 429 Rate Limit
try:
    import yfinance.data as yfd
    yfd.YfData.user_agent_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
except Exception as e:
    logger.warning(f"Failed to monkeypatch yfinance User-Agent: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_daily(ticker: str) -> Optional[pd.DataFrame]:
    """
    Ambil data harian 3 bulan dari yfinance via Ticker.history() (thread-safe)
    untuk menghitung MA 20, perubahan harga, volume hari ini, dan value hari ini.
    """
    try:
        import yfinance as yf

        yf_ticker = ticker if ticker.endswith(".JK") else ticker + ".JK"
        raw = yf.Ticker(yf_ticker).history(
            period="3mo",
            interval="1d",
            auto_adjust=True,
            timeout=15,
        )
        if raw is None or raw.empty:
            return None

        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [str(c).lower() for c in raw.columns]

        if "close" not in raw.columns or "volume" not in raw.columns:
            return None

        cols = ["close", "volume"] + (["value"] if "value" in raw.columns else [])
        df = raw[cols].copy()
        for col in cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close", "volume"])
        df = df[df["close"] > 0]
        return df if not df.empty else None
    except Exception as e:
        logger.warning(f"[BSJP] fetch_daily {ticker}: {e}")
        return None


def _compute_ranking_score(volume_ratio: float, value_today: float) -> float:
    """
    Hitung skor ranking (70–100) untuk kandidat yang sudah lolos semua 5 kriteria.
    Mengutamakan lonjakan volume terhadap MA20 dan besarnya likuiditas nilai transaksi.
    """
    vol_bonus = min(max((volume_ratio - BSJP_MIN_VOLUME_MA_MULTIPLIER) * 10.0, 0.0), 15.0)
    val_miliar = value_today / 1_000_000_000.0
    val_bonus = min(max((val_miliar - 10.0) * 0.3, 0.0), 15.0)
    return round(min(100.0, 70.0 + vol_bonus + val_bonus), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_bsjp_stock(ticker: str, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Evaluasi satu saham terhadap 5 syarat screener BSJP baru:
      1. Current Price Change >= 2%
      2. Current Price Change <= 4%
      3. Current Price >= 1 × Price MA 20
      4. Volume (Shares) Today >= 1.2 × Volume (Shares) MA 20
      5. Value (Today) >= Rp 10.000.000.000
    """
    result: Dict[str, Any] = {
        "ticker": ticker,
        "passed": False,
        "hard_filter_pass": False,
        "score": 0.0,
        "close_price": None,
        "prev_close": None,
        "price_change_pct": None,
        "price_ma20": None,
        "volume_today": None,
        "volume_ma20": None,
        "volume_ratio": None,
        "value_today": None,
        "checks": {
            "change_min_ok": False,
            "change_max_ok": False,
            "above_ma20_ok": False,
            "volume_ma20_ok": False,
            "value_ok": False,
        },
        "reason": "",
    }

    if df is None:
        df = _fetch_daily(ticker)

    min_bars = max(BSJP_PRICE_MA_PERIOD, BSJP_VOLUME_MA_PERIOD)
    if df is None or len(df) < min_bars:
        result["reason"] = "INSUFFICIENT_DAILY_DATA"
        return result

    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    if "close" not in df.columns or "volume" not in df.columns:
        result["reason"] = "MISSING_REQUIRED_COLUMNS"
        return result

    current_price = float(df["close"].iloc[-1])
    prev_close = float(df["close"].iloc[-2])
    if prev_close <= 0 or current_price <= 0:
        result["reason"] = "INVALID_PRICE"
        return result

    price_change_pct = ((current_price - prev_close) / prev_close) * 100.0
    price_ma20 = float(df["close"].tail(BSJP_PRICE_MA_PERIOD).mean())

    volume_today = float(df["volume"].iloc[-1])
    volume_ma20 = float(df["volume"].tail(BSJP_VOLUME_MA_PERIOD).mean())
    volume_ratio = (volume_today / volume_ma20) if volume_ma20 > 0 else 0.0

    if "value" in df.columns and pd.notna(df["value"].iloc[-1]):
        value_today = float(df["value"].iloc[-1])
    else:
        value_today = current_price * volume_today

    result["close_price"] = current_price
    result["prev_close"] = prev_close
    result["price_change_pct"] = round(price_change_pct, 2)
    result["price_ma20"] = round(price_ma20, 2)
    result["volume_today"] = volume_today
    result["volume_ma20"] = round(volume_ma20, 2)
    result["volume_ratio"] = round(volume_ratio, 2)
    result["value_today"] = value_today

    eps = 1e-9
    checks = {
        "change_min_ok": bool(price_change_pct >= BSJP_MIN_PRICE_CHANGE_PCT - eps),
        "change_max_ok": bool(price_change_pct <= BSJP_MAX_PRICE_CHANGE_PCT + eps),
        "above_ma20_ok": bool(current_price >= price_ma20 - eps),
        "volume_ma20_ok": bool(volume_ma20 > 0 and volume_today >= (BSJP_MIN_VOLUME_MA_MULTIPLIER * volume_ma20) - eps),
        "value_ok": bool(value_today >= BSJP_MIN_VALUE_TODAY_IDR - eps),
    }
    result["checks"] = checks

    all_passed = all(checks.values())
    result["passed"] = all_passed
    result["hard_filter_pass"] = all_passed

    if not all_passed:
        failed = [k for k, ok in checks.items() if not ok]
        result["reason"] = f"FAILED: {', '.join(failed)}"
        return result

    result["score"] = _compute_ranking_score(volume_ratio, value_today)
    result["reason"] = "OK"
    return result


def run_bsjp_screener(universe: List[str]) -> List[Dict[str, Any]]:
    """
    Jalankan BSJP screener untuk seluruh universe dengan safe rate-limiting.
    Menggunakan 4 worker terkendali + micro-delay agar cepat namun tetap aman dari blokir Yahoo Finance.
    Kembalikan daftar saham yang lolos seluruh 5 kriteria, diurutkan terbaik terlebih dahulu.
    """
    results: List[Dict[str, Any]] = []
    total = len(universe)
    print(f"🔍 Mulai scanning {total} saham BSJP (Safe Rate Limit mode)...")

    def _eval(ticker: str):
        try:
            time.sleep(0.12)
            return evaluate_bsjp_stock(ticker)
        except Exception as e:
            logger.debug(f"[BSJP] Error on {ticker}: {e}")
            return None

    completed = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_eval, t): t for t in universe}
        for future in as_completed(futures):
            completed += 1
            res = future.result()
            if res and res.get("passed"):
                results.append(res)
                print(
                    f"  ⭐ [{completed}/{total}] {res['ticker']} LOLOS BSJP "
                    f"(+{res['price_change_pct']}%, Vol {res['volume_ratio']}x MA20, "
                    f"Val Rp{res['value_today']/1e9:.1f}M)"
                )
                logger.info(f"[BSJP] {res['ticker']} LOLOS score={res['score']}")
            elif completed % 25 == 0 or completed == total:
                print(f"  ⏳ [{completed}/{total}] Memeriksa saham... (Aman & stabil)")

    results.sort(key=lambda x: (x["score"], x.get("value_today") or 0), reverse=True)
    print(f"\n✅ Selesai! Ditemukan {len(results)} kandidat BSJP.")
    return results
