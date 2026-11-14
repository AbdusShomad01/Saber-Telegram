"""
Tests for TP / SL real-time monitor & outcome tracker progression logic.
Verifies that:
1. Historical bars before signal creation (e.g. 30-day bars, morning session before noon scan) are ignored.
2. Chronological order is strictly respected (TP before SL -> win; SL before TP -> loss).
3. WATCHLIST signals must touch entry_price before TP/SL can trigger.
4. Timezone differences (UTC in DB vs WIB in market) are accurately handled.
"""

from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import pytest

from services.outcome_tracker import (
    filter_candles_after_signal,
    evaluate_signal_progression,
)


@pytest.fixture
def base_signal():
    return {
        "id": 101,
        "ticker": "BBCA",
        "signal": "STRONG BUY",
        "entry_price": 5000.0,
        "tp1": 5250.0,  # +5%
        "tp2": 5500.0,  # +10%
        "stop_loss_atr": 4850.0,  # -3%
        "created_at": "2026-11-13 02:30:00",  # 02:30 UTC = 09:30 WIB
    }


def test_historical_candles_before_signal_are_ignored(base_signal):
    """30-day historical highs and lows before signal creation must not trigger TP or SL."""
    # 5m bars in Asia/Jakarta
    # 09:00 - 09:25: Old bars that had high=6000 (above TP1) and low=4500 (below SL)
    # 09:30 - 10:00: Bars after signal where price is around 5000-5050 (neither TP nor SL hit)
    times = pd.date_range("2026-11-13 09:00", "2026-11-13 10:00", freq="5min", tz="Asia/Jakarta")
    
    highs = []
    lows = []
    closes = []
    
    for t in times:
        if t.time() < datetime.strptime("09:30", "%H:%M").time():
            # Old bars with extreme prices
            highs.append(6000.0)  # Would falsely trigger TP1 if not filtered
            lows.append(4500.0)   # Would falsely trigger SL if not filtered
            closes.append(5000.0)
        else:
            # Active bars after signal
            highs.append(5050.0)
            lows.append(4980.0)
            closes.append(5020.0)
            
    df = pd.DataFrame({
        "date": times,
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [1000] * len(times),
    })

    # Filtered check
    filtered = filter_candles_after_signal(base_signal, df)
    assert len(filtered) == 7  # 09:30, 09:35, 09:40, 09:45, 09:50, 09:55, 10:00
    assert float(filtered["high"].max()) == 5050.0
    assert float(filtered["low"].min()) == 4980.0

    # Progression check
    res = evaluate_signal_progression(base_signal, df)
    assert res["status"] == "PENDING"
    assert res["tp_hit"] is False
    assert res["sl_hit"] is False
    assert res["max_seen"] == 5050.0
    assert res["min_seen"] == 4980.0
    assert res["current_price"] == 5020.0


def test_noon_scan_ignores_morning_session(base_signal):
    """Noon signal (created at 12:30 WIB = 05:30 UTC) must ignore 09:00-12:00 morning session."""
    base_signal["created_at"] = "2026-11-13 05:30:00"  # 12:30 WIB
    
    # Morning bars hit 5300 (above TP1) at 10:00 WIB
    times = pd.date_range("2026-11-13 09:00", "2026-11-13 14:00", freq="15min", tz="Asia/Jakarta")
    highs = []
    lows = []
    closes = []
    
    for t in times:
        if t.time() < datetime.strptime("12:30", "%H:%M").time():
            highs.append(5300.0)  # morning high
            lows.append(4950.0)
            closes.append(5000.0)
        else:
            highs.append(5020.0)  # afternoon flat
            lows.append(4980.0)
            closes.append(5000.0)
            
    df = pd.DataFrame({
        "date": times,
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [1000] * len(times),
    })

    res = evaluate_signal_progression(base_signal, df)
    assert res["status"] == "PENDING"
    assert res["tp_hit"] is False
    assert res["max_seen"] == 5020.0


