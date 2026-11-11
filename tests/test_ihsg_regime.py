import pytest
from services.regime_engine import get_ihsg_regime, apply_ihsg_regime_adjustment

def test_ihsg_regime_bullish():
    # MA5 > MA20 and change_20d > 2%
    # Start with base 100, end with 105 (5% change)
    prices = [100.0] * 15 + [102.0, 103.0, 104.0, 105.0, 106.0] 
    # MA5 = (102+103+104+105+106)/5 = 104.0
    # MA20 = (100*15 + 102+103+104+105+106)/20 = 101.0
    # MA5 > MA20
    # Change = (106 - 100) / 100 = +6% (> 2%)
    
    assert get_ihsg_regime(prices) == "bullish"

def test_ihsg_regime_bearish():
    # MA5 < MA20 and change_20d < -2%
    # Start with base 100, end with 95 (-5% change)
    prices = [100.0] * 15 + [98.0, 97.0, 96.0, 95.0, 94.0] 
    # MA5 = (98+97+96+95+94)/5 = 96.0
    # MA20 = (100*15 + 98+97+96+95+94)/20 = 99.0
    # MA5 < MA20
    # Change = (94 - 100) / 100 = -6% (< -2%)
    
    assert get_ihsg_regime(prices) == "bearish"

def test_ihsg_regime_sideways_flat():
    # MA5 == MA20, flat
    prices = [100.0] * 20
    assert get_ihsg_regime(prices) == "sideways"

def test_ihsg_regime_sideways_small_change():
    # Change < 2%, MA5 > MA20
    prices = [100.0] * 15 + [100.0, 100.0, 101.0, 101.0, 101.0]
    # MA5 = 100.6, MA20 = 100.15
    # Change = (101 - 100)/100 = 1% 
    assert get_ihsg_regime(prices) == "sideways"
    
def test_regime_adjustment_logic():
    # IHSG murni sebagai informasi konteks pasar, skor saham tidak dimodifikasi
    assert apply_ihsg_regime_adjustment(80.0, "bullish") == 80.0
    assert apply_ihsg_regime_adjustment(80.0, "bearish") == 80.0
    assert apply_ihsg_regime_adjustment(80.0, "sideways") == 80.0
    assert apply_ihsg_regime_adjustment(80.0, "bullish", is_intraday=True) == 80.0
    assert apply_ihsg_regime_adjustment(80.0, "bearish", is_intraday=True) == 80.0


def test_regime_adjustment_clamp():
    # Skor tetap di-clamp di range [0.0, 100.0]
    assert apply_ihsg_regime_adjustment(105.0, "bullish") == 100.0
    assert apply_ihsg_regime_adjustment(-10.0, "bearish") == 0.0
    assert apply_ihsg_regime_adjustment(75.5, "bullish") == 75.5


def test_ihsg_regime_ignores_trailing_nan():
    import math
    import pandas as pd
    from unittest.mock import MagicMock
    from services.regime_engine import RegimeEngine

    prices = [5000.0 + i * 10.0 for i in range(21)] + [float("nan")]
    assert get_ihsg_regime(prices) == "bullish"

    dp = MagicMock()
    dp.get_ohlcv.return_value = pd.DataFrame({
        "date": pd.date_range("2026-10-01", periods=22, freq="B"),
        "close": prices,
    })
    regime = RegimeEngine(dp).get_ihsg_regime()
    assert regime["regime"] == "BULLISH"
    assert math.isfinite(regime["last_price"])
    assert math.isfinite(regime["ema_20"])
    assert "nan" not in regime["description"].lower()
