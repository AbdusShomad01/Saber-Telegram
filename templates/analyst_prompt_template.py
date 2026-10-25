"""
IDX AI Signal Bot - Analyst Prompt Template
Prompt templates for LLM-generated analyst opinions.

IMPORTANT: LLM only writes the narrative opinion.
All BUY/SELL decisions are made by the deterministic scoring engine.
"""

from typing import Dict, Any, Optional


def build_analyst_prompt(
    ticker: str,
    signal: str,
    confidence: int,
    technical: Dict[str, Any],
    pattern: Dict[str, Any],
    candle: Dict[str, Any],
    bandarmology: Dict[str, Any],
    foreign_flow: Dict[str, Any],
    risk_levels: Dict[str, Any],
    news: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build the prompt for LLM analyst opinion generation.
    The LLM is given pre-computed data and asked to write a professional opinion.
    It does NOT make the BUY/SELL decision.
    """

    # Extract key values
    rsi = technical.get("rsi", "N/A")
    macd = technical.get("macd", "N/A")
    adx = technical.get("adx", "N/A")
    ema_bullish = technical.get("ema_alignment_bullish", False)
    vol_ratio = technical.get("volume_ratio", "N/A")

    patterns_list = pattern.get("patterns", [])
    candle_list = candle.get("candle_patterns", [])

    bandar_signal = bandarmology.get("bandar_signal", "neutral")
    ff_signal = foreign_flow.get("ff_signal", "neutral")

    entry = risk_levels.get("entry_price", 0)
    tp1 = risk_levels.get("tp1", 0)
    sl = risk_levels.get("stop_loss_conservative", 0)
    rr = risk_levels.get("risk_reward_ratio", 0)

    headlines = news.get("headlines", []) if news else []

    prompt = f"""Kamu adalah analis saham senior Indonesia dengan pengalaman 15+ tahun di pasar IDX.

Berdasarkan data analisis berikut, tulis opini analis yang ringkas dan profesional dalam Bahasa Indonesia.

PENTING:
- Signal sudah ditentukan oleh sistem scoring deterministik: {signal}
- Kamu TIDAK boleh mengubah signal — tugasmu hanya menjelaskan MENGAPA signal ini masuk akal
- Tulis opini maksimal 3-4 kalimat, padat dan actionable
- Gunakan bahasa profesional tapi mudah dipahami

=== DATA ANALISIS ===

📌 Saham: {ticker}
📊 Signal: {signal} (Confidence: {confidence}/10)

📈 Technical Indicators:
- RSI(14): {rsi}
- MACD: {macd}
- ADX: {adx}
- EMA Alignment Bullish: {ema_bullish}
- Volume Ratio: {vol_ratio}x

🔍 Patterns: {', '.join(patterns_list) if patterns_list else 'Tidak ada'}
🕯 Candle: {', '.join(candle_list) if candle_list else 'Tidak ada'}

🏦 Bandarmology: {bandar_signal.replace('_', ' ').title()}
🌐 Foreign Flow: {ff_signal.replace('_', ' ').title()}

💰 Risk Management:
- Entry: Rp{entry:,.0f}
- TP1: Rp{tp1:,.0f}
- Stop Loss: Rp{sl:,.0f}
- R:R Ratio: {rr:.2f}"""

    if headlines:
        prompt += f"\n\n📰 Berita: {'; '.join(headlines[:3])}"

    prompt += """

=== FORMAT OUTPUT ===
Tulis opini dalam format:
[Paragraf 1: Kondisi teknikal dan momentum]
[Paragraf 2: Flow analysis — bandarmology & foreign flow]
[Paragraf 3: Rekomendasi risk management]

Jangan gunakan emoji atau formatting markdown. Plain text saja."""

    return prompt


NEWS_SUMMARY_PROMPT = """Kamu adalah editor berita keuangan Indonesia.
Rangkum berita-berita berikut menjadi 1-2 kalimat yang relevan untuk analisis saham.
Fokus pada dampak terhadap harga saham.

Berita:
{news_text}

Rangkuman (1-2 kalimat):"""