def test_chronological_tp_before_sl():
    """If candle touches TP1, subsequent drop below SL must not turn winning trade into loss."""
    signal = {
        "id": 102,
        "ticker": "ASII",
        "signal": "BUY",
        "entry_price": 5000.0,
        "tp1": 5200.0,
        "tp2": 5400.0,
        "stop_loss_atr": 4800.0,
        "created_at": "2026-11-13 02:00:00",  # 09:00 WIB
    }
    
    # 09:05: touches 5250 (TP1 Hit!)
    # 09:10: crashes to 4700 (below SL)
    times = pd.date_range("2026-11-13 09:05", "2026-11-13 09:15", freq="5min", tz="Asia/Jakarta")
    df = pd.DataFrame({
        "date": times,
        "open": [5000.0, 5200.0, 4800.0],
        "high": [5250.0, 5200.0, 4850.0],
        "low":  [4980.0, 4700.0, 4750.0],
        "close": [5200.0, 4750.0, 4800.0],
        "volume": [1000, 2000, 1500],
    })

    res = evaluate_signal_progression(signal, df)
    assert res["status"] == "TP1_HIT"
    assert res["tp_hit"] is True
    assert res["sl_hit"] is False
    assert res["outcome_price"] == 5200.0
    assert res["pnl_pct"] == pytest.approx(4.0)


def test_chronological_sl_before_tp():
    """If candle touches SL, subsequent rally above TP must not turn stopped out trade into win."""
    signal = {
        "id": 103,
        "ticker": "BBRI",
        "signal": "BUY",
        "entry_price": 4000.0,
        "tp1": 4200.0,
        "tp2": 4400.0,
        "stop_loss_atr": 3900.0,
        "created_at": "2026-11-13 02:00:00",  # 09:00 WIB
    }
    
    # 09:05: crashes to 3850 (SL Hit!)
    # 09:10: rallies to 4300 (above TP1)
    times = pd.date_range("2026-11-13 09:05", "2026-11-13 09:15", freq="5min", tz="Asia/Jakarta")
    df = pd.DataFrame({
        "date": times,
        "open": [4000.0, 3900.0, 4200.0],
        "high": [4020.0, 4300.0, 4350.0],
        "low":  [3850.0, 3880.0, 4150.0],
        "close": [3900.0, 4250.0, 4300.0],
        "volume": [1000, 2000, 1500],
    })

    res = evaluate_signal_progression(signal, df)
    assert res["status"] == "SL_HIT"
    assert res["sl_hit"] is True
    assert res["tp_hit"] is False
    assert res["outcome_price"] == 3900.0
    assert res["pnl_pct"] == pytest.approx(-2.5)


def test_tp2_progression():
    """If price hits TP1 and subsequently hits TP2, status becomes TP2_HIT."""
    signal = {
        "id": 104,
        "ticker": "TLKM",
        "signal": "BUY",
        "entry_price": 3000.0,
        "tp1": 3150.0,  # +5%
        "tp2": 3300.0,  # +10%
        "stop_loss_atr": 2900.0,
        "created_at": "2026-11-13 02:00:00",
    }
    
    times = pd.date_range("2026-11-13 09:05", "2026-11-13 09:15", freq="5min", tz="Asia/Jakarta")
    df = pd.DataFrame({
        "date": times,
        "open": [3000.0, 3160.0, 3310.0],
        "high": [3180.0, 3320.0, 3350.0],  # Bar 1 hits TP1 (3180), Bar 2 hits TP2 (3320)
        "low":  [2980.0, 3150.0, 3290.0],
        "close": [3160.0, 3300.0, 3320.0],
        "volume": [1000, 2000, 1500],
    })

    res = evaluate_signal_progression(signal, df)
    assert res["status"] == "TP2_HIT"
    assert res["tp_hit"] is True
    assert res["tp2_hit"] is True
    assert res["outcome_price"] == 3300.0
    assert res["pnl_pct"] == pytest.approx(10.0)


