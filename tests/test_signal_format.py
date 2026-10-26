"""
Unit tests for the revamped Telegram Signal Format.
"""

import pytest
from templates.telegram_signal_template import format_signal_message
from services.stock_universe_service import is_syariah_stock


def test_syariah_classification():
    assert is_syariah_stock("GZCO") is True
    assert is_syariah_stock("ANTM") is True
    assert is_syariah_stock("BRIS") is True
    assert is_syariah_stock("BBCA") is False
    assert is_syariah_stock("BBRI") is False
    assert is_syariah_stock("HMSP") is False


def test_format_signal_exact_user_spec():
    sample_signal_data = {
        "ticker": "GZCO",
        "signal": "WATCHLIST",
        "is_syariah": True,
        "entry_price": 134,
        "tp1": 142,
        "stop_loss_atr": 125,
        "stop_loss_moderate": 127,
        "stop_loss_conservative": 130,
        "technical": {
            "macd": 1.24,
            "macd_signal": 0.20,
            "rsi": 63.93,
            "volume_5d_label": "Rendah (58%) 🟡",
            "ema_20": 130,
            "ema_50": 133,
            "vwap": 130,
            "price_above_vwap": True,
            "adx": 26.26,
            "bb_lower": 121,
            "bb_upper": 136,
            "atr": 3,
            "beta": 1.83,
            "beta_label": "Very High",
            "volatility": 79.0,
        },
        "patterns": {
            "patterns": ["Recovery Bounce dari Low", "Higher Highs"]
        },
        "candles": {
            "candle_patterns": ["Bullish Momentum dengan Doji/Spinning Top di Resistance"]
        },
        "bandarmology": {
            "is_real_data": False,
        },
        "analyst_opinion": (
            "GZCO menunjukkan pemulihan kuat dari low 110 ke 134 pada timeframe 60m dengan MACD positif dan harga di atas EMA20/EMA50, "
            "namun mendekati resistance Fibonacci 61.8% di 135 dan batas atas Bollinger Band 136 sehingga perlu konfirmasi breakout sebelum entry. "
            "Sentimen berita mixed (direktur lepas 5 juta saham = sinyal bearish insider, absen dividen) menjadi penahan, tunggu penutupan di atas 136 dengan volume kuat sebagai konfirmasi BUY."
        ),
        "news": {
            "headlines": [
                "Menakar Prospek Saham GZCO, Fundamental Membaik tapi Risiko Produksi Masih Me...",
                "Direktur GZCO Lepas 5 Juta Saham, Sinyal Apa? - Pasardana",
                "Rekomendasi Saham Hari Ini: ARCI, GZCO, dan IMPC - Ajaib",
            ]
        }
    }

    msg = format_signal_message(sample_signal_data)

    expected = """Saham: GZCO 🟢 SYARIAH
Signal: WATCHLIST


💵 Entry Price: Rp134
🎯 TP1: Rp142 (+6.0%)

Stop Loss:
Default (ATR): Rp125 (-6.7%)
Moderat (-5%): Rp127
Konservatif (-3%): Rp130

📊 Technical:
- MACD: 1.24 (Sig: 0.20) 🟢 Bullish
- RSI (14): 63.93 🟡 Overbought
- Volume (vs rata2 5hr): Rendah (58%) 🟡
- EMA 20/50: Rp130 / Rp133 🔴 Bearish
- VWAP: Rp130 🟢 Above
- ADX: 26.26 🟢 Strong
- BB: [Rp121 - Rp136]
- ATR: Rp3

👁️ Pattern:
- Chart: Recovery Bounce dari Low + Higher Highs ⚪
- Candle: Bullish Momentum dengan Doji/Spinning Top di Resistance ⚪

🏦 Bandarmology: Data sedang maintenance

📈 Beta: 1.83 (Very High) | Volatilitas: 79%

💡 Analyst Opinion:
GZCO menunjukkan pemulihan kuat dari low 110 ke 134 pada timeframe 60m dengan MACD positif dan harga di atas EMA20/EMA50, namun mendekati resistance Fibonacci 61.8% di 135 dan batas atas Bollinger Band 136 sehingga perlu konfirmasi breakout sebelum entry. Sentimen berita mixed (direktur lepas 5 juta saham = sinyal bearish insider, absen dividen) menjadi penahan, tunggu penutupan di atas 136 dengan volume kuat sebagai konfirmasi BUY.

📰 Berita Terkait:
• Menakar Prospek Saham GZCO, Fundamental Membaik tapi Risiko Produksi Masih Me...
• Direktur GZCO Lepas 5 Juta Saham, Sinyal Apa? - Pasardana
• Rekomendasi Saham Hari Ini: ARCI, GZCO, dan IMPC - Ajaib"""

    assert msg.strip() == expected.strip()
