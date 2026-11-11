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

def make_technical(adx=25.0, atr_percent=2.0, volume_avg_20=10_000_000, volume_avg_5=None):
    return {
        "adx": adx,
        "atr_percent": atr_percent,
        "volume_avg_20": volume_avg_20,
        "volume_avg_5": volume_avg_20 if volume_avg_5 is None else volume_avg_5,
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
        """28 bar ke atas di daily: ADX < 12 gugur dengan category 'adx'."""
        result = engine._check_adx_filter(make_technical(adx=5.0), data_len=28, timeframe="1d")
        assert result.passed is False
        assert result.category == "adx"

    def test_adx_intraday_stays_scoring_only(self, engine):
        """Mode intraday (15m / pure_technical): ADX rendah tidak menggugurkan hard filter."""
        result = engine._check_adx_filter(make_technical(adx=5.0), data_len=28, timeframe="15m", pure_technical=True)
        assert result.passed is True
        assert result.category == "adx_scoring_only"

    def test_adx_filter_passes_with_sufficient_data_and_high_adx(self, engine):
        """ADX 25 dengan data 60 bar harus lolos."""
        result = engine._check_adx_filter(make_technical(adx=25.0), data_len=60)
        assert result.passed is True


# ─────────────────────────────────────────────
#  MASALAH 2: Threshold ADX Minimum Daily = 12
# ─────────────────────────────────────────────

class TestADXThreshold:
    """Batas minimum ADX hard filter daily (pagi hari) adalah 12."""

    def test_adx_below_12_fails_daily(self, engine):
        """ADX 11.9 (< 12) di daily harus gugur dengan category 'adx'."""
        result = engine._check_adx_filter(make_technical(adx=11.9), data_len=60, timeframe="1d")
        assert result.passed is False
        assert result.category == "adx"

    def test_adx_12_passes_daily(self, engine):
        """ADX tepat 12 harus lolos hard filter daily."""
        result = engine._check_adx_filter(make_technical(adx=12.0), data_len=60, timeframe="1d")
        assert result.passed is True

    def test_adx_14_passes_filter_scores_zero(self, engine):
        """ADX 14.9 (>= 12) lolos Hard Filter daily, namun dinilai 0 poin di scoring."""
        result = engine._check_adx_filter(make_technical(adx=14.9), data_len=60, timeframe="1d")
        assert result.passed is True
        assert engine.score_adx(14.9, 60)["score"] == 0

    def test_adx_15_lolos(self, engine):
        """ADX tepat 15 harus lolos."""
        result = engine._check_adx_filter(make_technical(adx=15.0), data_len=60)
        assert result.passed is True

    def test_adx_18_lolos(self, engine):
        """ADX 18 harus lolos hard filter, dinilai di scoring engine."""
        result = engine._check_adx_filter(make_technical(adx=18.0), data_len=60)
        assert result.passed is True

    def test_adx_19_lolos(self, engine):
        """ADX 19.9 harus lolos."""
        result = engine._check_adx_filter(make_technical(adx=19.9), data_len=60)
        assert result.passed is True

    def test_adx_class_constant_is_12(self, engine):
        """Pastikan konstanta threshold ADX daily adalah 12."""
        assert engine.ADX_HARD_FILTER_THRESHOLD == 12


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
    """Volume dan Value harus dicheck KEDUANYA secara independent (AND), rata-rata 5 hari untuk daily."""

    def test_lolos_jika_keduanya_cukup(self, engine):
        tech = make_technical(volume_avg_5=250_000, volume_avg_20=100_000)
        ohlcv = make_ohlcv_df(avg_value=1_500_000_000)
        result = engine._check_liquidity_filter(tech, ohlcv, timeframe="1d")
        assert result.passed is True

    def test_daily_uses_5d_avg_not_20d_avg(self, engine):
        """Daily wajib pakai rata-rata 5 hari (volume_avg_5 & 5 hari terakhir value), bukan 20 hari."""
        # 15 hari awal sepi (Rp 200jt), 5 hari terakhir ramai (Rp 2M); volume_avg_20 rendah, volume_avg_5 >= 200k
        tech = make_technical(volume_avg_20=80_000, volume_avg_5=250_000)
        ohlcv = make_ohlcv_df(rows=20, avg_value=200_000_000)
        ohlcv.iloc[-5:, ohlcv.columns.get_loc("value")] = 2_000_000_000
        assert engine._check_liquidity_filter(tech, ohlcv, timeframe="1d").passed is True

        # Kebalikannya: 15 hari awal ramai, 5 hari terakhir sepi -> harus gugur
        tech_drop = make_technical(volume_avg_20=5_000_000, volume_avg_5=150_000)
        ohlcv_drop = make_ohlcv_df(rows=20, avg_value=50_000_000_000)
        ohlcv_drop.iloc[-5:, ohlcv_drop.columns.get_loc("value")] = 500_000_000
        r_drop = engine._check_liquidity_filter(tech_drop, ohlcv_drop, timeframe="1d")
        assert r_drop.passed is False
        assert r_drop.category == "volume_and_value"

    def test_gugur_jika_volume_kurang(self, engine):
        """Volume 5H < 200 ribu lembar → gugur dengan category 'volume'."""
        tech = make_technical(volume_avg_5=199_999)  # < 200 ribu
        ohlcv = make_ohlcv_df(avg_value=5_000_000_000)  # value OK
        result = engine._check_liquidity_filter(tech, ohlcv, timeframe="1d")
        assert result.passed is False
        assert result.category == "volume"

    def test_gugur_jika_value_kurang(self, engine):
        """Value 5H < Rp1 miliar → gugur dengan category 'value'."""
        tech = make_technical(volume_avg_5=1_000_000)  # volume OK
        ohlcv = make_ohlcv_df(avg_value=900_000_000)   # < 1 miliar
        result = engine._check_liquidity_filter(tech, ohlcv, timeframe="1d")
        assert result.passed is False
        assert result.category == "value"

    def test_gugur_jika_keduanya_kurang(self, engine):
        """Keduanya gagal → category 'volume_and_value'."""
        tech = make_technical(volume_avg_5=150_000)   # < 200 ribu
        ohlcv = make_ohlcv_df(avg_value=800_000_000)  # < 1 miliar
        result = engine._check_liquidity_filter(tech, ohlcv, timeframe="1d")
        assert result.passed is False
        assert result.category == "volume_and_value"

    def test_lolos_tanpa_kolom_value(self, engine):
        """Jika kolom 'value' tidak ada di DataFrame, value filter dilewati (default lolos)."""
        tech = make_technical(volume_avg_5=10_000_000)
        ohlcv = make_ohlcv_df().drop(columns=["value"])
        result = engine._check_liquidity_filter(tech, ohlcv)
        assert result.passed is True

    def test_lolos_tanpa_ohlcv(self, engine):
        """Tanpa ohlcv_df sama sekali, value filter default lolos."""
        tech = make_technical(volume_avg_5=10_000_000)
        result = engine._check_liquidity_filter(tech, None)
        assert result.passed is True

    def test_volume_threshold_constant(self, engine):
        """Pastikan threshold volume daily adalah 200.000 lembar."""
        assert engine.MIN_AVG_VOLUME_LOT == 200_000

    def test_value_threshold_constant(self, engine):
        """Pastikan threshold value daily adalah Rp 1 miliar."""
        assert engine.MIN_AVG_VALUE_IDR == 1_000_000_000


# ─────────────────────────────────────────────
#  ATR Filter
# ─────────────────────────────────────────────

class TestATRFilter:
    def test_atr_normal_lolos(self, engine):
        assert engine._check_atr_filter(make_technical(atr_percent=3.0)).passed is True

    def test_atr_10_masih_lolos_daily(self, engine):
        assert engine._check_atr_filter(make_technical(atr_percent=10.0), timeframe="1d").passed is True

    def test_atr_above_10_gugur_daily(self, engine):
        r = engine._check_atr_filter(make_technical(atr_percent=10.1), timeframe="1d")
        assert r.passed is False
        assert r.category == "atr"

    def test_atr_above_7_gugur_intraday(self, engine):
        r = engine._check_atr_filter(make_technical(atr_percent=7.1), timeframe="15m")
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
#  MASALAH 6: Filter Saham Naik > 20% Kemarin (Daily)
# ─────────────────────────────────────────────

class TestPrevDayGainFilter:
    """Daily: saham yang naik > 20% kemarin digugurkan. Intraday: > 15%."""

    def test_prev_gain_below_20_passes(self, engine):
        """Kenaikan 16% kemarin pada daily harus lolos."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1160.0],
        })
        r = engine._check_prev_day_gain_filter(ohlcv, timeframe="1d")
        assert r.passed is True

    def test_prev_gain_exactly_20_passes(self, engine):
        """Kenaikan tepat 20% kemarin pada daily harus lolos (batas atas)."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1200.0],
        })
        r = engine._check_prev_day_gain_filter(ohlcv, timeframe="1d")
        assert r.passed is True

    def test_prev_gain_above_20_fails(self, engine):
        """Kenaikan 21% kemarin pada daily harus gugur."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1210.0],
        })
        r = engine._check_prev_day_gain_filter(ohlcv, timeframe="1d")
        assert r.passed is False
        assert r.category == "prev_day_surge"
        assert "20%" in r.reason

    def test_prev_gain_intraday_grouped_by_date(self, engine):
        """Intraday 60m: harus mengecek return hari kemarin vs lusa kemarin (batas 15%)."""
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
        tech = make_technical(adx=12.0, atr_percent=10.0, volume_avg_5=200_000)
        tech["_data_length"] = 60
        ohlcv = make_ohlcv_df(avg_value=1_000_000_000)
        r = engine._run_hard_filters(tech, ohlcv, data_len=60, timeframe="1d")
        assert r.passed is True

    def test_adx_below_12_fails_daily(self, engine):
        """ADX < 12 menggugurkan saham di scan pagi daily jika data >= 28 bar."""
        tech = make_technical(adx=11.0, atr_percent=3.0, volume_avg_5=10_000_000)
        ohlcv = make_ohlcv_df(avg_value=50_000_000_000)
        r = engine._run_hard_filters(tech, ohlcv, data_len=60, timeframe="1d")
        assert r.passed is False
        assert r.category == "adx"

    def test_warmup_skip_then_check_volume(self, engine):
        """Saat warm-up, ADX di-skip. Jika volume kurang, volume yang gugur."""
        tech = make_technical(adx=0.0, atr_percent=3.0, volume_avg_5=100_000)
        ohlcv = make_ohlcv_df(avg_value=50_000_000_000)
        r = engine._run_hard_filters(tech, ohlcv, data_len=20, timeframe="1d")  # < 28 → skip ADX
        assert r.passed is False
        assert r.category == "volume"


# ─────────────────────────────────────────────
#  ARA Filter (Auto Rejection Atas)
# ─────────────────────────────────────────────

class TestARAFilter:
    """Saham yang sudah ARA atau hampir menyentuh batas ARA harus digugurkan."""

    def test_ara_exact_hit_fails(self, engine):
        """Saham harga 1000 (batas 25%, ARA=1250) jika close 1250 harus gugur."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1250.0],
            "high":  [1000.0, 1250.0],
        })
        r = engine._check_ara_filter(ohlcv, timeframe="1d")
        assert r.passed is False
        assert r.category == "ara_limit"
        assert "sudah" in r.reason.lower()

    def test_ara_high_intraday_hit_fails(self, engine):
        """Saham yang high-nya menyentuh ARA (meski close sedikit turun) harus gugur."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1230.0],
            "high":  [1000.0, 1250.0],
        })
        r = engine._check_ara_filter(ohlcv, timeframe="1d")
        assert r.passed is False
        assert r.category == "ara_limit"

    def test_near_ara_fails(self, engine):
        """Saham naik +22% (dari batas 25%, sisa ke ARA < 3.5%) harus gugur."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1220.0],
            "high":  [1000.0, 1220.0],
        })
        r = engine._check_ara_filter(ohlcv, timeframe="1d")
        assert r.passed is False
        assert r.category == "ara_limit"
        assert "hampir" in r.reason.lower()

    def test_moderate_gain_passes(self, engine):
        """Saham dengan gain wajar (+7%) harus lolos."""
        ohlcv = pd.DataFrame({
            "close": [1000.0, 1070.0],
            "high":  [1000.0, 1075.0],
        })
        r = engine._check_ara_filter(ohlcv, timeframe="1d")
        assert r.passed is True

    def test_intraday_15m_ara_grouped(self, engine):
        """Intraday 15m: harus memisahkan tanggal hari ini vs kemarin dan mendeteksi ARA."""
        dates = (
            [pd.Timestamp("2026-11-06 15:45:00")] * 4 +
            [pd.Timestamp("2026-11-07 10:00:00"), pd.Timestamp("2026-11-07 11:30:00")]
        )
        closes = [100.0, 100.0, 100.0, 100.0, 130.0, 134.0]  # Saham 100 -> ARA 35% (135)
        highs = [100.0, 100.0, 100.0, 100.0, 130.0, 134.0]
        ohlcv = pd.DataFrame({"date": dates, "close": closes, "high": highs})
        r = engine._check_ara_filter(ohlcv, timeframe="15m")
        assert r.passed is False
        assert r.category == "ara_limit"


