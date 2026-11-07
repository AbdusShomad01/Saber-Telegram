"""
Unit Test: Validasi total skor ScoringEngine tidak pernah melebihi/kurang dari 0-100.

Jalankan dengan:
    python -m pytest tests/test_scoring_total.py -v
    atau
    python tests/test_scoring_total.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd  # type: ignore
import numpy as np
from services.scoring_engine import ScoringEngine
from services.gap_engine import GapEngine
from services.sector_correlation_engine import SectorCorrelationEngine


def make_ohlcv(n=60, base_price=1000.0, trend="up") -> pd.DataFrame:
    """Helper: buat DataFrame OHLCV sintetis."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    
    if trend == "up":
        closes = [base_price * (1 + 0.002 * i + np.random.normal(0, 0.005)) for i in range(n)]
    elif trend == "down":
        closes = [base_price * (1 - 0.002 * i + np.random.normal(0, 0.005)) for i in range(n)]
    else:
        closes = [base_price * (1 + np.random.normal(0, 0.01)) for i in range(n)]

    closes = [max(c, 50.0) for c in closes]
    volumes = [int(10_000_000 * (1 + np.random.uniform(-0.3, 0.5))) for _ in range(n)]

    return pd.DataFrame({
        "date":   dates,
        "open":   [c * 0.995 for c in closes],
        "high":   [c * 1.01  for c in closes],
        "low":    [c * 0.99  for c in closes],
        "close":  closes,
        "volume": volumes,
        "value":  [v * p for v, p in zip(volumes, closes)],
    })


def make_technical_bullish() -> dict:
    return {
        "ema_10": 1050.0, "ema_20": 1030.0, "ema_50": 1000.0,
        "ema_alignment_bullish": True, "ema_alignment_bearish": False,
        "price_above_ema20": True, "price_above_ema50": True, "price_above_ema200": False,
        "macd": 5.0, "macd_signal": 3.0, "macd_histogram": 2.0,
        "macd_bullish_cross": True, "macd_bearish_cross": False,
        "macd_above_zero": True, "macd_histogram_rising": True,
        "adx": 28.0, "adx_trending": True, "adx_strong_trend": False,
        "adx_no_trend": False, "di_bullish": True,
        "rsi": 55.0, "rsi_overbought": False, "rsi_oversold": False,
        "rsi_bullish_zone": True, "rsi_divergence": None,
        "bb_upper": 1100.0, "bb_middle": 1040.0, "bb_lower": 980.0,
        "bb_percent_b": 0.65, "bb_squeeze": False,
        "price_above_upper_bb": False, "price_below_lower_bb": False,
        "stoch_k": 55.0, "stoch_d": 50.0,
        "stoch_overbought": False, "stoch_oversold": False, "stoch_bullish_cross": False,
        "atr": 20.0, "atr_percent": 2.0, "atr_expanding": False,
        "obv": 1_000_000, "obv_rising": True,
        "obv_divergence_bullish": False, "obv_divergence_bearish": False,
        "volume_current": 15_000_000, "volume_avg_20": 10_000_000, "volume_avg_5": 12_000_000,
        "volume_ratio": 1.5, "volume_breakout": False, "volume_dry_up": False,
        "volume_increasing": True, "volume_5_above_20": True,
        "volume_is_buying": True, "volume_is_selling": False,
        "vwap": 1035.0, "price_above_vwap": True, "vwap_slope": 0.5,
        "daily_trend_bias": None,
    }


def make_bandarmology(real=False, signal="neutral") -> dict:
    return {
        "is_real_data": real,
        "bandar_score": 5 if signal == "accumulation" else 0,
        "bandar_signal": signal,
        "smart_vs_retail_divergence": False,
        "accumulation_detected": False,
        "distribution_detected": False,
        "smart_money_buying": False,
    }


