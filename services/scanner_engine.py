"""
IDX AI Signal Bot - Scanner Engine
Orchestrates: Data → Technical → Pattern → Candle → Bandarmology → Foreign Flow → Scoring → Risk → Regime → Chart → Strategy LLM

v2 Improvements:
- Parallel batch data fetching for speed (ThreadPoolExecutor)
- Multi-Timeframe Analysis (daily trend cross-check for intraday)
- Bullish-only signal filtering
"""

import logging
import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import pandas as pd

from services.data_provider_service import DataProviderService
from services.technical_engine import TechnicalEngine
from services.pattern_engine import PatternEngine
from services.candle_engine import CandleEngine
from services.bandarmology_engine import BandarmologyEngine
from services.foreign_flow_engine import ForeignFlowEngine
from services.gap_engine import GapEngine
from services.sector_correlation_engine import SectorCorrelationEngine
from services.scoring_engine import ScoringEngine
from services.risk_engine import RiskEngine
from services.news_engine import NewsEngine
from services.llm_engine import LLMEngine
from services.regime_engine import RegimeEngine
from services.chart_service import ChartService
from services.stock_universe_service import get_stock_universe, get_stock_by_ticker, is_syariah_stock
from services.idx_full_universe_service import get_full_idx_universe, is_fca_stock
from database.models import Signal
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SignalOutput:
    ticker: str
    name: str
    sector: str
    signal: str
    confidence_score: int
    confidence_label: str
    raw_score: float
    entry_price: float
    tp1: float
    tp2: float                      # TP2 — partial exit 30%
    tp3: float                      # TP3 — hold 20%
    stop_loss_atr: float
    stop_loss_moderate: float
    stop_loss_conservative: float
    risk_reward_ratio: float
    technical_summary: Dict[str, Any]
    pattern_summary: Dict[str, Any]
    candle_summary: Dict[str, Any]
    bandarmology_summary: Dict[str, Any]
    foreign_flow_summary: Dict[str, Any]
    news_summary: Dict[str, Any]
    analyst_opinion: str
    category_scores: Dict[str, float]
    category_raw_scores: Optional[Dict[str, float]] = None
    chart_path: str = ""
    ihsg_regime: Optional[Dict[str, Any]] = None
    fib_levels: Optional[Dict[str, Any]] = None
    interval: str = ""
    pure_technical: bool = False
    is_syariah: Optional[bool] = None



