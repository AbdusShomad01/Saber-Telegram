"""
Unit tests for BSJP (Beli Sore Jual Profit) Engine and DB.
Tests all criteria:
- EMA 9 > EMA 20 (20 pts, Hard Filter)
- Price > VWAP & VWAP slope up (20 pts, Hard Filter: price > VWAP)
- RSI 14 in [52, 68] (15 pts)
- Volume Expansion >= 1.2x (15 pts)
- CLV >= 0.75 (15 pts, Hard Filter)
- Relative Strength vs IHSG (10 pts)
- Candle 15M Bullish Quality (5 pts)
Total = 100 pts.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from services.bsjp_engine import compute_bsjp_score
from services.bsjp_db import (
    migrate_bsjp_table, save_bsjp_signals, get_pending_bsjp_signals, update_bsjp_outcome
)


def _make_dummy_data(
    n_bars=40,
    base_price=1000.0,
    uptrend=True,
    vol_expansion=True,
    clv_high=True,
    candle_bullish=True,
):
    """Buat data 5M dan 15M sintesis untuk testing."""
    times_5m = [datetime(2026, 11, 7, 9, 0) + timedelta(minutes=5 * i) for i in range(n_bars)]
    
    closes = []
    highs = []
    lows = []
    opens = []
    volumes = []
    
    price = base_price
    for i in range(n_bars):
        if uptrend:
            price += 2.0
        else:
            price -= 2.0
        
        o = price - 1.0
        c = price
        if clv_high:
            # Close very close to high -> CLV >= 0.75
            h = c + 0.5
            l = o - 10.0
        else:
            # Close near low -> CLV < 0.75
            h = c + 20.0
            l = c - 1.0
            
        # Volume
        if vol_expansion and i >= n_bars - 3:
            v = 25000.0
        else:
            v = 10000.0
            
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        volumes.append(v)
        
    df5 = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    }, index=pd.to_datetime(times_5m))
    
    # Buat df15
    times_15m = [datetime(2026, 11, 7, 9, 0) + timedelta(minutes=15 * i) for i in range(n_bars // 3)]
    c15 = closes[-1]
    o15 = closes[-3] if candle_bullish else closes[-1] + 10.0
    h15 = c15 + 0.5 if clv_high else c15 + 20.0
    l15 = o15 - 5.0 if candle_bullish else c15 - 5.0
    df15 = pd.DataFrame({
        "open": [o15] * len(times_15m),
        "high": [h15] * len(times_15m),
        "low": [l15] * len(times_15m),
        "close": [c15] * len(times_15m),
        "volume": [40000.0] * len(times_15m),
    }, index=pd.to_datetime(times_15m))
    
    return df5, df15


def test_bsjp_full_score_and_criteria():
    """Test skenario ketika kriteria terpenuhi."""
    df5, df15 = _make_dummy_data(uptrend=True, vol_expansion=True, clv_high=True, candle_bullish=True)
    # Berikan IHSG return lebih rendah dari saham agar Relative Strength lolos
    ihsg_ret = -0.01

    res = compute_bsjp_score("BBCA", df5=df5, df15=df15, ihsg_ret=ihsg_ret)
    assert res["hard_filter_pass"] is True
    assert res["ema_ok"] is True
    assert res["vwap_ok"] is True
    assert res["clv_ok"] is True
    assert res["rs_ok"] is True
    assert res["candle_ok"] is True
    assert res["volume_ok"] is True
    assert res["score"] >= 80  # Lolosan kriteria kuat (layak / prioritas)


def test_bsjp_hard_filter_ema_fail():
    """Jika EMA9 <= EMA20 (downtrend), hard filter gagal -> Skor 0."""
    df5, df15 = _make_dummy_data(uptrend=False)
    res = compute_bsjp_score("BBCA", df5=df5, df15=df15, ihsg_ret=0.0)
    assert res["ema_ok"] is False
    assert res["hard_filter_pass"] is False
    assert res["score"] == 0
    assert res["reason"] == "HARD_FILTER_FAILED"


def test_bsjp_hard_filter_clv_fail():
    """Jika CLV < 0.75 (close di dekat low), hard filter gagal -> Skor 0."""
    df5, df15 = _make_dummy_data(clv_high=False)
    res = compute_bsjp_score("BBCA", df5=df5, df15=df15, ihsg_ret=0.0)
    assert res["clv_ok"] is False
    assert res["hard_filter_pass"] is False
    assert res["score"] == 0
    assert res["reason"] == "HARD_FILTER_FAILED"


def test_bsjp_db_operations(tmp_path, monkeypatch):
    """Test tabel SQLite bsjp_signals: migrate, insert, duplicate prevention, update."""
    db_file = tmp_path / "test_bsjp.db"
    monkeypatch.setattr("services.bsjp_db._get_db_path", lambda: str(db_file))

    migrate_bsjp_table()

    # Simpan signal hari ini
    signals = [
        {"ticker": "BBCA", "score": 95, "close_price": 3200},
        {"ticker": "BMRI", "score": 85, "close_price": 6500},
    ]
    save_bsjp_signals(signals, signal_date="2026-11-06")

    # Pastikan tersimpan
    pending = get_pending_bsjp_signals("2026-11-06")
    assert len(pending) == 2
    assert pending[0]["ticker"] == "BBCA"

    # Cek duplikasi: panggil save lagi dengan data yang sama tidak menambah row
    save_bsjp_signals(signals, signal_date="2026-11-06")
    pending2 = get_pending_bsjp_signals("2026-11-06")
    assert len(pending2) == 2

    # Update outcome besok pagi
    update_bsjp_outcome(
        ticker="BBCA",
        signal_date="2026-11-06",
        open_price=3220,
        high_price=3264,
        pct_change=0.02,
        outcome="profit",
    )

    # Setelah diupdate, BBCA sudah tidak pending lagi
    pending_after = get_pending_bsjp_signals("2026-11-06")
    assert len(pending_after) == 1
    assert pending_after[0]["ticker"] == "BMRI"