# ─────────────────────────────────────────────
#  Intraday Tightened Liquidity & Min Price
# ─────────────────────────────────────────────

class TestIntradayTightenedFilters:
    """Verifikasi pengetatan likuiditas dan harga minimal untuk intraday (15m)."""

    def test_intraday_min_price_50_fails(self, engine):
        """Saham harga 45 di intraday 15m harus gugur (min price 50)."""
        ohlcv = pd.DataFrame({"close": [45.0, 45.0]})
        r = engine._check_min_price_filter(ohlcv, timeframe="15m")
        assert r.passed is False
        assert r.category == "min_price"

    def test_intraday_min_price_55_passes(self, engine):
        """Saham harga 55 di intraday 15m harus lolos."""
        ohlcv = pd.DataFrame({"close": [55.0, 55.0]})
        r = engine._check_min_price_filter(ohlcv, timeframe="15m")
        assert r.passed is True

    def test_intraday_volume_tightened_to_200k(self, engine):
        """Volume 150.000 lembar gugur di intraday (karena min 200.000)."""
        tech = make_technical(volume_avg_20=150_000)
        ohlcv = make_ohlcv_df(avg_value=5_000_000_000)
        r = engine._check_liquidity_filter(tech, ohlcv, timeframe="15m")
        assert r.passed is False
        assert r.category == "volume"

    def test_intraday_value_tightened_to_2b(self, engine):
        """Value Rp 1.5 Miliar gugur di intraday (karena min Rp 2 Miliar)."""
        tech = make_technical(volume_avg_20=500_000)
        ohlcv = make_ohlcv_df(avg_value=1_500_000_000)
        r = engine._check_liquidity_filter(tech, ohlcv, timeframe="15m")
        assert r.passed is False
        assert r.category == "value"