def make_foreign_flow(real=False, signal="neutral") -> dict:
    return {
        "is_real_data": real,
        "ff_score": 3 if signal == "foreign_buy" else 0,
        "ff_signal": signal,
        "ff_net_value_today": 0,
        "ff_net_5d": 0,
        "ff_momentum": "flat",
    }


def make_pattern(bias="neutral") -> dict:
    score = 5 if bias == "bullish" else (-5 if bias == "bearish" else 0)
    return {"patterns": [], "pattern_score": score, "pattern_bias": bias, "pattern_count": 0}


def make_candle(bias="neutral") -> dict:
    score = 3 if bias == "bullish" else (-3 if bias == "bearish" else 0)
    return {"candle_patterns": [], "candle_score": score, "candle_bias": bias, "candle_count": 0}


# ===================================================================
# TEST CASES
# ===================================================================

def test_score_in_range_free_mode():
    """Total skor harus selalu [0, 100] di FREE mode."""
    engine = ScoringEngine()
    df = make_ohlcv(60, trend="up")
    technical = make_technical_bullish()
    technical["_data_length"] = 60

    result = engine.score(
        ticker="TEST.JK",
        technical=technical,
        pattern=make_pattern("bullish"),
        candle=make_candle("bullish"),
        bandarmology=make_bandarmology(real=False, signal="accumulation"),
        foreign_flow=make_foreign_flow(real=False, signal="foreign_buy"),
        ohlcv_df=df,
        gap_analysis={"gap_type": "gap_up_confirmed", "gap_pct": 1.5, "gap_confirmed": True, "gap_score": 5},
        sector_correlation={"corr_signal": "outperform", "relative_strength": 3.0, "sector_score": 4},
    )
    assert 0 <= result.total_score <= 100, f"FREE mode score out of range: {result.total_score}"
    assert result.data_mode in ("free", "standard")
    print(f"  [OK] FREE mode, score = {result.total_score:.1f}/100")


def test_score_in_range_premium_mode():
    """Total skor harus selalu [0, 100] di PREMIUM mode."""
    engine = ScoringEngine()
    df = make_ohlcv(60, trend="up")
    technical = make_technical_bullish()

    result = engine.score(
        ticker="TEST.JK",
        technical=technical,
        pattern=make_pattern("bullish"),
        candle=make_candle("bullish"),
        bandarmology=make_bandarmology(real=True, signal="strong_accumulation"),
        foreign_flow=make_foreign_flow(real=True, signal="strong_foreign_buy"),
        ohlcv_df=df,
        gap_analysis={"gap_type": "gap_up_confirmed", "gap_pct": 1.5, "gap_confirmed": True, "gap_score": 5},
        sector_correlation={"corr_signal": "outperform", "relative_strength": 3.0, "sector_score": 4},
    )
    assert 0 <= result.total_score <= 100, f"PREMIUM mode score out of range: {result.total_score}"
    assert result.data_mode in ("premium", "standard")
    print(f"  [OK] PREMIUM mode, score = {result.total_score:.1f}/100")


def test_score_bearish_not_negative():
    """Skor bearish extreme harus floor di 0."""
    engine = ScoringEngine()
    df = make_ohlcv(60, trend="down")
    technical = make_technical_bullish()
    # Override ke bearish
    technical.update({
        "ema_alignment_bullish": False, "ema_alignment_bearish": True,
        "price_above_ema20": False, "macd_bearish_cross": True, "macd_bullish_cross": False,
        "adx_trending": False, "di_bullish": False, "rsi": 25.0,
        "obv_rising": False, "volume_dry_up": True, "price_above_vwap": False,
    })

    result = engine.score(
        ticker="TEST.JK",
        technical=technical,
        pattern=make_pattern("bearish"),
        candle=make_candle("bearish"),
        bandarmology=make_bandarmology(real=True, signal="strong_distribution"),
        foreign_flow=make_foreign_flow(real=True, signal="strong_foreign_sell"),
        ohlcv_df=df,
        gap_analysis={"gap_type": "gap_down", "gap_pct": -2.0, "gap_confirmed": False, "gap_score": -3},
        sector_correlation={"corr_signal": "underperform", "relative_strength": -4.0, "sector_score": -2},
    )
    assert result.total_score >= 0, f"Score went negative: {result.total_score}"
    print(f"  [OK] Bearish extreme, score = {result.total_score:.1f}/100 (floored at 0)")


