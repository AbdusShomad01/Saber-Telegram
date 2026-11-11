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


def test_format_signal_morning_bandarmology_exact_spec():
    """Format Bandarmology scan pagi harus menampilkan Sinyal Bandar, Smart Money Net, Top 3 Buyer & Top 3 Seller."""
    sample_signal_data = {
        "ticker": "BBCA",
        "signal": "STRONG BUY",
        "is_syariah": False,
        "entry_price": 10000,
        "tp1": 10600,
        "stop_loss_atr": 9700,
        "stop_loss_moderate": 9500,
        "stop_loss_conservative": 9700,
        "technical": {
            "macd": 20.0,
            "macd_signal": 10.0,
            "rsi": 58.0,
            "ema_20": 9800,
            "ema_50": 9500,
            "vwap": 9950,
            "price_above_vwap": True,
            "adx": 30.0,
            "bb_lower": 9400,
            "bb_upper": 10400,
            "atr": 150,
        },
        "patterns": {"patterns": []},
        "candles": {"candle_patterns": []},
        "bandarmology": {
            "is_real_data": True,
            "bandar_signal": "strong_accumulation",
            "smart_money_net_latest": 225_000,
            "smart_money_flow": 1_500_000,
            "top_buyers": ["AK", "BK", "CC", "KZ"],
            "top_buyers_lots": {"AK": 122775, "BK": 70162, "CC": 41901, "KZ": 10000},
            "top_sellers": ["PD", "AZ", "NI", "XL"],  # tail = XL (seller terbesar)
            "top_sellers_lots": {"XL": 38532, "NI": 28068, "AZ": 23715, "PD": 12000},
        },
    }

    msg = format_signal_message(sample_signal_data)
    expected_bandar_block = """🏦 Bandarmology:
Sinyal Bandar: 🟢🟢 STRONG_BUY
Smart Money Net: +225K lot
🟢 Top Buyer:
AK : +122,775 lot
BK : +70,162 lot
CC : +41,901 lot
🔴 Top Seller:
XL : -38,532 lot
NI : -28,068 lot
AZ : -23,715 lot"""

    assert expected_bandar_block in msg

    # Di mode pure_technical (scan siang), tetap maintenance
    sample_signal_data["pure_technical"] = True
    noon_msg = format_signal_message(sample_signal_data)
    assert "🏦 Bandarmology: Data sedang maintenance" in noon_msg


def test_bandarmology_engine_latest_smart_money_and_mock_guard():
    """smart_money_net_latest hanya menghitung H-1 (cocok dengan Top Buyer/Seller) & data mock ditolak."""
    import pandas as pd
    from datetime import date
    from services.bandarmology_engine import BandarmologyEngine

    rows = [
        # H-2: AK jual besar (-1_000_000) agar beda dari H-1
        {"date": date(2026, 11, 1), "broker_code": "AK", "buy_lot": 0, "sell_lot": 1_000_000, "net_lot": -1_000_000, "buy_value": 0, "sell_value": 1e11, "investor_type": "foreign", "broker_category": "SM"},
        # H-1: AK, BK, CC beli bersih +225_000 total
        {"date": date(2026, 11, 2), "broker_code": "AK", "buy_lot": 122775, "sell_lot": 0, "net_lot": 122775, "buy_value": 1e10, "sell_value": 0, "investor_type": "foreign", "broker_category": "SM"},
        {"date": date(2026, 11, 2), "broker_code": "BK", "buy_lot": 70162, "sell_lot": 0, "net_lot": 70162, "buy_value": 7e9, "sell_value": 0, "investor_type": "foreign", "broker_category": "SM"},
        {"date": date(2026, 11, 2), "broker_code": "CC", "buy_lot": 32063, "sell_lot": 0, "net_lot": 32063, "buy_value": 3e9, "sell_value": 0, "investor_type": "domestic", "broker_category": "SM"},
        {"date": date(2026, 11, 2), "broker_code": "XL", "buy_lot": 0, "sell_lot": 38532, "net_lot": -38532, "buy_value": 0, "sell_value": 3e9, "investor_type": "domestic", "broker_category": "RT"},
        {"date": date(2026, 11, 2), "broker_code": "NI", "buy_lot": 0, "sell_lot": 28068, "net_lot": -28068, "buy_value": 0, "sell_value": 2e9, "investor_type": "domestic", "broker_category": "DI"},
    ]
    df_real = pd.DataFrame(rows)
    res_real = BandarmologyEngine(df_real).analyze()
    assert res_real["is_real_data"] is True
    assert res_real["smart_money_net_latest"] == 225_000
    assert res_real["top_buyers"][:3] == ["AK", "BK", "CC"]
    assert res_real["top_sellers"][::-1][:2] == ["XL", "NI"]

    # Mock DataFrame dengan attrs['is_mock'] = True harus ditolak
    df_mock = df_real.copy()
    df_mock.attrs["is_mock"] = True
    res_mock = BandarmologyEngine(df_mock).analyze()
    assert res_mock["is_real_data"] is False