# ─────────────────────────────────────────────
#  Suspended Stock Filter (Pagi 1d & Siang 15m)
# ─────────────────────────────────────────────

class TestSuspendedFilter:
    """Saham yang sedang suspen harus langsung gugur di scan pagi maupun scan siang."""

    def test_daily_last_day_zero_volume_fails_immediately(self, engine):
        """Meskipun 2 hari lalu ramai, jika hari terakhir volume=0 (baru suspen), gugur."""
        ohlcv = make_ohlcv_df(rows=30)
        ohlcv.iloc[-1, ohlcv.columns.get_loc("volume")] = 0
        r = engine._check_suspended_filter(ohlcv, timeframe="1d")
        assert r.passed is False
        assert r.category == "suspended"

    def test_daily_stale_date_vs_ihsg_fails_immediately(self, engine):
        """Jika bar terakhir tertinggal dari tanggal IHSG (^JKSE), langsung dianggap suspen."""
        ohlcv = make_ohlcv_df(rows=30)
        latest_ihsg_date = pd.to_datetime(ohlcv["date"].iloc[-1]).date() + pd.Timedelta(days=2)
        r = engine._check_suspended_filter(ohlcv, timeframe="1d", latest_market_date=latest_ihsg_date)
        assert r.passed is False
        assert r.category == "suspended"

    def test_intraday_15m_today_zero_volume_fails_immediately(self, engine):
        """Di scan siang 15m, jika seluruh sesi hari terakhir bervolume 0 -> gugur."""
        dates = (
            [pd.Timestamp("2026-11-10 09:00:00"), pd.Timestamp("2026-11-10 09:15:00")] +
            [pd.Timestamp("2026-11-11 09:00:00"), pd.Timestamp("2026-11-11 09:15:00")]
        )
        ohlcv = pd.DataFrame({
            "date": dates,
            "close": [1000.0, 1000.0, 1000.0, 1000.0],
            "volume": [500_000, 500_000, 0, 0],
        })
        r = engine._check_suspended_filter(ohlcv, timeframe="15m")
        assert r.passed is False
        assert r.category == "suspended"

    def test_run_hard_filters_catches_suspended_first_and_tracks_stat(self, engine):
        """_run_hard_filters langsung memfilter saham suspen dengan category 'suspended'."""
        ohlcv = make_ohlcv_df(rows=30)
        ohlcv.iloc[-1, ohlcv.columns.get_loc("volume")] = 0
        tech = make_technical(adx=25.0, atr_percent=2.0, volume_avg_5=10_000_000)
        r = engine._run_hard_filters(tech, ohlcv, data_len=30, timeframe="1d")
        assert r.passed is False
        assert r.category == "suspended"

    def test_scanner_fetch_stock_data_rejects_suspended_without_goapi(self):
        """ScannerEngine._fetch_stock_data langsung gugurkan saham suspen sebelum memanggil GoAPI."""
        from unittest.mock import MagicMock
        from services.scanner_engine import ScannerEngine

        scanner = ScannerEngine.__new__(ScannerEngine)
        scanner.scoring_engine = ScoringEngine()
        scanner.data_provider = MagicMock()

        ohlcv = make_ohlcv_df(rows=40)
        ohlcv.iloc[-1, ohlcv.columns.get_loc("volume")] = 0
        scanner.data_provider.get_ohlcv.return_value = ohlcv

        res = scanner._fetch_stock_data("ABCD", interval="1d", period_days=365, pure_technical=False)
        assert "error" in res
        assert "suspen" in res["error"].lower()
        scanner.data_provider.get_broker_summary.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