def test_watchlist_must_touch_entry_first():
    """For WATCHLIST (Buy on Weakness), signal stays WAITING ENTRY until price dips <= entry_price."""
    signal = {
        "id": 105,
        "ticker": "BRIS",
        "signal": "WATCHLIST",
        "entry_price": 2800.0,  # pullback entry
        "tp1": 3000.0,
        "stop_loss_atr": 2700.0,
        "created_at": "2026-11-13 02:00:00",
    }
    
    # Prices stay between 2850 and 3100 (never dips to 2800)
    times = pd.date_range("2026-11-13 09:05", "2026-11-13 09:15", freq="5min", tz="Asia/Jakarta")
    df = pd.DataFrame({
        "date": times,
        "open": [2900.0, 2950.0, 3050.0],
        "high": [3050.0, 3100.0, 3100.0],  # Above TP1! But entry was never filled!
        "low":  [2850.0, 2900.0, 2980.0],  # Min low is 2850 > 2800
        "close": [2950.0, 3050.0, 3080.0],
        "volume": [1000, 2000, 1500],
    })

    res = evaluate_signal_progression(signal, df)
    assert res["entry_hit"] is False
    assert res["status"] == "PENDING"
    assert res["tp_hit"] is False
    assert res["sl_hit"] is False


def test_watchlist_enters_and_hits_tp():
    """When WATCHLIST price dips to entry_price, it activates and can hit TP afterwards."""
    signal = {
        "id": 106,
        "ticker": "BRIS",
        "signal": "WATCHLIST",
        "entry_price": 2800.0,
        "tp1": 2950.0,
        "stop_loss_atr": 2700.0,
        "created_at": "2026-11-13 02:00:00",
    }
    
    times = pd.date_range("2026-11-13 09:05", "2026-11-13 09:20", freq="5min", tz="Asia/Jakarta")
    df = pd.DataFrame({
        "date": times,
        "open": [2850.0, 2820.0, 2800.0, 2900.0],
        "high": [2870.0, 2830.0, 2850.0, 2980.0],  # Candle 4 hits 2980 (TP1 >= 2950)
        "low":  [2820.0, 2780.0, 2790.0, 2880.0],  # Candle 2 dips to 2780 (<= entry 2800)
        "close": [2830.0, 2800.0, 2850.0, 2960.0],
        "volume": [1000, 2000, 1500, 2500],
    })

    res = evaluate_signal_progression(signal, df)
    assert res["entry_hit"] is True
    assert res["status"] == "TP1_HIT"
    assert res["tp_hit"] is True
    assert res["outcome_price"] == 2950.0


def test_daily_candles_date_filtering():
    """Daily bars compared with signal created at morning scan (23:00 UTC = 06:00 WIB next day)."""
    # Signal created at 06:00 WIB on 2026-11-03 (stored in SQLite as 2026-11-02 23:00:00 UTC)
    signal = {
        "id": 107,
        "ticker": "BBCA",
        "signal": "BUY",
        "entry_price": 5000.0,
        "tp1": 5200.0,
        "stop_loss_atr": 4800.0,
        "created_at": "2026-11-02 23:00:00",
    }
    
    # Daily bars: 2026-11-01, 2026-11-02, 2026-11-03, 2026-11-04
    dates = [date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 4)]
    df = pd.DataFrame({
        "date": dates,
        "open": [4900, 4950, 5000, 5100],
        "high": [5300, 5350, 5050, 5250],  # Nov 1 & 2 were high, but Nov 3 is flat, Nov 4 hits TP1
        "low":  [4700, 4750, 4980, 5050],
        "close": [4950, 5000, 5020, 5220],
        "volume": [10000] * 4,
    })

    filtered = filter_candles_after_signal(signal, df)
    assert len(filtered) == 2
    assert list(filtered["date"]) == [date(2026, 11, 3), date(2026, 11, 4)]

    res = evaluate_signal_progression(signal, df)
    assert res["status"] == "TP1_HIT"
    assert res["tp_hit"] is True
    assert res["outcome_price"] == 5200.0
