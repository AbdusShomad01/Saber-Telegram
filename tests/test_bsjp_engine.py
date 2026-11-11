"""
Unit tests for BSJP (Beli Sore Jual Profit) Engine and DB.
Tests all 5 Stockbit-style BSJP criteria:
  1. Current Price Change >= +2%
  2. Current Price Change <= +4%
  3. Current Price >= 1 × Price MA 20
  4. Volume (Shares) Today >= 1.2 × Volume (Shares) MA 20
  5. Value (Today) >= Rp 10.000.000.000
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from services.bsjp_db import (
    get_pending_bsjp_signals,
    migrate_bsjp_table,
    save_bsjp_signals,
    update_bsjp_outcome,
)
from services.bsjp_engine import evaluate_bsjp_stock, run_bsjp_screener


def _make_daily_df(
    n_bars=25,
    prev_close=1000.0,
    today_close=1030.0,
    prev_volume=8_000_000.0,
    today_volume=12_000_000.0,
    base_history_close=1000.0,
):
    """Buat DataFrame harian (1d) sintesis untuk testing BSJP."""
    dates = [datetime(2026, 10, 1) + timedelta(days=i) for i in range(n_bars)]
    closes = [base_history_close] * (n_bars - 2) + [prev_close, today_close]
    volumes = [prev_volume] * (n_bars - 1) + [today_volume]
    return pd.DataFrame(
        {"close": closes, "volume": volumes},
        index=pd.to_datetime(dates),
    )


def test_bsjp_all_5_criteria_pass():
    """Lolos semua 5 syarat: +3%, >= MA20, vol >= 1.2x MA20, value >= Rp10M."""
    df = _make_daily_df(
        prev_close=1000.0,
        today_close=1030.0,     # +3.0% (antara 2% - 4%)
        prev_volume=8_000_000.0,
        today_volume=12_000_000.0,  # val = 1030 * 12M = Rp 12.36M; MA20 vol = 8.2M -> 1.46x
    )
    res = evaluate_bsjp_stock("BBCA", df=df)
    assert res["passed"] is True
    assert res["hard_filter_pass"] is True
    assert res["reason"] == "OK"
    assert res["score"] >= 70.0
    assert res["close_price"] == 1030.0
    assert res["price_change_pct"] == 3.0
    assert all(res["checks"].values())


def test_bsjp_boundary_exact_2_and_4_percent():
    """Batas tepat +2.0% dan +4.0% harus lolos."""
    df_min = _make_daily_df(today_close=1020.0, today_volume=12_000_000.0)
    res_min = evaluate_bsjp_stock("BBCA", df=df_min)
    assert res_min["passed"] is True
    assert res_min["checks"]["change_min_ok"] is True

    df_max = _make_daily_df(today_close=1040.0, today_volume=12_000_000.0)
    res_max = evaluate_bsjp_stock("BBCA", df=df_max)
    assert res_max["passed"] is True
    assert res_max["checks"]["change_max_ok"] is True


def test_bsjp_fails_change_below_2_or_above_4():
    """Perubahan < 2% atau > 4% harus gugur."""
    df_low = _make_daily_df(today_close=1019.0, today_volume=12_000_000.0)  # +1.9%
    res_low = evaluate_bsjp_stock("BBCA", df=df_low)
    assert res_low["passed"] is False
    assert res_low["checks"]["change_min_ok"] is False
    assert res_low["score"] == 0.0

    df_high = _make_daily_df(today_close=1041.0, today_volume=12_000_000.0)  # +4.1%
    res_high = evaluate_bsjp_stock("BBCA", df=df_high)
    assert res_high["passed"] is False
    assert res_high["checks"]["change_max_ok"] is False
    assert res_high["score"] == 0.0


def test_bsjp_fails_below_price_ma20():
    """Harga saat ini di bawah Price MA 20 harus gugur."""
    df = _make_daily_df(
        base_history_close=1200.0,  # MA20 jadi tinggi (~1181)
        prev_close=1000.0,
        today_close=1030.0,         # +3%, tapi masih di bawah MA20
        today_volume=12_000_000.0,
    )
    res = evaluate_bsjp_stock("BBCA", df=df)
    assert res["passed"] is False
    assert res["checks"]["above_ma20_ok"] is False
    assert res["score"] == 0.0


def test_bsjp_fails_volume_below_1_2x_ma20():
    """Volume hari ini < 1.2 × Volume MA 20 harus gugur meski value >= Rp10M."""
    df = _make_daily_df(
        today_close=1030.0,
        prev_volume=10_000_000.0,
        today_volume=11_000_000.0,  # MA20=10.05M -> 1.2x=12.06M > 11M (val=11.33M OK)
    )
    res = evaluate_bsjp_stock("BBCA", df=df)
    assert res["checks"]["value_ok"] is True
    assert res["checks"]["volume_ma20_ok"] is False
    assert res["passed"] is False
    assert res["score"] == 0.0


def test_bsjp_fails_value_below_10_billion():
    """Value hari ini < Rp 10 miliar harus gugur meski volume >= 1.2 × MA 20."""
    df = _make_daily_df(
        today_close=1030.0,
        prev_volume=1_000_000.0,
        today_volume=5_000_000.0,   # Vol ratio ~4.17x MA20 OK, tapi val = Rp 5.15M < 10M
    )
    res = evaluate_bsjp_stock("BBCA", df=df)
    assert res["checks"]["volume_ma20_ok"] is True
    assert res["checks"]["value_ok"] is False
    assert res["passed"] is False
    assert res["score"] == 0.0


def test_bsjp_fails_insufficient_daily_bars():
    """Data harian < 20 bar (tidak cukup untuk MA20) harus return INSUFFICIENT_DAILY_DATA."""
    df = _make_daily_df(n_bars=15)
    res = evaluate_bsjp_stock("BBCA", df=df)
    assert res["passed"] is False
    assert res["reason"] == "INSUFFICIENT_DAILY_DATA"


def test_run_bsjp_screener_filters_and_sorts():
    """run_bsjp_screener hanya mengembalikan saham lolos dan terurut dari skor/value tertinggi."""
    good_big = _make_daily_df(today_close=1030.0, prev_volume=10_000_000.0, today_volume=25_000_000.0)
    good_small = _make_daily_df(today_close=1025.0, prev_volume=8_000_000.0, today_volume=11_000_000.0)
    bad = _make_daily_df(today_close=1010.0, prev_volume=8_000_000.0, today_volume=12_000_000.0)  # +1%

    mock_map = {"BMRI": good_small, "BBCA": good_big, "TLKM": bad}
    with patch("services.bsjp_engine._fetch_daily", side_effect=lambda t: mock_map.get(t)):
        signals = run_bsjp_screener(["TLKM", "BMRI", "BBCA"])

    assert [s["ticker"] for s in signals] == ["BBCA", "BMRI"]


def test_bsjp_db_operations(tmp_path, monkeypatch):
    """Test tabel SQLite bsjp_signals: migrate, insert, duplicate prevention, update."""
    db_file = tmp_path / "test_bsjp.db"
    monkeypatch.setattr("services.bsjp_db._get_db_path", lambda: str(db_file))

    migrate_bsjp_table()

    signals = [
        {"ticker": "BBCA", "score": 95, "close_price": 3200},
        {"ticker": "BMRI", "score": 85, "close_price": 6500},
    ]
    save_bsjp_signals(signals, signal_date="2026-11-06")

    pending = get_pending_bsjp_signals("2026-11-06")
    assert len(pending) == 2
    assert pending[0]["ticker"] == "BBCA"

    save_bsjp_signals(signals, signal_date="2026-11-06")
    pending2 = get_pending_bsjp_signals("2026-11-06")
    assert len(pending2) == 2

    update_bsjp_outcome(
        ticker="BBCA",
        signal_date="2026-11-06",
        open_price=3220,
        high_price=3264,
        pct_change=0.02,
        outcome="profit",
    )

    pending_after = get_pending_bsjp_signals("2026-11-06")
    assert len(pending_after) == 1
    assert pending_after[0]["ticker"] == "BMRI"


def test_resolve_bsjp_universe_extracts_dicts_and_filters_fca():
    """resolve_bsjp_universe harus mengekstrak key 'ticker' dari dict full universe tanpa fallback ke 107."""
    from jobs.scheduler import resolve_bsjp_universe

    fake_full = [
        {"ticker": "bbca", "board": "Utama"},
        {"ticker": "BMRI", "board": "Utama"},
        {"ticker": "BBCA", "board": "Utama"},  # duplikat
        {"ticker": "FCAA", "board": "Pemantauan"},
    ]
    with patch("services.idx_full_universe_service.get_full_idx_universe", return_value=fake_full), \
         patch("services.idx_full_universe_service.is_fca_stock", side_effect=lambda t, **kw: t == "FCAA"):
        res = resolve_bsjp_universe()

    assert res == ["BBCA", "BMRI"]


def test_resolve_bsjp_universe_fallback_on_error():
    """Jika get_full_idx_universe gagal, fallback aman ke get_stock_universe."""
    from jobs.scheduler import resolve_bsjp_universe

    fake_default = [{"ticker": "BBCA"}, {"ticker": "TLKM"}]
    with patch("services.idx_full_universe_service.get_full_idx_universe", side_effect=RuntimeError("boom")), \
         patch("services.stock_universe_service.get_stock_universe", return_value=fake_default):
        res = resolve_bsjp_universe()

    assert res == ["BBCA", "TLKM"]


def test_bsjp_latest_pending_handles_weekend_gap(tmp_path, monkeypatch):
    """Sinyal Jumat harus ditemukan saat rekap Senin pagi (lewati Sabtu & Minggu)."""
    from services.bsjp_db import get_latest_pending_bsjp_signals

    db_file = tmp_path / "test_bsjp_weekend.db"
    monkeypatch.setattr("services.bsjp_db._get_db_path", lambda: str(db_file))
    migrate_bsjp_table()

    # Simpan sinyal hari Jumat 2026-11-06 dan hari Senin 2026-11-09 (jangan terbaca saat cek Senin)
    save_bsjp_signals([{"ticker": "BBCA", "score": 88, "close_price": 10000}], signal_date="2026-11-06")
    save_bsjp_signals([{"ticker": "BMRI", "score": 82, "close_price": 6000}], signal_date="2026-11-09")

    target_date, pending = get_latest_pending_bsjp_signals("2026-11-09")
    assert target_date == "2026-11-06"
    assert [p["ticker"] for p in pending] == ["BBCA"]

    # Setelah di-update, Senin tidak lagi menganggap 2026-11-06 pending
    update_bsjp_outcome("BBCA", "2026-11-06", 10100, 10200, 0.02, "profit")
    target2, pending2 = get_latest_pending_bsjp_signals("2026-11-09")
    assert target2 is None
    assert pending2 == []


def test_run_bsjp_rekap_sync_friday_to_monday_end_to_end(tmp_path, monkeypatch):
    """Pastikan run_bsjp_rekap_sync menangani jeda Jumat->Senin, cutoff < 09:30 WIB, profit/lose & DB update."""
    import pytz
    from jobs.scheduler import run_bsjp_rekap_sync

    db_file = tmp_path / "test_rekap_e2e.db"
    monkeypatch.setattr("services.bsjp_db._get_db_path", lambda: str(db_file))
    migrate_bsjp_table()
    save_bsjp_signals(
        [
            {"ticker": "BBCA", "score": 90, "close_price": 1000.0},
            {"ticker": "TLKM", "score": 82, "close_price": 3000.0},
        ],
        signal_date="2026-11-06",  # Jumat
    )

    wib = pytz.timezone("Asia/Jakarta")
    fake_now = wib.localize(datetime(2026, 11, 9, 9, 30, 0))  # Senin 09:30 WIB

    bars_by_ticker = {
        "BBCA.JK": pd.DataFrame(
            {
                "Open": [1005.0, 1015.0, 1050.0],
                "High": [1015.0, 1030.0, 1090.0],  # bar ke-3 (>= 09:30) tidak boleh dihitung!
                "Low": [1000.0, 1010.0, 1040.0],
                "Close": [1012.0, 1025.0, 1080.0],
                "Volume": [100_000, 200_000, 300_000],
            },
            index=pd.DatetimeIndex(
                [
                    wib.localize(datetime(2026, 11, 9, 9, 0)),
                    wib.localize(datetime(2026, 11, 9, 9, 25)),
                    wib.localize(datetime(2026, 11, 9, 9, 30)),
                ]
            ),
        ),
        "TLKM.JK": pd.DataFrame(
            {
                "Open": [2980.0, 2970.0],
                "High": [2990.0, 2980.0],  # < 3000 -> Lose
                "Low": [2940.0, 2950.0],   # -2.0%
                "Close": [2960.0, 2965.0],
                "Volume": [100_000, 150_000],
            },
            index=pd.DatetimeIndex(
                [
                    wib.localize(datetime(2026, 11, 9, 9, 0)),
                    wib.localize(datetime(2026, 11, 9, 9, 15)),
                ]
            ),
        ),
    }

    res = run_bsjp_rekap_sync(now_wib=fake_now, fetch_bars_fn=lambda t: bars_by_ticker.get(t))

    assert res is not None
    assert res["target_date"] == "2026-11-06"
    assert res["profit_count"] == 1
    assert res["lose_count"] == 1
    assert res["wr"] == 50
    assert "Rekap BSJP kemaren" in res["msg"]
    assert "BBCA | 1030 | +3.0% | Profit" in res["msg"]
    assert "TLKM | 2940 | -2.0% | Lose" in res["msg"]
    assert get_pending_bsjp_signals("2026-11-06") == []