def test_weights_sum_free():
    """Bobot FREE mode harus berjumlah tepat 100."""
    engine = ScoringEngine()
    categories = engine._get_categories("free")
    total = sum(categories.values())
    assert abs(total - 100) < 0.01, f"FREE mode weights sum = {total} (bukan 100!)"

    # Validasi 75% Teknikal, 15% Broker Summary (Bandarmology), 10% Foreign Flow
    technical_cats = ["trend_momentum", "volume_liquidity", "pattern", "gap_analysis", "sector_correlation", "support_resistance"]
    technical_sum = sum(categories[cat] for cat in technical_cats)
    assert abs(technical_sum - 75.0) < 0.01, f"Technical weight sum = {technical_sum} (harus 75%)"
    assert abs(categories["bandarmology"] - 15.0) < 0.01, f"Bandarmology weight = {categories['bandarmology']} (harus 15%)"
    assert abs(categories["foreign_flow"] - 10.0) < 0.01, f"Foreign Flow weight = {categories['foreign_flow']} (harus 10%)"
    print(f"  [OK] FREE mode weights sum = {total} (Teknikal: {technical_sum}%, Broker: {categories['bandarmology']}%, Foreign: {categories['foreign_flow']}%)")


def test_weights_sum_premium():
    """Bobot PREMIUM mode harus berjumlah tepat 100."""
    engine = ScoringEngine()
    categories = engine._get_categories("premium")
    total = sum(categories.values())
    assert abs(total - 100) < 0.01, f"PREMIUM mode weights sum = {total} (bukan 100!)"

    technical_cats = ["trend_momentum", "volume_liquidity", "pattern", "gap_analysis", "sector_correlation", "support_resistance"]
    technical_sum = sum(categories[cat] for cat in technical_cats)
    assert abs(technical_sum - 75.0) < 0.01, f"Technical weight sum = {technical_sum} (harus 75%)"
    assert abs(categories["bandarmology"] - 15.0) < 0.01, f"Bandarmology weight = {categories['bandarmology']} (harus 15%)"
    assert abs(categories["foreign_flow"] - 10.0) < 0.01, f"Foreign Flow weight = {categories['foreign_flow']} (harus 10%)"
    print(f"  [OK] PREMIUM mode weights sum = {total} (Teknikal: {technical_sum}%, Broker: {categories['bandarmology']}%, Foreign: {categories['foreign_flow']}%)")


def test_gap_engine():
    """GapEngine harus mendeteksi gap up dengan benar."""
    df = make_ohlcv(25)
    # Paksa gap up besar di hari terakhir
    df.loc[df.index[-1], "open"] = df["close"].iloc[-2] * 1.025  # 2.5% gap up
    df.loc[df.index[-1], "volume"] = int(df["volume"].tail(20).mean() * 2.0)  # Volume 2x

    result = GapEngine(df).analyze()
    assert result["gap_type"] == "gap_up_confirmed", f"Expected gap_up_confirmed, got {result['gap_type']}"
    assert result["gap_score"] == 5
    print(f"  [OK] GapEngine gap_up_confirmed, pct={result['gap_pct']:.2f}%")


def test_sector_correlation_outperform():
    """SectorCorrelationEngine harus mendeteksi outperform dengan benar."""
    stock_df = make_ohlcv(10, base_price=1000, trend="up")
    ihsg_df  = make_ohlcv(10, base_price=7000, trend="down")  # IHSG turun, saham naik

    result = SectorCorrelationEngine(stock_df, ihsg_df).analyze()
    assert result["sector_score"] >= 2, f"Expected sector_score >= 2, got {result['sector_score']}"
    print(f"  [OK] SectorCorrelation outperform, RS={result['relative_strength']:.2f}%")


