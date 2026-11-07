"""
BSJP Engine — Beli Sore Jual Profit
Screener yang berjalan pukul 15:45 WIB setiap hari bursa.
Menggunakan data intraday hari yang sama (5M, 15M).
Data diambil dari Yahoo Finance (yfinance).

Kriteria (dari spec user):
  EMA 9 > EMA 20 (5M)         → 20 poin  [HARD FILTER]
  Harga > VWAP & VWAP naik    → 20 poin  [HARD FILTER: harga > VWAP]
  RSI 14 zona 52–68 (5M)      → 15 poin
  Volume Expansion ≥1,2× (5M) → 15 poin
  CLV ≥ 0,75 (intraday)       → 15 poin  [HARD FILTER]
  Relative Strength vs IHSG   → 10 poin
  Candle 15M bullish quality  →  5 poin
  Total                       = 100 poin

Klasifikasi:
  90–100 : kandidat prioritas
  80–89  : kandidat layak diuji
  70–79  : observasi
  <70    : tidak dipilih

Syarat wajib: harga di atas VWAP, EMA 9 di atas EMA 20, dan CLV minimal 0,75.
"""

import logging
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_intraday(ticker: str, interval: str, target_date: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Ambil data intraday dari yfinance, kembalikan hanya baris hari tertentu (WIB).
    Kolom: open, high, low, close, volume (lowercase).
    """
    try:
        import yfinance as yf
        import pytz

        yf_ticker = ticker if ticker.endswith(".JK") else ticker + ".JK"
        raw = yf.download(
            yf_ticker,
            period="5d",
            interval=interval,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if raw is None or raw.empty:
            return None

        # Flatten MultiIndex kolom (yfinance v0.2+)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [c.lower() for c in raw.columns]

        # Pastikan index ber-timezone; konversi ke WIB
        wib = pytz.timezone("Asia/Jakarta")
        if raw.index.tzinfo is None:
            raw.index = raw.index.tz_localize("UTC")
        raw.index = raw.index.tz_convert(wib)

        date_str = target_date or datetime.now(wib).strftime("%Y-%m-%d")
        df = raw[raw.index.strftime("%Y-%m-%d") == date_str].copy()
        return df if not df.empty else None
    except Exception as e:
        logger.warning(f"[BSJP] fetch_intraday {ticker} {interval}: {e}")
        return None


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Hitung cumulative session VWAP sejak candle pertama hari itu.
    VWAP(t) = sum(TP × Vol) / sum(Vol)
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_tpv = (tp * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    return cum_tpv / cum_vol.replace(0, np.nan)


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # Handle pure uptrend (avg_loss = 0)
    rsi = rsi.fillna(pd.Series(
        np.where(avg_gain > 0, 100.0, 50.0), index=series.index
    ))
    return rsi


def _ihsg_return_today() -> Optional[float]:
    """Return IHSG hari ini (pct change dari close kemarin ke close/terakhir hari ini)."""
    try:
        import yfinance as yf
        ihsg = yf.download("^JKSE", period="5d", interval="1d",
                           auto_adjust=True, progress=False, threads=False)
        if ihsg is None or len(ihsg) < 2:
            return None
        if isinstance(ihsg.columns, pd.MultiIndex):
            ihsg.columns = ihsg.columns.get_level_values(0)
        ihsg.columns = [c.lower() for c in ihsg.columns]
        closes = ihsg["close"].dropna()
        if len(closes) < 2:
            return None
        return float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2])
    except Exception as e:
        logger.warning(f"[BSJP] IHSG return: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def compute_bsjp_score(
    ticker: str,
    target_date: Optional[str] = None,
    df5: Optional[pd.DataFrame] = None,
    df15: Optional[pd.DataFrame] = None,
    ihsg_ret: Optional[float] = None,
) -> dict:
    """
    Hitung skor BSJP untuk satu saham pada hari ini / target_date.
    Returns dict dengan keys:
        score, ema_ok, vwap_ok, rsi_ok, volume_ok, clv_ok, rs_ok, candle_ok,
        hard_filter_pass, close_price, reason
    """
    result = {
        "ticker": ticker,
        "score": 0,
        "ema_ok": False,
        "vwap_ok": False,
        "rsi_ok": False,
        "volume_ok": False,
        "clv_ok": False,
        "rs_ok": False,
        "candle_ok": False,
        "hard_filter_pass": False,
        "close_price": None,
        "reason": "",
    }

    # ── 1. Ambil data 5M ────────────────────────────────────────────────────
    if df5 is None:
        df5 = _fetch_intraday(ticker, "5m", target_date)
    if df5 is None or len(df5) < 10:
        result["reason"] = "INSUFFICIENT_5M_DATA"
        return result

    # ── 2. EMA 9 & EMA 20 (5M) — 20 poin [Syarat Wajib] ────────────────────
    ema9 = _ema(df5["close"], 9)
    ema20 = _ema(df5["close"], 20)
    last_ema9 = float(ema9.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    result["ema_ok"] = bool(last_ema9 > last_ema20)

    # ── 3. VWAP Session kumulatif (5M) — 20 poin [Syarat Wajib Harga > VWAP] ─
    vwap_series = _session_vwap(df5)
    last_close_5m = float(df5["close"].iloc[-1])
    last_vwap = float(vwap_series.iloc[-1]) if not vwap_series.empty else None
    result["close_price"] = last_close_5m

    if last_vwap is None or np.isnan(last_vwap):
        result["reason"] = "VWAP_UNAVAILABLE"
        return result

    price_above_vwap = bool(last_close_5m > last_vwap)
    # VWAP slope: VWAP candle terakhir > VWAP 3 candle sebelumnya
    if len(vwap_series) >= 4:
        vwap_prev3 = float(vwap_series.iloc[-4])
        vwap_slope_up = bool(last_vwap > vwap_prev3)
    else:
        vwap_slope_up = False
    result["vwap_ok"] = bool(price_above_vwap and vwap_slope_up)

    # ── 4. RSI 14 zona 52–68 (5M) — 15 poin ────────────────────────────────
    rsi_series = _rsi(df5["close"], 14)
    last_rsi = float(rsi_series.iloc[-1])
    result["rsi_ok"] = bool(52.0 <= last_rsi <= 68.0)

    # ── 5. Volume Expansion (5M) — 15 poin ──────────────────────────────────
    # Avg volume 3 candle terakhir ≥ 1,2× avg 6 candle sebelumnya
    if len(df5) >= 9:
        vol_last3 = float(df5["volume"].iloc[-3:].mean())
        vol_prev6 = float(df5["volume"].iloc[-9:-3].mean())
        result["volume_ok"] = bool((vol_prev6 > 0) and (vol_last3 >= 1.2 * vol_prev6))
    else:
        result["volume_ok"] = False

    # ── 6. CLV Intraday — 15 poin [Syarat Wajib ≥ 0,75] ─────────────────────
    # CLV = ((Close - Low) - (High - Close)) / (High - Low)
    day_h = float(df5["high"].max())
    day_l = float(df5["low"].min())
    day_c = last_close_5m
    if day_h > day_l:
        clv_intraday = ((day_c - day_l) - (day_h - day_c)) / (day_h - day_l)
    else:
        clv_intraday = 0.0
    result["clv_ok"] = bool(clv_intraday >= 0.75)

    # ── 7. Relative Strength vs IHSG — 10 poin ───────────────────────────────
    first_open = float(df5["open"].iloc[0])
    stock_ret = (last_close_5m - first_open) / first_open if first_open > 0 else 0.0

    if ihsg_ret is None:
        ihsg_ret = _ihsg_return_today()

    if ihsg_ret is not None:
        result["rs_ok"] = bool(stock_ret > ihsg_ret)
    else:
        result["rs_ok"] = False

    # ── 8. Candle 15M bullish berkualitas — 5 poin ───────────────────────────
    if df15 is None:
        df15 = _fetch_intraday(ticker, "15m", target_date)

    if df15 is not None and len(df15) >= 1:
        row15 = df15.iloc[-1]
        h15 = float(row15["high"])
        l15 = float(row15["low"])
        c15 = float(row15["close"])
        o15 = float(row15["open"])
        candle_len = h15 - l15
        if candle_len > 0:
            # Bullish candle: Close > Open
            is_bullish = bool(c15 > o15)
            # Close dekat high: close ≥ low + 0.7×candle_length
            close_near_high = bool(c15 >= (l15 + 0.7 * candle_len))
            # Upper shadow ≤ 30% dari panjang candle
            upper_shadow = h15 - max(c15, o15)
            upper_shadow_ok = bool(upper_shadow <= (0.3 * candle_len))
            result["candle_ok"] = bool(is_bullish and close_near_high and upper_shadow_ok)
        else:
            result["candle_ok"] = False
    else:
        result["candle_ok"] = False

    # ── 9. Hard Filter [Syarat Wajib] ─────────────────────────────────────────
    # Syarat wajib: harga di atas VWAP, EMA 9 di atas EMA 20, dan CLV minimal 0,75
    result["hard_filter_pass"] = bool(
        result["ema_ok"] and price_above_vwap and result["clv_ok"]
    )

    if not result["hard_filter_pass"]:
        result["score"] = 0
        result["reason"] = "HARD_FILTER_FAILED"
        return result

    # ── 10. Hitung Total Skor (Total 100 poin) ────────────────────────────────
    score = 0
    if result["ema_ok"]:
        score += 20
    if result["vwap_ok"]:
        score += 20
    if result["rsi_ok"]:
        score += 15
    if result["volume_ok"]:
        score += 15
    if result["clv_ok"]:
        score += 15
    if result["rs_ok"]:
        score += 10
    if result["candle_ok"]:
        score += 5

    result["score"] = score
    result["reason"] = "OK"
    return result


def run_bsjp_screener(universe: List[str]) -> List[Dict[str, Any]]:
    """
    Jalankan BSJP screener untuk seluruh universe.
    Kembalikan daftar saham yang lolos (skor ≥ 70), diurutkan dari skor tertinggi.
    """
    ihsg_ret = _ihsg_return_today()
    results = []
    for ticker in universe:
        try:
            res = compute_bsjp_score(ticker, ihsg_ret=ihsg_ret)
            if res["score"] >= 70:
                results.append(res)
                logger.info(
                    f"[BSJP] {ticker} → score={res['score']} "
                    f"ema={res['ema_ok']} vwap={res['vwap_ok']} "
                    f"rsi={res['rsi_ok']} vol={res['volume_ok']} "
                    f"clv={res['clv_ok']} rs={res['rs_ok']} candle={res['candle_ok']}"
                )
            else:
                logger.debug(
                    f"[BSJP] {ticker} SKIP score={res['score']} reason={res['reason']}"
                )
        except Exception as e:
            logger.error(f"[BSJP] Error on {ticker}: {e}", exc_info=True)
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
