"""
IDX AI Signal Bot - LLM Engine
Uses Claude or Gemini to generate analyst opinions and run the visual Strategy Agent.
Migrated to google.genai (new official SDK) from deprecated google.generativeai.
"""

import json
import re
import logging
import base64
from typing import Dict, Any, Optional

from app.config import get_settings
from templates.analyst_prompt_template import build_analyst_prompt

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMEngine:
    """
    LLM integration for:
    1. Analyst opinion generation (narrative writing).
    2. Strategy Agent (multimodal visual analysis + indicator cross-check + IHSG regime filter).
    """

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.LLM_PROVIDER
        self._gemini_client = None

    def _get_gemini_client(self):
        """Lazy-init Gemini client (reuse across calls)."""
        if self._gemini_client is None:
            from google import genai
            self._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._gemini_client

    # ------------------------------------------------------------------ #
    #  Opinion Generator (Text-only)
    # ------------------------------------------------------------------ #

    async def generate_opinion(
        self,
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
        Generate professional analyst opinion using LLM.
        """
        prompt = build_analyst_prompt(
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            technical=technical,
            pattern=pattern,
            candle=candle,
            bandarmology=bandarmology,
            foreign_flow=foreign_flow,
            risk_levels=risk_levels,
            news=news,
        )

        try:
            if self.provider == "claude":
                return await self._call_claude(prompt)
            elif self.provider == "gemini":
                return await self._call_gemini(prompt, model_name="gemini-2.5-flash")
            else:
                return self._fallback_opinion(ticker, signal, confidence)
        except Exception as e:
            logger.error(f"LLM opinion generation failed: {e}")
            return self._fallback_opinion(ticker, signal, confidence)

    async def _call_claude(self, prompt: str) -> str:
        """Call Anthropic Claude API."""
        if not settings.CLAUDE_API_KEY:
            logger.warning("Claude API key not set")
            return "Opini analis tidak tersedia — API key belum dikonfigurasi."

        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)
            message = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

        except ImportError:
            logger.error("anthropic package not installed")
            return "Opini analis tidak tersedia — package anthropic belum terinstall."
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def _call_gemini(self, prompt: str, model_name: str = "gemini-2.5-flash") -> str:
        """Call Google Gemini API using new google.genai SDK."""
        if not settings.GEMINI_API_KEY:
            logger.warning("Gemini API key not set")
            return "Opini analis tidak tersedia — API key belum dikonfigurasi."

        try:
            client = self._get_gemini_client()

            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text
            except Exception as inner_e:
                if "429" in str(inner_e) or "quota" in str(inner_e).lower():
                    logger.warning(f"Gemini {model_name} quota exceeded. Falling back to gemini-2.0-flash.")
                    response = await client.aio.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                    )
                    return response.text
                raise inner_e

        except ImportError:
            logger.error("google-genai package not installed. Run: pip install google-genai")
            return "Opini analis tidak tersedia — package google-genai belum terinstall."
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    def _fallback_opinion(self, ticker: str, signal: str, confidence: int) -> str:
        """Fallback opinion when LLM is unavailable."""
        signal_text = {
            "STRONG BUY": "sangat bullish dengan conviction tinggi",
            "BUY": "bullish dengan setup yang solid",
            "WATCHLIST": "menarik untuk dipantau namun belum ideal untuk entry",
            "AVOID": "sebaiknya dihindari karena setup kurang mendukung",
            "SELL": "bearish dan disarankan untuk keluar dari posisi",
        }

        desc = signal_text.get(signal, "netral")

        return (
            f"📊 **Opini Analis — {ticker}**\n\n"
            f"Berdasarkan analisis teknikal, bandarmology, dan foreign flow, "
            f"saham {ticker} saat ini {desc}. "
            f"Confidence score: {confidence}/10.\n\n"
            f"_Catatan: Opini ini dihasilkan secara otomatis. "
            f"Selalu lakukan riset mandiri sebelum mengambil keputusan investasi._"
        )

    # ------------------------------------------------------------------ #
    #  Strategy Agent (Visual + Multi-Indicator Analysis)
    # ------------------------------------------------------------------ #

    async def run_strategy_agent(
        self,
        ticker: str,
        technical: Dict[str, Any],
        pattern: Dict[str, Any],
        candle: Dict[str, Any],
        bandarmology: Dict[str, Any],
        foreign_flow: Dict[str, Any],
        risk_levels: Dict[str, Any],
        ihsg_regime: Dict[str, Any],
        image_path: str,
    ) -> Dict[str, Any]:
        """
        Run the multimodal Strategy Agent.
        Uses visual chart analysis and cross-checks all indicators with the IHSG regime filter.
        Returns a dict: {
           "decision": str,
           "confidence_score": int,
           "chart_visual_analysis": str,
           "indicators_cross_check": str,
           "ihsg_regime_impact": str,
           "final_reasoning": str
        }
        """
        prompt = self._build_strategy_agent_prompt(
            ticker=ticker,
            technical=technical,
            pattern=pattern,
            candle=candle,
            bandarmology=bandarmology,
            foreign_flow=foreign_flow,
            risk_levels=risk_levels,
            ihsg_regime=ihsg_regime,
        )

        try:
            if self.provider == "claude" and settings.CLAUDE_API_KEY:
                raw_response = await self._call_claude_vision(prompt, image_path)
            elif self.provider == "gemini" and settings.GEMINI_API_KEY:
                raw_response = await self._call_gemini_vision(prompt, image_path, model_name="gemini-2.5-flash")
            else:
                logger.warning("No valid LLM credentials found for Strategy Agent. Falling back to rules.")
                raw_response = ""

            parsed = self._parse_json_response(raw_response)
            if parsed:
                return parsed

            logger.warning("Could not parse Strategy Agent response as JSON. Falling back to rules.")
            return {}

        except Exception as e:
            logger.error(f"Strategy Agent LLM execution failed: {e}", exc_info=True)
            return {}

    async def _call_gemini_vision(self, prompt: str, image_path: str, model_name: str = "gemini-2.5-flash") -> str:
        """Call Google Gemini Vision API using new google.genai SDK."""
        try:
            from google.genai import types

            client = self._get_gemini_client()

            # Read image bytes
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            # Determine MIME type
            mime_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"

            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=[image_part, prompt],
                )
                return response.text
            except Exception as inner_e:
                if "429" in str(inner_e) or "quota" in str(inner_e).lower():
                    logger.warning(f"Gemini Vision {model_name} quota exceeded. Falling back to gemini-2.0-flash.")
                    response = await client.aio.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=[image_part, prompt],
                    )
                    return response.text
                raise inner_e

        except Exception as e:
            logger.error(f"Gemini Vision API error: {e}")
            raise

    async def _call_claude_vision(self, prompt: str, image_path: str) -> str:
        """Call Anthropic Claude API with image context."""
        try:
            import anthropic

            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

            client = anthropic.AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)
            message = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": encoded_image,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Claude Vision API error: {e}")
            raise

    def _build_strategy_agent_prompt(
        self,
        ticker: str,
        technical: Dict[str, Any],
        pattern: Dict[str, Any],
        candle: Dict[str, Any],
        bandarmology: Dict[str, Any],
        foreign_flow: Dict[str, Any],
        risk_levels: Dict[str, Any],
        ihsg_regime: Dict[str, Any],
    ) -> str:
        """Build the rich strategy decision prompt in Indonesian."""
        patterns_list = pattern.get("patterns", [])
        candle_list = candle.get("candle_patterns", [])
        
        bandar_signal = bandarmology.get("bandar_signal", "neutral")
        ff_signal = foreign_flow.get("ff_signal", "neutral")
        
        entry = risk_levels.get("entry_price", 0)
        tp1 = risk_levels.get("tp1", 0)
        sl = risk_levels.get("stop_loss_conservative", 0)
        rr = risk_levels.get("risk_reward_ratio", 0)

        from app.config import get_settings
        settings = get_settings()

        mode_label = "SWING TRADING (EOD)"
        exit_rule = "Simpan saham selama beberapa hari hingga beberapa minggu sesuai dengan target profit dan stop loss."
        stop_loss_rule = "Stop loss diletakkan di bawah support kuat atau level ATR (sekitar 3-5%)."
        vwap_instruction = ""
        ema_instruction = "Lihat posisi harga terhadap garis EMA 20 (kuning) dan EMA 50 (biru). Apakah terjadi golden cross atau death cross?"
        indicators_desc = "EMA 20 & EMA 50"

        if settings.DAY_TRADE_MODE:
            mode_label = f"DAY TRADING (Intraday {settings.CHART_INTERVAL})"
            exit_rule = "Keluar dari posisi sebelum jam penutupan pasar 16:00 WIB hari ini. JANGAN MENAHAN POSISI SEMALAM (no overnight hold)."
            stop_loss_rule = "Disiplin ketat dengan stop loss yang sangat ketat (target 1% - 1.5% dari harga beli, atau exit ketika momentum melemah)."
            vwap_instruction = "- Perhatikan garis VWAP (garis putus-putus merah muda/magenta). Jika harga berada di atas VWAP, tandanya bullish intraday. Jika di bawah VWAP, tandanya bearish intraday."
            ema_instruction = "Lihat posisi harga terhadap garis EMA 9 dan EMA 21."
            indicators_desc = "EMA 9, EMA 21, dan VWAP"

        # Multi-Timeframe context (if available)
        mtf_section = ""
        daily_trend = technical.get("daily_trend_bias")
        if daily_trend:
            mtf_section = f"""
=== MULTI-TIMEFRAME ANALYSIS ===
📊 Daily Trend (Higher TF): **{daily_trend.upper()}**
- Daily EMA Alignment Bullish: {technical.get('daily_ema_alignment_bullish', 'N/A')}
- Daily RSI: {technical.get('daily_rsi', 'N/A')}
- Daily ADX: {technical.get('daily_adx', 'N/A')}
- PENTING: Jika daily trend BEARISH, jangan ambil sinyal BUY di intraday kecuali ada konfirmasi sangat kuat (reversal pattern + volume breakout).
- Jika daily trend BULLISH, sinyal BUY intraday jauh lebih reliable.
"""

        prompt = f"""Kamu adalah "Strategy Agent", otak utama (brain engine) dari Saber Trader AI Signal Bot.
Saat ini kamu beroperasi dalam mode: **{mode_label}**.

Tugas utama kamu adalah:
1. Menganalisis grafik candlestick (OHLCV, {indicators_desc}, Volume, RSI) secara visual yang dilampirkan.
2. Melakukan cross-check terhadap seluruh indikator teknikal, pola candlestick, bandarmology, dan foreign flow yang disediakan.
3. Menjadikan kondisi IHSG murni sebagai informasi konteks pasar makro (BUKAN sebagai penentu keputusan utama dan DILARANG menurunkan skor/sinyal hanya karena IHSG).
4. Menerapkan aturan trading yang ketat untuk mode {mode_label}:
   - Aturan Keluar: {exit_rule}
   - Aturan Stop Loss: {stop_loss_rule}
5. Menentukan keputusan akhir (BUY, STRONG BUY, WATCHLIST, AVOID, atau SELL) beserta skor keyakinan (confidence score 1-10) berdasarkan setup saham individual.

=== IHSG REGIME (ALAT INFORMASI SAJA — BUKAN PENURUN SKOR) ===
IHSG Regime: {ihsg_regime.get('regime', 'SIDEWAYS')} ({ihsg_regime.get('description', '')})

💡 PANDUAN PENGGUNAAN KONTEKS IHSG:
- Kondisi IHSG HANYA berfungsi sebagai alat informasi / wawasan pasar secara umum bagi trader.
- JANGAN PERNAH menurunkan skor, membatalkan sinyal, atau melarang keputusan BUY/STRONG BUY hanya karena kondisi IHSG sedang BEARISH atau SIDEWAYS.
- Banyak saham individual yang tetap naik kencang dan memberikan profit besar meskipun pasar IHSG sedang turun/sideways.
- Keputusan BUY/STRONG BUY/WATCHLIST/AVOID/SELL harus berfokus penuh dan murni pada kualitas setup saham itu sendiri (indikator teknikal, volume breakout, akumulasi bandar, foreign flow, dan Risk/Reward).
{mtf_section}
=== DATA INDIKATOR ===
Saham: {ticker}

📈 Technical & Momentum:
- RSI (14): {technical.get('rsi', 'N/A')}
- MACD: {technical.get('macd', 'N/A')}
- ADX: {technical.get('adx', 'N/A')}
- Trend EMAs: Price vs EMA9: {technical.get('price_above_ema9') if settings.DAY_TRADE_MODE else technical.get('price_above_ema20')}, Price vs EMA21: {technical.get('price_above_ema21') if settings.DAY_TRADE_MODE else technical.get('price_above_ema50')}
{"- Price vs VWAP: " + str(technical.get('price_above_vwap')) if settings.DAY_TRADE_MODE else ""}

🔍 Patterns & Candles:
- Chart Patterns: {', '.join(patterns_list) if patterns_list else 'Tidak ada'}
- Candle Patterns: {', '.join(candle_list) if candle_list else 'Tidak ada'}

🏦 Bandarmology Flow:
- Signal: {bandar_signal.replace('_', ' ').title()}
- Smart Money: {'Accumulation' if bandarmology.get('smart_money_buying') else 'Distribution'}
- Smart vs Retail Divergence: {bandarmology.get('smart_vs_retail_divergence')}

🌐 Foreign Flow:
- Signal: {ff_signal.replace('_', ' ').title()}
- Net Buy Today: Rp{foreign_flow.get('ff_net_value_today', 0):,.0f}

💰 Risk Levels:
- Entry Price Suggestion: Rp{entry:,.0f}
- TP1: Rp{tp1:,.0f}
- Stop Loss (Conservative): Rp{sl:,.0f}
- R:R Ratio: {rr:.2f}

=== INSTRUKSI ANALISIS GRAFIK SECARA VISUAL ===
Perhatikan gambar grafik yang diberikan:
- Amati trend pergerakan harga saat ini (uptrend, downtrend, sideways).
- {ema_instruction}
{vwap_instruction}
- Amati volume transaksi di panel tengah. Apakah volume meningkat saat harga naik?
- Perhatikan indikator RSI di panel bawah. Apakah jenuh beli (overbought) atau jenuh jual (oversold)?

=== FORMAT OUTPUT ===
Kamu WAJIB mengembalikan respon dalam format JSON yang valid. Jangan sertakan teks lain sebelum atau sesudah blok JSON. Format JSON harus persis seperti ini:
```json
{{
  "decision": "STRONG BUY",
  "confidence_score": 8,
  "chart_visual_analysis": "Penjelasan detail hasil analisis visual grafik (Maksimal 2-3 kalimat padat)",
  "indicators_cross_check": "Penjelasan hasil cross-check indikator teknikal dan aliran dana (Maksimal 2-3 kalimat padat)",
  "ihsg_regime_impact": "Informasi/konteks kondisi pasar IHSG saat ini sebagai wawasan makro (Maksimal 1-2 kalimat)",
  "final_reasoning": "Rangkuman kesimpulan akhir analisis (Maksimal 2-3 kalimat yang sangat jelas)"
}}
```
Catatan: "decision" harus salah satu dari: STRONG BUY, BUY, WATCHLIST, AVOID, SELL. "confidence_score" adalah integer 1-10."""
        return prompt

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse JSON block from LLM string."""
        if not text:
            return None
            
        # Try regex search for markdown JSON block
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass

        # Try searching for any curly braces block
        json_match2 = re.search(r"(\{.*?\})", text, re.DOTALL)
        if json_match2:
            try:
                return json.loads(json_match2.group(1))
            except Exception:
                pass

        # Try parsing directly
        try:
            return json.loads(text.strip())
        except Exception:
            return None