def test_score_adx_logic():
    """Validasi logika ADX yang baru sesuai spesifikasi tiered scoring."""
    engine = ScoringEngine()

    # Test 1: Warm-up guard (day < 28)
    res_warmup = engine.score_adx(35.0, 20)
    assert res_warmup["score"] == 0
    assert res_warmup["low_confidence"] is True
    
    # Test 2: Boundaries (day >= 28)
    assert engine.score_adx(14.0, 30)["score"] == 0  # < 15
    assert engine.score_adx(15.0, 30)["score"] == 1  # 15 - 19.99
    assert engine.score_adx(20.0, 30)["score"] == 2  # 20 - 24.99
    assert engine.score_adx(25.0, 30)["score"] == 3  # 25 - 40 (Sweet spot)
    assert engine.score_adx(40.0, 30)["score"] == 3  # 25 - 40
    
    # Test 3: ADX > 40 tidak pernah maksimal (max 3, harus turun)
    assert engine.score_adx(45.0, 30)["score"] == 2  # > 40, <= 50
    assert engine.score_adx(55.0, 30)["score"] == 1  # > 50

    print("  [OK] score_adx logic (warm-up, boundaries, overextended penalty) passed")


def test_rsi_four_new_rules():
    """Test 4 kondisi baru logika RSI."""
    engine = ScoringEngine()

    # Rule 1: RSI > 80 konsisten 4 periode -> +4 poin
    t1 = {"rsi": 84.0, "rsi_consistent_above_80": True}
    rules1 = engine._score_trend_momentum(t1)
    r1 = next((r for r in rules1 if "RSI Super Momentum" in r.name), None)
    assert r1 is not None, "Rule 1 tidak ditemukan"
    assert r1.score == 4

    # Rule 2: RSI > 80 pembalikan arah ke < 80 -> -4 poin
    t2 = {"rsi": 77.0, "rsi_prev": 82.0, "rsi_reversal_down_from_80": True}
    rules2 = engine._score_trend_momentum(t2)
    r2 = next((r for r in rules2 if "RSI Overbought Reversal" in r.name), None)
    assert r2 is not None, "Rule 2 tidak ditemukan"
    assert r2.score == -4

    # Rule 3: RSI < 30 konsisten 4 periode -> -4 poin
    t3 = {"rsi": 24.0, "rsi_consistent_below_30": True}
    rules3 = engine._score_trend_momentum(t3)
    r3 = next((r for r in rules3 if "RSI Persistent Oversold" in r.name), None)
    assert r3 is not None, "Rule 3 tidak ditemukan"
    assert r3.score == -4

    # Rule 4: RSI < 30 pembalikan arah ke > 30 -> +4 poin
    t4 = {"rsi": 33.0, "rsi_prev": 27.0, "rsi_reversal_up_from_30": True}
    rules4 = engine._score_trend_momentum(t4)
    r4 = next((r for r in rules4 if "RSI Oversold Reversal" in r.name), None)
    assert r4 is not None, "Rule 4 tidak ditemukan"
    assert r4.score == 4

    print("  [OK] 4 aturan baru logika RSI (Super Momentum, Overbought Reversal, Falling Knife, Bullish Rebound) passed")


if __name__ == "__main__":
    tests = [
        test_weights_sum_free,
        test_weights_sum_premium,
        test_gap_engine,
        test_sector_correlation_outperform,
        test_score_adx_logic,
        test_score_in_range_free_mode,
        test_score_in_range_premium_mode,
        test_score_bearish_not_negative,
    ]
    
    print("=" * 60)
    print("Saber Trader Scoring Engine - Unit Tests")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for t in tests:
        name = t.__name__
        try:
            print(f"\n[TEST] {name}")
            t()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
