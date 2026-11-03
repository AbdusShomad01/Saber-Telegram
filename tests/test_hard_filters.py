"""
Unit Tests — Hard Filter Improvements (Masalah 1, 2, 3, 4)
Jalankan: python -m pytest tests/test_hard_filters.py -v
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch

from services.scoring_engine import ScoringEngine, HardFilterResult, FilterFunnelStats


# ─────────────────────────────────────────────
#  Helper factories
# ─────────────────────────────────────────────

def make_technical(adx=25.0, atr_percent=2.0, volume_avg_20=10_000_000):
    return {
        "adx": adx,
        "atr_percent": atr_percent,
        "volume_avg_20": volume_avg_20,
        "_data_length": 60,
    }


def make_ohlcv_df(rows=60, avg_value=50_000_000_000):
    """Buat DataFrame OHLCV minimal dengan kolom 'value'."""
    dates = pd.date_range("2025-01-01", periods=rows, freq="B")
    value_per_row = avg_value  # setiap row nilainya sama
    return pd.DataFrame({
        "date":   dates,
        "open":   [1000.0] * rows,
        "high":   [1050.0] * rows,
        "low":    [950.0]  * rows,
        "close":  [1000.0] * rows,
        "volume": [10_000_000] * rows,
        "value":  [value_per_row] * rows,
    })


@pytest.fixture
def engine():
    return ScoringEngine()


# ─────────────────────────────────────────────
#  MASALAH 1: ADX Warm-Up Awareness
# ─────────────────────────────────────────────

class TestADXWarmUp:
    """Saat data < 28 bar, ADX filter harus di-skip (returned passed=True)."""

    def test_adx_filter_skipped_when_data_below_warmup(self, engine):
        """ADX 5 (sangat rendah) TIDAK boleh gugurkan saham jika data hanya 20 bar."""
        result = engine._check_adx_filter(make_technical(adx=5.0), data_len=20)
        assert result.passed is True
        assert result.category == "adx_warmup_skip"

    def test_adx_filter_skipped_at_exactly_27_bar(self, engine):
        """Batas atas warm-up: 27 bar masih harus di-skip."""
        result = engine._check_adx_filter(make_technical(adx=0.0), data_len=27)
        assert result.passed is True
        assert result.category == "adx_warmup_skip"

    def test_adx_filter_active_at_28_bar(self, engine):
        """28 bar ke atas: ADX rendah tetap lolos Hard Filter (dinilai di scoring engine)."""
        result = engine._check_adx_filter(make_technical(adx=5.0), data_len=28)
        assert result.passed is True
        assert result.category == "adx_scoring_only"

    def test_adx_filter_passes_with_sufficient_data_and_high_adx(self, engine):
        """ADX 25 dengan data 60 bar harus lolos."""
        result = engine._check_adx_filter(make_technical(adx=25.0), data_len=60)
        assert result.passed is True


# ─────────────────────────────────────────────
#  MASALAH 2: Threshold ADX dari 20 ke 15
# ─────────────────────────────────────────────

class TestADXThreshold:
    """Zona ADX 15-20 ('early_trend') harus lolos hard filter."""

    def test_adx_14_passes_filter_scores_zero(self, engine):
        """ADX 14 (di bawah 15) tetap lolos Hard Filter, dinilai 0 poin di scoring."""
        result = engine._check_adx_filter(make_technical(adx=14.9), data_len=60)
        assert result.passed is True
        assert result.category == "adx_scoring_only"
        assert engine.score_adx(14.9, 60)["score"] == 0

    def test_adx_15_lolos(self, engine):
        """ADX tepat 15 harus lolos (batas bawah baru)."""
        result = engine._check_adx_filter(make_technical(adx=15.0), data_len=60)
        assert result.passed is True

    def test_adx_18_lolos(self, engine):
        """ADX 18 (early_trend) harus lolos hard filter, dinilai di scoring engine."""
        result = engine._check_adx_filter(make_technical(adx=18.0), data_len=60)
        assert result.passed is True

    def test_adx_19_lolos(self, engine):
        """ADX 19.9 yang dulu gugur di threshold 20 sekarang harus lolos."""
        result = engine._check_adx_filter(make_technical(adx=19.9), data_len=60)
        assert result.passed is True

    def test_adx_class_constant_is_15(self, engine):
        """Pastikan konstanta threshold tidak berubah tanpa sengaja."""
        assert engine.ADX_HARD_FILTER_THRESHOLD == 15


# ─────────────────────────────────────────────
#  MASALAH 3: Filter Funnel Stats Tracking
# ─────────────────────────────────────────────

class TestFilterFunnelStats:
    """FilterFunnelStats harus terakumulasi dengan benar dan reset bersih."""

    def test_reset_clears_stats(self, engine):
        """reset_scan_stats harus mengembalikan semua counter ke 0."""
        engine._scan_stats.total_stocks = 99
        engine._scan_stats.gugur_adx = 5
        engine.reset_scan_stats()
        s = engine.get_scan_stats()
        assert s.total_stocks == 0
        assert s.gugur_adx == 0

    def test_get_scan_stats_returns_same_object(self, engine):
        """get_scan_stats harus mengembalikan instance yang sama."""
        engine.reset_scan_stats()
        s1 = engine.get_scan_stats()
        s1.total_stocks = 42
        s2 = engine.get_scan_stats()
        assert s2.total_stocks == 42

    def test_to_summary_text_no_crash(self, engine):
        """to_summary_text tidak boleh raise exception meski semua 0."""
        engine.reset_scan_stats()
        text = engine.get_scan_stats().to_summary_text()
        assert "FILTER FUNNEL" in text
        assert "Total saham" in text

    def test_summary_shows_correct_counts(self):
        """to_summary_text harus menampilkan angka yang benar."""
        s = FilterFunnelStats(
            total_stocks=100,
            passed_hard_filter=70,
            failed_hard_filter=30,
            passed_to_signal=20,
            gugur_adx=10,
            gugur_atr=5,
            gugur_volume=8,
            gugur_value=4,
            gugur_volume_dan_value=3,
            strong_buy_count=5,
            buy_count=10,
            watchlist_count=5,
        )
        text = s.to_summary_text()
        assert "100" in text   # total_stocks
        assert "70" in text    # passed_hard_filter
        assert "10" in text    # gugur_adx


# ─────────────────────────────────────────────
#  MASALAH 4: Volume AND Value (AND logic)
# ─────────────────────────────────────────────

class TestLiquidityFilter:
    """Volume dan Value harus dicheck KEDUANYA secara independent (AND)."""

    def test_lolos_jika_keduanya_cukup(self, engine):
        tech = make_technical(volume_avg_20=10_000_000)
        ohlcv = make_ohlcv_df(avg_value=50_000_000_000)
        result = engine._check_liquidity_filter(tech, ohlcv)
        assert result.passed is True

    def test_gugur_jika_volume_kurang(self, engine):
        """Volume < 500 ribu lembar (5.000 lot) → gugur dengan category 'volume'."""
        tech = make_technical(volume_avg_20=200_000)  # < 500 ribu
        ohlcv = make_ohlcv_df(avg_value=50_000_000_000)  # value OK
        result = engine._check_liquidity_filter(tech, ohlcv)
        assert result.passed is False
        assert result.category == "volume"

    def test_gugur_jika_value_kurang(self, engine):
        """Value < Rp2 miliar → gugur dengan category 'value'."""
        tech = make_technical(volume_avg_20=10_000_000)  # volume OK
        ohlcv = make_ohlcv_df(avg_value=1_000_000_000)   # < 2 miliar
        result = engine._check_liquidity_filter(tech, ohlcv)
        assert result.passed is False
        assert result.category == "value"

    def test_gugur_jika_keduanya_kurang(self, engine):
        """Keduanya gagal → category 'volume_and_value'."""
        tech = make_technical(volume_avg_20=200_000)   # < 500 ribu
        ohlcv = make_ohlcv_df(avg_value=1_000_000_000)  # < 2 miliar
        result = engine._check_liquidity_filter(tech, ohlcv)
        assert result.passed is False
        assert result.category == "volume_and_value"

    def test_lolos_tanpa_kolom_value(self, engine):
        """Jika kolom 'value' tidak ada di DataFrame, value filter dilewati (default lolos)."""
        tech = make_technical(volume_avg_20=10_000_000)
        ohlcv = make_ohlcv_df().drop(columns=["value"])
        result = engine._check_liquidity_filter(tech, ohlcv)
        assert result.passed is True

    def test_lolos_tanpa_ohlcv(self, engine):
        """Tanpa ohlcv_df sama sekali, value filter default lolos."""
        tech = make_technical(volume_avg_20=10_000_000)
        result = engine._check_liquidity_filter(tech, None)
        assert result.passed is True

    def test_volume_threshold_constant(self, engine):
        """Pastikan threshold volume tidak berubah tanpa sengaja."""
        assert engine.MIN_AVG_VOLUME_LOT == 500_000

    def test_value_threshold_constant(self, engine):
        """Pastikan threshold value tidak berubah tanpa sengaja."""
        assert engine.MIN_AVG_VALUE_IDR == 2_000_000_000


# ─────────────────────────────────────────────
#  ATR Filter
# ─────────────────────────────────────────────

class TestATRFilter:
    def test_atr_normal_lolos(self, engine):
        assert engine._check_atr_filter(make_technical(atr_percent=3.0)).passed is True

    def test_atr_7_masih_lolos(self, engine):
        assert engine._check_atr_filter(make_technical(atr_percent=7.0)).passed is True

    def test_atr_above_7_gugur(self, engine):
        r = engine._check_atr_filter(make_technical(atr_percent=7.1))
        assert r.passed is False
        assert r.category == "atr"


# ─────────────────────────────────────────────
#  MASALAH 5: Filter Harga Minimum (> 10 dimasukkan, <= 10 gugur)
# ─────────────────────────────────────────────

class TestMinPriceFilter:
    """Saham yang harganya > 10 tetap dimasukkan, <= 10 dikeluarkan."""

    def test_price_above_10_passes(self, engine):
        """Harga Rp 15 (> 10) harus lolos."""
        ohlcv = pd.DataFrame({"close": [14.0, 15.0]})
        r = engine._check_min_price_filter(ohlcv)
        assert r.passed is True

    def test_price_50_passes(self, engine):
        """Harga Rp 50 (saham gocap) harus lolos."""
        ohlcv = pd.DataFrame({"close": [50.0, 50.0]})
        r = engine._check_min_price_filter(ohlcv)
        assert r.passed is True

    def test_price_exactly_10_fails(self, engine):
        """Harga tepat Rp 10 harus gugur (harus > 10)."""
        ohlcv = pd.DataFrame({"close": [10.0, 10.0]})
        r = engine._check_min_price_filter(ohlcv)
        assert r.passed is False
        assert r.category == "min_price"

    def test_price_below_10_fails(self, engine):
        """Harga Rp 5 (saham tidur/delisting) harus gugur."""
        ohlcv = pd.DataFrame({"close": [6.0, 5.0]})
        r = engine._check_min_price_filter(ohlcv)
        assert r.passed is False
        assert r.category == "min_price"


# ─────────────────────────────────────────────
#  MASALAH 6: Filter Saham Naik > 15% Kemarin
# ─────────────────────────────────────────────

class TestPrevDayGainFilter:
    """Saham yang naik > 15% pada hari perdagangan sebelumnya harus digugurkan."""

    def test_prev_gain_below_15_passes(self, engine):
        """Kenaikan 10% kemarin harus lolos."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1100.0],
        })
        r = engine._check_prev_day_gain_filter(ohlcv, timeframe="1d")
        assert r.passed is True

    def test_prev_gain_exactly_15_passes(self, engine):
        """Kenaikan tepat 15% kemarin harus lolos (batas atas)."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1150.0],
        })
        r = engine._check_prev_day_gain_filter(ohlcv, timeframe="1d")
        assert r.passed is True

    def test_prev_gain_above_15_fails(self, engine):
        """Kenaikan 16% (ARA/climax) kemarin harus gugur."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1160.0],
        })
        r = engine._check_prev_day_gain_filter(ohlcv, timeframe="1d")
        assert r.passed is False
        assert r.category == "prev_day_surge"
        assert "15%" in r.reason

    def test_prev_gain_intraday_grouped_by_date(self, engine):
        """Intraday 60m: harus mengecek return hari kemarin vs lusa kemarin."""
        dates = (
            [pd.Timestamp("2026-10-20 10:00:00")] * 4 +
            [pd.Timestamp("2026-10-21 10:00:00")] * 4 +
            [pd.Timestamp("2026-10-22 10:00:00")] * 2
        )
        closes = [1000.0]*4 + [1200.0]*4 + [1210.0]*2
        ohlcv = pd.DataFrame({"date": dates, "close": closes})
        r = engine._check_prev_day_gain_filter(ohlcv, timeframe="60m")
        assert r.passed is False
        assert r.category == "prev_day_surge"