class ScannerEngine:
    """Full market scanner — orchestrates all analysis engines."""

    def __init__(self):
        self.data_provider = DataProviderService()
        self.scoring_engine = ScoringEngine()
        self.risk_engine = RiskEngine()
        self.news_engine = NewsEngine()
        self.llm_engine = LLMEngine()
        self.regime_engine = RegimeEngine(self.data_provider)
        self._executor = ThreadPoolExecutor(max_workers=10)

    # ------------------------------------------------------------------ #
    #  Multi-Timeframe: Fetch daily trend for cross-check
    # ------------------------------------------------------------------ #
    def _fetch_daily_trend(self, ticker: str) -> Dict[str, Any]:
        """Fetch daily timeframe data and compute trend indicators for MTF cross-check."""
        try:
            daily_ohlcv = self.data_provider.get_ohlcv(ticker, period_days=120, interval="1d")
            if daily_ohlcv.empty or len(daily_ohlcv) < 50:
                return {}

            daily_tech = TechnicalEngine(daily_ohlcv).compute_all()

            # Determine overall daily trend bias
            bullish_signals = 0
            bearish_signals = 0

            if daily_tech.get("ema_alignment_bullish"):
                bullish_signals += 2
            if daily_tech.get("ema_alignment_bearish"):
                bearish_signals += 2
            if daily_tech.get("price_above_ema20"):
                bullish_signals += 1
            else:
                bearish_signals += 1
            if daily_tech.get("macd_above_zero"):
                bullish_signals += 1
            else:
                bearish_signals += 1
            if daily_tech.get("adx_trending") and daily_tech.get("di_bullish"):
                bullish_signals += 1
            elif daily_tech.get("adx_trending") and not daily_tech.get("di_bullish"):
                bearish_signals += 1

            rsi = daily_tech.get("rsi", 50)
            if rsi and rsi > 50:
                bullish_signals += 1
            elif rsi and rsi < 50:
                bearish_signals += 1

            if bullish_signals > bearish_signals + 1:
                trend_bias = "bullish"
            elif bearish_signals > bullish_signals + 1:
                trend_bias = "bearish"
            else:
                trend_bias = "sideways"

            return {
                "daily_trend_bias": trend_bias,
                "daily_ema_alignment_bullish": daily_tech.get("ema_alignment_bullish", False),
                "daily_ema_alignment_bearish": daily_tech.get("ema_alignment_bearish", False),
                "daily_rsi": daily_tech.get("rsi"),
                "daily_adx": daily_tech.get("adx"),
                "daily_macd_above_zero": daily_tech.get("macd_above_zero"),
                "daily_price_above_ema20": daily_tech.get("price_above_ema20"),
                "daily_price_above_ema50": daily_tech.get("price_above_ema50"),
            }
        except Exception as e:
            logger.warning(f"[{ticker}] Multi-TF daily trend fetch failed: {e}")
            return {}

    # ------------------------------------------------------------------ #
    #  Parallel Data Fetching
    # ------------------------------------------------------------------ #
    def _fetch_stock_data(self, ticker: str, interval: str, period_days: int, pure_technical: bool = False) -> Dict[str, Any]:
        """Fetch all data for a single stock (runs in thread pool for parallelism)."""
        try:
            ohlcv = self.data_provider.get_ohlcv(ticker, period_days=period_days, interval=interval)
            if ohlcv.empty or len(ohlcv) < 30:
                return {"ticker": ticker, "error": f"Data tidak cukup ({len(ohlcv)} rows)"}

            # Filter out suspended or completely illiquid stocks
            last_3_vol = ohlcv["volume"].tail(3).sum()
            if last_3_vol == 0:
                return {"ticker": ticker, "error": "Saham suspen atau tidak likuid (volume 0)"}

            # Get the last actual trading day
            last_date_val = ohlcv["date"].iloc[-1]
            if isinstance(last_date_val, datetime.date):
                last_trading_day = last_date_val
            else:
                last_trading_day = pd.to_datetime(last_date_val).date()

            # In Pure Technical Mode (Screener Siang): Skip GoAPI & Supabase completely
            if pure_technical:
                broker_data = pd.DataFrame(columns=["date", "broker_code", "buy_lot", "sell_lot", "net_lot", "buy_value", "sell_value", "investor_type", "broker_category"])
                ff_data = pd.DataFrame(columns=["date", "foreign_buy_lot", "foreign_sell_lot", "foreign_net_lot", "foreign_buy_value", "foreign_sell_value", "foreign_net_value", "foreign_participation_percent"])
            else:
                # Early Hard Filter Check to save GoAPI tokens
                technical = TechnicalEngine(ohlcv).compute_all()
                technical["_data_length"] = len(ohlcv)
                hf_err = self.scoring_engine._check_hard_filters(technical, ohlcv, timeframe=interval, pure_technical=pure_technical)
                
                if hf_err is not None:
                    broker_data = pd.DataFrame(columns=["date", "broker_code", "buy_lot", "sell_lot", "net_lot", "buy_value", "sell_value", "investor_type", "broker_category"])
                    ff_data = pd.DataFrame(columns=["date", "foreign_buy_lot", "foreign_sell_lot", "foreign_net_lot", "foreign_buy_value", "foreign_sell_value", "foreign_net_value", "foreign_participation_percent"])
                else:
                    broker_data = self.data_provider.get_broker_summary(ticker, target_date=last_trading_day, days=20)
                    ff_data = self.data_provider.get_foreign_flow(ticker, target_date=last_trading_day, days=30, broker_df=broker_data)

            result = {
                "ticker": ticker,
                "ohlcv": ohlcv,
                "broker_data": broker_data,
                "ff_data": ff_data,
            }

            # Multi-TF: fetch daily trend if we're in intraday mode
            if interval != "1d":
                result["daily_trend"] = self._fetch_daily_trend(ticker)

            return result
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

    async def _fetch_all_data_parallel(self, tickers: List[str], interval: str, period_days: int, pure_technical: bool = False) -> List[Dict]:
        """Fetch data for all tickers in parallel using ThreadPoolExecutor."""
        loop = asyncio.get_event_loop()
        sem = asyncio.Semaphore(10)

        async def fetch_bounded(t):
            async with sem:
                return await loop.run_in_executor(self._executor, self._fetch_stock_data, t, interval, period_days, pure_technical)

        tasks = [fetch_bounded(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Parallel fetch exception: {r}")
            elif isinstance(r, dict) and "error" not in r:
                valid_results.append(r)
            elif isinstance(r, dict) and "error" in r:
                logger.warning(f"[{r.get('ticker')}] Skipped: {r.get('error')}")

        return valid_results

    # ------------------------------------------------------------------ #
    #  Core: Scan Single Stock
    # ------------------------------------------------------------------ #
    async def scan_single(self, ticker: str, run_llm: bool = True, prefetched_data: Optional[Dict] = None, override_interval: Optional[str] = None, pure_technical: bool = False) -> Optional[SignalOutput]:
        """Scan a single stock and generate its signal using visual Strategy Agent."""
        stock_info = get_stock_by_ticker(ticker)
        if not stock_info:
            return None

        try:
            settings = get_settings()
            interval = override_interval if override_interval else settings.CHART_INTERVAL
            period_days = 365
            if interval in ["15m", "30m"]:
                period_days = 60
            elif interval in ["60m", "1h", "60"]:
                interval = "60m"
                period_days = 120

            # Use prefetched data if available (from parallel scan), otherwise fetch fresh
            if prefetched_data and prefetched_data.get("ticker") == ticker:
                ohlcv = prefetched_data["ohlcv"]
                broker_data = prefetched_data["broker_data"]
                ff_data = prefetched_data["ff_data"]
                daily_trend = prefetched_data.get("daily_trend", {})
            else:
                ohlcv = self.data_provider.get_ohlcv(ticker, period_days=period_days, interval=interval)
                if ohlcv.empty or len(ohlcv) < 30:
                    raise ValueError(f"Data tidak cukup atau tidak ditemukan untuk saham {ticker}.")

                # Verify volume for suspended stock check in fallback mode
                last_3_vol = ohlcv["volume"].tail(3).sum()
                if last_3_vol == 0:
                    raise ValueError(f"Saham {ticker} sedang suspen atau tidak likuid (volume 0).")

                last_date_val = ohlcv["date"].iloc[-1]
                if isinstance(last_date_val, datetime.date):
                    last_trading_day = last_date_val
                else:
                    last_trading_day = pd.to_datetime(last_date_val).date()

                if pure_technical:
                    broker_data = pd.DataFrame(columns=["date", "broker_code", "buy_lot", "sell_lot", "net_lot", "buy_value", "sell_value", "investor_type", "broker_category"])
                    ff_data = pd.DataFrame(columns=["date", "foreign_buy_lot", "foreign_sell_lot", "foreign_net_lot", "foreign_buy_value", "foreign_sell_value", "foreign_net_value", "foreign_participation_percent"])
                else:
                    # Early Hard Filter Check to save GoAPI tokens
                    technical = TechnicalEngine(ohlcv).compute_all()
                    technical["_data_length"] = len(ohlcv)
                    hf_err = self.scoring_engine._check_hard_filters(technical, ohlcv, timeframe=interval, pure_technical=pure_technical)
                    
                    if hf_err is not None:
                        logger.debug(f"[{ticker}] Early Hard Filter fail (scan_single): {hf_err} -> Skipping GoAPI")
                        broker_data = pd.DataFrame(columns=["date", "broker_code", "buy_lot", "sell_lot", "net_lot", "buy_value", "sell_value", "investor_type", "broker_category"])
                        ff_data = pd.DataFrame(columns=["date", "foreign_buy_lot", "foreign_sell_lot", "foreign_net_lot", "foreign_buy_value", "foreign_sell_value", "foreign_net_value", "foreign_participation_percent"])
                    else:
                        broker_data = self.data_provider.get_broker_summary(ticker, target_date=last_trading_day, days=20)
                        ff_data = self.data_provider.get_foreign_flow(ticker, target_date=last_trading_day, days=30, broker_df=broker_data)

                # Multi-TF for intraday
                daily_trend = {}
                if interval != "1d":
                    daily_trend = self._fetch_daily_trend(ticker)

            # Attempt to fetch IHSG data for sector correlation & Beta calculation
            try:
                ihsg_df = self.data_provider.get_ohlcv("^JKSE", period_days=period_days, interval=interval)
                if ihsg_df.empty or len(ihsg_df) < 10:
                    ihsg_df = None
            except Exception:
                ihsg_df = None

            technical = TechnicalEngine(ohlcv, ihsg_df=ihsg_df).compute_all()
            patterns = PatternEngine(ohlcv).detect_all()
            candles = CandleEngine(ohlcv).detect_all()
            
            if pure_technical:
                bandarmology = {}
                foreign_flow = {}
            else:
                bandarmology = BandarmologyEngine(broker_data).analyze()
                foreign_flow = ForeignFlowEngine(ff_data).analyze()
                
            gap_analysis = GapEngine(ohlcv).analyze()
            sector_correlation = SectorCorrelationEngine(ohlcv, ihsg_df).analyze()


            # Merge daily trend data into technical dict for scoring
            if daily_trend:
                technical.update(daily_trend)

            # Fetch IHSG regime before scoring so we can adjust the final score
            ihsg_regime = self.regime_engine.get_ihsg_regime()

            score_result = self.scoring_engine.score(
                ticker=ticker, technical=technical, pattern=patterns,
                candle=candles, bandarmology=bandarmology,
                foreign_flow=foreign_flow, ohlcv_df=ohlcv,
                timeframe=interval, gap_analysis=gap_analysis,
                sector_correlation=sector_correlation,
                ihsg_regime_dict=ihsg_regime,
                pure_technical=pure_technical,
            )

            if score_result.hard_filter_failed:
                logger.warning(f"{ticker} failed hard filter: {score_result.hard_filter_reason}")

            risk_levels = self.risk_engine.calculate_from_ohlcv(ohlcv, signal=score_result.signal)
            risk_dict = self.risk_engine.to_dict(risk_levels)

            news_summary = {}
            chart_path = ""

            if run_llm and not score_result.hard_filter_failed:
                try:
                    news_items = await self.news_engine.fetch_news(ticker, limit=3)
                    news_summary = self.news_engine.analyze_sentiment(news_items)
                except Exception as ne:
                    logger.warning(f"[{ticker}] News fetching failed: {ne}")

                try:
                    # Chart + LLM Decision
                    chart_path = ChartService.generate_chart(ticker, ohlcv)
                except Exception as ce:
                    logger.warning(f"[{ticker}] Chart generation failed: {ce}")

            strategy_result = {}
            if run_llm and chart_path:
                strategy_result = await self.llm_engine.run_strategy_agent(
                    ticker=ticker,
                    technical=technical,
                    pattern=patterns,
                    candle=candles,
                    bandarmology=bandarmology,
                    foreign_flow=foreign_flow,
                    risk_levels=risk_dict,
                    ihsg_regime=ihsg_regime,
                    image_path=chart_path,
                    pure_technical=pure_technical,
                )

            # Integrate Strategy Agent decision or Fallback
            if run_llm and strategy_result and "decision" in strategy_result:
                final_signal = strategy_result["decision"]
                final_confidence = int(strategy_result.get("confidence_score", 5))

                # AI Guard (Pagi & Siang): jika scoring deterministik menghasilkan BUY / STRONG BUY / WATCHLIST,
                # jangan biarkan AI vision membunuh sinyal menjadi AVOID atau SELL
                if score_result.signal in ("BUY", "STRONG BUY", "WATCHLIST") and final_signal in ("AVOID", "SELL"):
                    logger.info(
                        f"[{ticker}] AI Guard: LLM suggested {final_signal}, "
                        f"keeping deterministic signal {score_result.signal}"
                    )
                    final_signal = score_result.signal
                    final_confidence = max(final_confidence, score_result.confidence_score)

                conf_label = "MEDIUM"
                if final_confidence >= 8:
                    conf_label = "VERY HIGH"
                elif final_confidence >= 6:
                    conf_label = "HIGH CONVICTION"
                elif final_confidence <= 3:
                    conf_label = "LOW"

                # Synthesize cohesive analyst opinion narrative
                opinion_parts = []
                if strategy_result.get("chart_visual_analysis"):
                    opinion_parts.append(strategy_result["chart_visual_analysis"].strip())
                if strategy_result.get("indicators_cross_check"):
                    opinion_parts.append(strategy_result["indicators_cross_check"].strip())
                if strategy_result.get("final_reasoning"):
                    opinion_parts.append(strategy_result["final_reasoning"].strip())
                opinion = " ".join(opinion_parts) if opinion_parts else strategy_result.get("final_reasoning", "")
            elif run_llm:
                logger.warning(f"[{ticker}] Strategy Agent failed. Falling back to deterministic scoring.")
                final_signal = score_result.signal
                final_confidence = score_result.confidence_score
                conf_label = score_result.confidence_label
                opinion = await self.llm_engine.generate_opinion(
                    ticker=ticker, signal=score_result.signal,
                    confidence=score_result.confidence_score,
                    technical=technical, pattern=patterns, candle=candles,
                    bandarmology=bandarmology, foreign_flow=foreign_flow,
                    risk_levels=risk_dict, news=news_summary,
                )
            else:
                final_signal = score_result.signal
                final_confidence = score_result.confidence_score
                conf_label = score_result.confidence_label
                opinion = "Opini analis dilewati selama pemindaian penuh."

            # Recalculate risk levels based on final_signal to ensure consistency
            if final_signal != score_result.signal:
                logger.info(f"[{ticker}] Signal changed from {score_result.signal} to {final_signal}. Recalculating risk levels.")
                risk_levels = self.risk_engine.calculate_from_ohlcv(ohlcv, signal=final_signal)

            sig_output = SignalOutput(
                ticker=ticker, name=stock_info["name"], sector=stock_info["sector"],
                signal=final_signal, confidence_score=final_confidence,
                confidence_label=conf_label,
                raw_score=round(score_result.total_score, 2),
                entry_price=risk_levels.entry_price, tp1=risk_levels.tp1,
                tp2=risk_levels.tp2,
                tp3=risk_levels.tp3,
                stop_loss_atr=risk_levels.stop_loss_atr,
                stop_loss_moderate=risk_levels.stop_loss_moderate,
                stop_loss_conservative=risk_levels.stop_loss_conservative,
                risk_reward_ratio=risk_levels.risk_reward_ratio,
                technical_summary=technical, pattern_summary=patterns,
                candle_summary=candles, bandarmology_summary=bandarmology,
                foreign_flow_summary=foreign_flow, news_summary=news_summary,
                analyst_opinion=opinion, category_scores=score_result.category_scores,
                category_raw_scores=score_result.category_raw_scores,
                chart_path=chart_path,
                ihsg_regime=ihsg_regime,
                fib_levels=risk_levels.fib_levels,
                interval=interval,
                pure_technical=pure_technical,
                is_syariah=is_syariah_stock(ticker),
            )


            # Save to Database
            if run_llm:
                self._save_signal_to_db(sig_output)

            return sig_output
        except ValueError as ve:
            raise ve
        except Exception as e:
            logger.error(f"[{ticker}] Scan error: {e}", exc_info=True)
            return None

    def _save_signal_to_db(self, signal: SignalOutput):
        import sqlite3
        import os
        from app.config import get_settings
        import json
        settings = get_settings()

        db_url = settings.DATABASE_URL_SYNC
        db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "./idx_signal_bot.db"

        def default_serializer(obj):
            import numpy as np
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            if isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Dynamic migrations to ensure columns exist
            for col, col_type in [
                ("tp2", "FLOAT"),
                ("tp3", "FLOAT"),
                ("bandarmology_json", "JSON"),
                ("foreign_flow_json", "JSON"),
                ("category_raw_json", "JSON")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE signals ADD COLUMN {col} {col_type}")
                    conn.commit()
                except Exception:
                    pass

            cursor.execute("""
                INSERT INTO signals 
                (ticker, timeframe, signal, raw_score, confidence_score, confidence_label, 
                 entry_price, tp1, tp2, tp3, stop_loss_atr, stop_loss_moderate, stop_loss_conservative, 
                 technical_json, pattern_json, bandarmology_json, foreign_flow_json, category_raw_json, analyst_opinion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.ticker,
                signal.interval if signal.interval else settings.CHART_INTERVAL,
                signal.signal,
                signal.raw_score,
                signal.confidence_score,
                signal.confidence_label,
                signal.entry_price,
                signal.tp1,
                signal.tp2,
                signal.tp3,
                signal.stop_loss_atr,
                signal.stop_loss_moderate,
                signal.stop_loss_conservative,
                json.dumps(signal.technical_summary, default=default_serializer),
                json.dumps(signal.pattern_summary, default=default_serializer),
                json.dumps(signal.bandarmology_summary, default=default_serializer),
                json.dumps(signal.foreign_flow_summary, default=default_serializer),
                json.dumps(signal.category_raw_scores or {}, default=default_serializer),
                signal.analyst_opinion
            ))

            conn.commit()
            conn.close()
            logger.info(f"[{signal.ticker}] Saved AI Signal analysis to DB.")
        except Exception as e:
            logger.error(f"[{signal.ticker}] Failed to save signal to DB: {e}")

    # ------------------------------------------------------------------ #
    #  Parallel Full Scan
    # ------------------------------------------------------------------ #
    async def scan_all(self, top_n: Optional[int] = None, override_interval: Optional[str] = None, pure_technical: bool = False) -> List[SignalOutput]:
        """Scan all stocks in the universe with parallel data fetching.
        
        - In pure_technical mode: Only technical indicators are evaluated (Noon screener).
        - In DAY_TRADE_MODE: Uses the FULL IDX universe (all stocks except FCA & delisted).
        - In normal mode: Uses the curated DEFAULT_STOCK_UNIVERSE (~160 stocks).
        """
        settings = get_settings()

        # Choose universe based on mode
        if settings.DAY_TRADE_MODE:
            logger.info("[scan_all] DAY_TRADE_MODE ON — Loading FULL IDX universe (excluding FCA & delisted)...")
            goapi_keys = [
                k.strip() for k in (settings.GOAPI_KEY or "").split(",") if k.strip()
            ]
            universe = get_full_idx_universe(goapi_keys=goapi_keys or None, exclude_fca=False, min_price=10)
            if not universe:
                logger.warning("[scan_all] Full IDX universe is empty! Falling back to default universe.")
                universe = get_stock_universe()
            logger.info(f"[scan_all] Intraday universe loaded: {len(universe)} stocks")
        else:
            universe = get_stock_universe()
            logger.info(f"[scan_all] Standard universe: {len(universe)} stocks")

        tickers = [s["ticker"] for s in universe]

        interval = override_interval if override_interval else settings.CHART_INTERVAL
        period_days = 365
        if interval in ["15m", "30m"]:
            period_days = 60
        elif interval in ["60m", "1h", "60"]:
            interval = "60m"
            period_days = 120

        # ========== PHASE 1: Parallel data fetch ==========
        mode_text = "PURE TEKNIKAL" if pure_technical else "FULL (Teknikal + Bandar + Asing)"
        logger.info(f"[scan_all] Phase 1: Fetching data for {len(tickers)} stocks in parallel [{mode_text}]...")
        all_data = await self._fetch_all_data_parallel(tickers, interval, period_days, pure_technical=pure_technical)
        logger.info(f"[scan_all] Phase 1 complete: {len(all_data)} stocks fetched successfully.")

        # ========== PHASE 2: Score all (deterministic, fast) ==========
        # Reset filter funnel stats sebelum batch baru dimulai
        self.scoring_engine.reset_scan_stats()

        results = []
        for stock_data in all_data:
            try:
                signal = await self.scan_single(
                    stock_data["ticker"],
                    run_llm=False,
                    prefetched_data=stock_data,
                    override_interval=override_interval,
                    pure_technical=pure_technical,
                )
                if signal:
                    results.append(signal)
            except Exception as e:
                logger.error(f"Error scanning {stock_data['ticker']}: {e}")

        # ── Log filter funnel summary ──
        funnel = self.scoring_engine.get_scan_stats()
        logger.info(funnel.to_summary_text())

        # Sort by raw score descending
        results.sort(key=lambda x: x.raw_score, reverse=True)

        # Only keep actionable bullish signals — filter out AVOID & SELL
        # Pagi & Siang scan: HANYA WATCHLIST, BUY, STRONG BUY
        BULLISH_SIGNALS = {"STRONG BUY", "BUY", "WATCHLIST"}
        bullish_results = [r for r in results if r.signal in BULLISH_SIGNALS]
        
        if len(bullish_results) > 0:
            logger.info(f"[scan_all] {len(bullish_results)} stocks with bullish signal after filtering AVOID/SELL.")
            results = bullish_results
        else:
            logger.warning(
                "[scan_all] ⚠️  ZERO bullish signals this scan! "
                f"Hard filter gugur {funnel.failed_hard_filter}/{funnel.total_stocks} saham. "
                "Tidak ada saham yang memenuhi kriteria WATCHLIST/BUY/STRONG BUY."
            )
            # Return empty list — scheduler akan kirim pesan "tidak ada saham yang memenuhi kriteria"
            return []

        # Hapus batasan kuota Top 10 dan maksimal 3 per sektor:
        # Seluruh kandidat bullish hasil scoring Fase 2 diteruskan ke Fase 3 (LLM Strategy Agent)
        if top_n is not None:
            top_candidates = results[:top_n]
            logger.info(f"[scan_all] Phase 2 complete. Taking top {len(top_candidates)} as LLM candidates (top_n={top_n}).")
        else:
            top_candidates = results
            logger.info(f"[scan_all] Phase 2 complete. Taking all {len(top_candidates)} bullish stocks as LLM candidates (unlimited quota, no sector limit).")

        # ========== PHASE 3: LLM analysis (parallel with semaphore) ==========
        sem = asyncio.Semaphore(2)  # Max 2 concurrent LLM requests to respect Gemini 15 RPM limit
        prefetched_map = {d["ticker"]: d for d in all_data if isinstance(d, dict) and "ticker" in d}

        async def process_cand(cand):
            async with sem:
                try:
                    pref = prefetched_map.get(cand.ticker)
                    final_sig = await self.scan_single(
                        cand.ticker,
                        run_llm=True,
                        prefetched_data=pref,
                        override_interval=override_interval,
                        pure_technical=pure_technical,
                    )
                    await asyncio.sleep(4)
                    if final_sig:
                        return final_sig
                    else:
                        # LLM gagal: gunakan cand dengan opini fallback yang jelas
                        logger.warning(f"[{cand.ticker}] LLM returned None, using deterministic fallback.")
                        cand.analyst_opinion = (
                            "[FALLBACK — Opini AI tidak tersedia. Analisis berdasarkan scoring deterministic.]\n"
                            + (cand.analyst_opinion or "")
                        )
                        return cand
                except Exception as e:
                    logger.error(f"Error executing LLM scan for candidate {cand.ticker}: {e}")
                    cand.analyst_opinion = f"[FALLBACK] LLM error: {str(e)[:100]}"
                    return cand

        tasks = [process_cand(cand) for cand in top_candidates]
        all_results = await asyncio.gather(*tasks)

        # Filter out any Nones, sort by score again, trim to top_n
        final_signals = [s for s in all_results if s is not None]
        final_signals.sort(key=lambda x: x.raw_score, reverse=True)

        # Deduplication by ticker: pastikan setiap saham hanya muncul sekali
        seen_tickers = set()
        deduped_signals = []
        for sig in final_signals:
            if sig.ticker not in seen_tickers:
                deduped_signals.append(sig)
                seen_tickers.add(sig.ticker)
        final_signals = deduped_signals[:top_n] if top_n else deduped_signals

        logger.info(f"[scan_all] Final: {len(final_signals)} signals akan dikirim ke Telegram (setelah dedup).")
        return final_signals

    def _diversify_by_sector(self, results: list, top_n: int, max_per_sector: int = 3) -> list:
        """
        Pilih top_n sinyal dengan diversifikasi sektor.
        Max max_per_sector saham dari sektor yang sama.
        Sisanya diisi dari sektor lain.
        """
        sector_count: Dict[str, int] = {}
        diversified = []

        for r in results:  # Sudah diurutkan by score desc
            sector = getattr(r, "sector", "Unknown") or "Unknown"
            count = sector_count.get(sector, 0)
            if count < max_per_sector:
                diversified.append(r)
                sector_count[sector] = count + 1
            if len(diversified) >= top_n:
                break

        # Jika kurang dari top_n setelah diversifikasi, tambah sisanya
        if len(diversified) < top_n:
            existing_tickers = {r.ticker for r in diversified}
            for r in results:
                if r.ticker not in existing_tickers:
                    diversified.append(r)
                    if len(diversified) >= top_n:
                        break

        return diversified

    async def scan_sector(self, sector: str, top_n: int = 5) -> List[SignalOutput]:
        """Scan all stocks in a specific sector."""
        from services.stock_universe_service import get_stocks_by_sector
        stocks = get_stocks_by_sector(sector)
        results = []
        for stock in stocks:
            try:
                signal = await self.scan_single(stock["ticker"], run_llm=False)
                if signal:
                    results.append(signal)
            except Exception as e:
                logger.error(f"Error scanning {stock['ticker']}: {e}")

        results.sort(key=lambda x: x.raw_score, reverse=True)
        top_candidates = results[:top_n] if top_n else results

        sem = asyncio.Semaphore(3)

        async def process_cand(cand):
            async with sem:
                try:
                    final_sig = await self.scan_single(cand.ticker, run_llm=True)
                    return final_sig if final_sig else cand
                except Exception as e:
                    logger.error(f"Error executing LLM scan for candidate {cand.ticker}: {e}")
                    return cand

        tasks = [process_cand(cand) for cand in top_candidates]
        final_signals = await asyncio.gather(*tasks)

        return final_signals

    def signal_to_dict(self, signal: SignalOutput) -> Dict[str, Any]:
        """Convert SignalOutput to JSON-serializable dict."""
        return {
            "ticker": signal.ticker, "name": signal.name, "sector": signal.sector,
            "signal": signal.signal, "confidence_score": signal.confidence_score,
            "confidence_label": signal.confidence_label, "raw_score": signal.raw_score,
            "entry_price": signal.entry_price, "tp1": signal.tp1,
            "tp2": signal.tp2, "tp3": signal.tp3,
            "stop_loss_atr": signal.stop_loss_atr,
            "stop_loss_moderate": signal.stop_loss_moderate,
            "stop_loss_conservative": signal.stop_loss_conservative,
            "risk_reward_ratio": signal.risk_reward_ratio,
            "technical": signal.technical_summary, "patterns": signal.pattern_summary,
            "candles": signal.candle_summary, "bandarmology": signal.bandarmology_summary,
            "foreign_flow": signal.foreign_flow_summary, "news": signal.news_summary,
            "analyst_opinion": signal.analyst_opinion,
            "category_scores": signal.category_scores,
            "chart_path": signal.chart_path,
            "ihsg_regime": signal.ihsg_regime,
            "fib_levels": signal.fib_levels,
            "interval": signal.interval,
            "pure_technical": getattr(signal, "pure_technical", False),
            "is_syariah": getattr(signal, "is_syariah", None) if getattr(signal, "is_syariah", None) is not None else is_syariah_stock(signal.ticker),
            "beta": signal.technical_summary.get("beta", 1.0),
            "beta_label": signal.technical_summary.get("beta_label", "Moderate"),
            "volatility": signal.technical_summary.get("volatility", 0.0),
        }