# ─────────────────────────────────────────────
#  _run_hard_filters (integrasi)
# ─────────────────────────────────────────────

class TestRunHardFilters:
    def test_all_pass(self, engine):
        tech = make_technical(adx=25.0, atr_percent=3.0, volume_avg_20=10_000_000)
        tech["_data_length"] = 60
        ohlcv = make_ohlcv_df(avg_value=50_000_000_000)
        r = engine._run_hard_filters(tech, ohlcv, data_len=60)
        assert r.passed is True

    def test_adx_low_does_not_fail_hard_filters(self, engine):
        """ADX rendah (5.0) tidak lagi menggugurkan saham jika liquidity & ATR terpenuhi."""
        tech = make_technical(adx=5.0, atr_percent=3.0, volume_avg_20=10_000_000)
        ohlcv = make_ohlcv_df(avg_value=50_000_000_000)
        r = engine._run_hard_filters(tech, ohlcv, data_len=60)
        assert r.passed is True

    def test_warmup_skip_then_check_volume(self, engine):
        """Saat warm-up, ADX di-skip. Jika volume kurang, volume yang gugur."""
        tech = make_technical(adx=0.0, atr_percent=3.0, volume_avg_20=100_000)
        ohlcv = make_ohlcv_df(avg_value=50_000_000_000)
        r = engine._run_hard_filters(tech, ohlcv, data_len=20)  # < 28 → skip ADX
        assert r.passed is False
        assert r.category == "volume"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
