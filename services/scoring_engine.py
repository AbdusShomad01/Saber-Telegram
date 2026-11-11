"""
IDX AI Signal Bot - Scoring Engine (CORE)
The deterministic decision maker. No LLM involvement.

Aggregates scores from 8 engines:
- Trend & Momentum       (21 pts)
- Volume & Liquidity     (20 pts)
- Pattern & Candle       (10 pts)
- Gap Analysis           (5 pts)
- Sector Correlation     (4 pts)
- Support & Resistance   (15 pts)
- Bandarmology           (15 pts) — WR-based broker confidence (Broker Summary)
- Foreign Flow           (10 pts)
Total: 100 points
(Analisis Teknikal: 75%, Broker Summary: 15%, Foreign Flow: 10%)

Bandarmology WR-Based Scoring (dari dataset 458 resolved signals):
- Elite buyers (AK/RX/DP/NI/YP) as #1 buyer → confidence +3 (WR 97-100%)
- Good buyers (BK/CC/BB) as #1 buyer → confidence +2 (WR 83-88%)
- Foreign broker in top 3 → confidence +2 (asing WR 93.5%)
- Winning combo match → confidence +2 (100% WR)
- Danger buyers (XL/MG/PD/CP) as #1 buyer → confidence -2 (WR 46-54%)
- Toxic sellers (KI/YP/AZ/DX) as #1 seller → confidence -2 (WR 0-33%)
- MG in top 3 buyers → extra penalty -1 (WR 46.2%)

Signal mapping:
  90 - 100 → STRONG BUY (Confidence 9-10)
  75 - 89  → BUY (Confidence 7-8)
  55 - 74  → WATCHLIST (Confidence 5-6)
  < 55     → AVOID (Confidence 1-4)
"""

import logging
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import math

from app.config import get_settings
from services.regime_engine import apply_ihsg_regime_adjustment

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache threshold config agar tidak baca file tiap scoring
_THRESHOLD_CACHE: Dict[str, Dict[str, float]] = {}
_THRESHOLD_CACHE_TS: float = 0  # Unix timestamp last load


def _load_adaptive_thresholds(timeframe: str) -> Dict[str, float]:
    """
    Baca threshold dari threshold_config.json (dihasilkan oleh job_adaptive_threshold).
    Di-cache selama 1 jam agar tidak baca disk terus-menerus.
    Fallback ke default jika file tidak ada atau format salah.
    """
    import time
    global _THRESHOLD_CACHE, _THRESHOLD_CACHE_TS

    now = time.time()
    # Cache valid selama 60 menit
    if timeframe in _THRESHOLD_CACHE and (now - _THRESHOLD_CACHE_TS) < 3600:
        return _THRESHOLD_CACHE[timeframe]

    defaults = {"buy_threshold": 75.0, "strong_buy_threshold": 90.0}
    config_path = "./threshold_config.json"
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = json.load(f)
            
            tf_data = data.get(timeframe, data) # fallback to root for backwards compatibility
            loaded = {
                "buy_threshold": float(tf_data.get("buy_threshold", 75.0)),
                "strong_buy_threshold": float(tf_data.get("strong_buy_threshold", 90.0)),
            }
            # Validasi range threshold yang masuk akal
            if 65 <= loaded["buy_threshold"] <= 85 and 85 <= loaded["strong_buy_threshold"] <= 95:
                _THRESHOLD_CACHE[timeframe] = loaded
                _THRESHOLD_CACHE_TS = now
                logger.debug(f"[ScoringEngine] Adaptive thresholds loaded for {timeframe}: BUY={loaded['buy_threshold']}, STRONG_BUY={loaded['strong_buy_threshold']}")
                return loaded
    except Exception as e:
        logger.warning(f"[ScoringEngine] Failed to load threshold_config.json: {e}")

    _THRESHOLD_CACHE[timeframe] = defaults
    _THRESHOLD_CACHE_TS = now
    return defaults


@dataclass
class RuleResult:
    """Result of a single scoring rule."""
    name: str
    score: float
    max_score: float
    category: str
    reason: str


@dataclass
class ScoringResult:
    """Complete scoring result for a stock."""
    ticker: str
    total_score: float
    max_possible: float = 100.0
    signal: str = "AVOID"
    confidence_score: int = 1
    confidence_label: str = "LOW"
    rule_results: List[RuleResult] = field(default_factory=list)
    category_scores: Dict[str, float] = field(default_factory=dict)
    category_raw_scores: Dict[str, float] = field(default_factory=dict)
    hard_filter_failed: bool = False
    hard_filter_reason: str = ""
    hard_filter_category: str = ""  # "adx", "volume", "value", "volume_and_value", "atr"
    data_mode: str = "free"            # "free" or "premium"
    data_warning: str = ""             # Warning message if data is unverified


@dataclass
class HardFilterResult:
    """
    Structured result dari pengecekan satu Hard Filter.
    passed=True  → saham LOLOS, lanjut ke filter berikutnya.
    passed=False → saham GUGUR, sertakan reason & category untuk tracking.
    """
    passed: bool
    reason: str = ""
    category: str = ""  # "adx_warmup_skip" | "adx" | "volume" | "value" | "volume_and_value" | "atr"


@dataclass
class FilterFunnelStats:
    """
    Statistik pipeline filter untuk satu batch scan.
    Di-reset tiap scan_all() via ScoringEngine.reset_scan_stats().
    Digunakan untuk diagnosa bottle-neck dan alert "0 sinyal".
    """
    total_stocks: int = 0
    passed_hard_filter: int = 0
    failed_hard_filter: int = 0
    passed_to_signal: int = 0       # STRONG BUY + BUY + WATCHLIST
    # -- Breakdown Hard Filter --
    gugur_suspended: int = 0        # Sedang suspen (volume 0 / data berhenti)
    gugur_min_price: int = 0        # Harga <= Rp 10 (Daily) / Rp 50 (Intraday)
    gugur_prev_day_surge: int = 0   # Naik > batas kemarin (Daily > 20% / Intraday > 15%)
    gugur_ara: int = 0              # Sudah atau hampir menyentuh ARA
    gugur_adx: int = 0              # ADX < 12 (Daily)
    gugur_atr: int = 0              # ATR > batas (Daily > 10% / Intraday > 7%)
    gugur_volume: int = 0           # hanya gagal volume lot
    gugur_value: int = 0            # hanya gagal value IDR
    gugur_volume_dan_value: int = 0 # gagal keduanya
    # -- Breakdown sinyal akhir --
    strong_buy_count: int = 0
    buy_count: int = 0
    watchlist_count: int = 0
    avoid_count: int = 0
    sell_count: int = 0

    def to_summary_text(self) -> str:
        """Teks ringkasan untuk log / Telegram."""
        hf_pct  = (self.passed_hard_filter / self.total_stocks * 100) if self.total_stocks > 0 else 0
        sig_pct = (self.passed_to_signal / self.passed_hard_filter * 100) if self.passed_hard_filter > 0 else 0
        return (
            "\n══════════════════════════════════════\n"
            "📊  FILTER FUNNEL SUMMARY\n"
            "══════════════════════════════════════\n"
            f"  Total saham diproses : {self.total_stocks}\n"
            f"  Lolos Hard Filter    : {self.passed_hard_filter} ({hf_pct:.1f}%)\n"
            f"  Gugur Hard Filter    : {self.failed_hard_filter}\n"
            f"  ├─ Sedang suspen     : {self.gugur_suspended}\n"
            f"  ├─ Harga di bawah min: {self.gugur_min_price}\n"
            f"  ├─ Naik > 20% Kemarin: {self.gugur_prev_day_surge}\n"
            f"  ├─ Sudah/Hampir ARA  : {self.gugur_ara}\n"
            f"  ├─ ADX < 12          : {self.gugur_adx}\n"
            f"  ├─ ATR > 10%         : {self.gugur_atr}\n"
            f"  ├─ Volume kurang     : {self.gugur_volume}\n"
            f"  ├─ Value kurang      : {self.gugur_value}\n"
            f"  └─ Volume & Value    : {self.gugur_volume_dan_value}\n"
            f"  Lolos ke Sinyal      : {self.passed_to_signal} ({sig_pct:.1f}%)\n"
            f"  ├─ STRONG BUY : {self.strong_buy_count}\n"
            f"  ├─ BUY        : {self.buy_count}\n"
            f"  ├─ WATCHLIST  : {self.watchlist_count}\n"
            f"  ├─ AVOID      : {self.avoid_count}\n"
            f"  └─ SELL       : {self.sell_count}\n"
            "══════════════════════════════════════"
        )


class ScoringEngine:
    """
    Deterministic scoring engine — 8 kategori, total WAJIB 100 poin.
    NO AI/LLM involvement — decisions are purely rule-based.

    DATA CONFIDENCE MODE:
    - 'free'    : Bandarmology=5, ForeignFlow=5  (data GoAPI unverified)
    - 'premium' : Bandarmology=20, ForeignFlow=15 (data terverifikasi real)

    Mode dipilih otomatis berdasarkan flag `is_real_data` dari masing-masing engine.
    Jika KEDUANYA is_real_data=True → premium mode.
    Jika salah satu atau keduanya False → free mode.

    CATATAN VALIDITAS INDIKATOR (window 60 hari):
    - EMA200 TIDAK DIPAKAI — butuh 200+ hari untuk konverge
    - MACD dianggap reliable mulai hari ke-35 dalam window
    - ADX  dianggap reliable mulai hari ke-28 dalam window
    - Pola chart panjang (Cup&Handle, H&S, Double Top/Bottom, Triangle) DIHAPUS
    """

    CATEGORIES = {
        "trend_momentum":    21,
        "volume_liquidity":  20,
        "pattern":           10,
        "gap_analysis":       5,
        "sector_correlation": 4,
        "support_resistance": 15,
        "bandarmology":       15,
        "foreign_flow":       10,
    }

    # Bobot khusus untuk Screener Siang (Noon Intraday) — PURE TEKNIKAL (Tanpa Bandarmologi & Foreign Flow)
    # Total WAJIB 100 poin murni dari analisis teknikal, momentum, pola, dan volume
    CATEGORIES_PURE_TECHNICAL = {
        "trend_momentum":    30,
        "volume_liquidity":  25,
        "pattern":           15,
        "gap_analysis":       5,
        "sector_correlation": 5,
        "support_resistance": 20,
        "bandarmology":       0,
        "foreign_flow":       0,
    }

    def __init__(self):
        self._scan_stats = FilterFunnelStats()  # accumulates during scan_all()

    def _get_categories(self, data_mode: str, pure_technical: bool = False) -> Dict[str, float]:
        """Return the category weight dict."""
        if pure_technical or data_mode == "pure_technical":
            return {k: float(v) for k, v in self.CATEGORIES_PURE_TECHNICAL.items()}
        return {k: float(v) for k, v in self.CATEGORIES.items()}

    # ------------------------------------------------------------------ #
    #  Filter Funnel Stats
    # ------------------------------------------------------------------ #

    def reset_scan_stats(self) -> None:
        """Reset filter funnel stats. Panggil di awal setiap scan_all()."""
        self._scan_stats = FilterFunnelStats()

    def get_scan_stats(self) -> FilterFunnelStats:
        """Ambil statistik filter funnel hasil scan terakhir."""
        return self._scan_stats

    def _resolve_data_mode(self, bandarmology: Dict, foreign_flow: Dict) -> str:
        """
        Mode data standard.
        """
        return "standard"

    def score(
        self,
        ticker: str,
        technical: Dict[str, Any],
        pattern: Dict[str, Any],
        candle: Dict[str, Any],
        bandarmology: Dict[str, Any],
        foreign_flow: Dict[str, Any],
        ohlcv_df=None,
        timeframe: str = "1d",
        gap_analysis: Optional[Dict[str, Any]] = None,
        sector_correlation: Optional[Dict[str, Any]] = None,
        ihsg_regime_dict: Optional[Dict[str, Any]] = None,
        pure_technical: bool = False,
        latest_market_date=None,
    ) -> ScoringResult:
        """
        Score a stock based on analysis engines.
        Jika pure_technical=True (Screener Siang), bobot bandarmology dan foreign flow dinonaktifkan,
        skor 100% dihitung dari indikator teknikal.
        Total skor selalu dalam range [0, 100].
        """
        result = ScoringResult(ticker=ticker, total_score=0)
        all_rules: List[RuleResult] = []

        # Resolve data mode (pure_technical vs standard)
        data_mode = "pure_technical" if pure_technical else self._resolve_data_mode(bandarmology, foreign_flow)
        categories = self._get_categories(data_mode, pure_technical=pure_technical)
        result.data_mode = data_mode

        # Warning flag untuk Telegram jika data tidak terverifikasi
        if data_mode == "free":
            result.data_warning = (
                "⚠️ Skor Bandarmology & Foreign Flow menggunakan bobot rendah "
                "(data broker/asing belum terverifikasi)"
            )

        # ============================================================ #
        #  HARD FILTERS
        # ============================================================ #
        # data_len dibutuhkan oleh ADX warm-up check, inject dulu
        data_len = len(ohlcv_df) if ohlcv_df is not None else 60
        technical["_data_length"] = data_len

        # Track total stocks per scan
        self._scan_stats.total_stocks += 1

        market_ref_date = latest_market_date if latest_market_date is not None else technical.get("_latest_market_date")
        hf_result = self._run_hard_filters(
            technical, ohlcv_df, data_len,
            timeframe=timeframe, pure_technical=pure_technical,
            latest_market_date=market_ref_date,
        )
        if not hf_result.passed:
            result.hard_filter_failed   = True
            result.hard_filter_reason   = hf_result.reason
            result.hard_filter_category = hf_result.category
            # Track breakdown kegagalan
            self._scan_stats.failed_hard_filter += 1
            cat = hf_result.category
            if cat == "suspended":          self._scan_stats.gugur_suspended += 1
            elif cat == "min_price":        self._scan_stats.gugur_min_price += 1
            elif cat == "prev_day_surge":   self._scan_stats.gugur_prev_day_surge += 1
            elif cat == "ara_limit":        self._scan_stats.gugur_ara += 1
            elif cat == "adx":              self._scan_stats.gugur_adx += 1
            elif cat == "atr":             self._scan_stats.gugur_atr += 1
            elif cat == "volume":          self._scan_stats.gugur_volume += 1
            elif cat == "value":           self._scan_stats.gugur_value += 1
            elif cat == "volume_and_value": self._scan_stats.gugur_volume_dan_value += 1
        else:
            self._scan_stats.passed_hard_filter += 1

        # ============================================================ #
        #  1. TREND & MOMENTUM
        # ============================================================ #
        all_rules.extend(self._score_trend_momentum(technical))

        # ============================================================ #
        #  2. VOLUME & LIKUIDITAS
        # ============================================================ #
        all_rules.extend(self._score_volume_liquidity(technical, ohlcv_df))

        # ============================================================ #
        #  3. POLA CHART & CANDLE (hanya Flag + Candle 1-3 bar)
        # ============================================================ #
        all_rules.extend(self._score_patterns(pattern, candle))

        # ============================================================ #
        #  4. GAP ANALYSIS
        # ============================================================ #
        all_rules.extend(self._score_gap_analysis(gap_analysis or {}))

        # ============================================================ #
        #  5. SECTOR / MARKET CORRELATION
        # ============================================================ #
        all_rules.extend(self._score_sector_correlation(sector_correlation or {}))

        # ============================================================ #
        #  6. SUPPORT / RESISTANCE + RISK-REWARD
        # ============================================================ #
        all_rules.extend(self._score_support_resistance(technical, ohlcv_df))
        all_rules.extend(self._score_risk_reward(technical, ohlcv_df))

        # ============================================================ #
        #  7. BANDARMOLOGY (Hanya jika BUKAN pure_technical)
        # ============================================================ #
        if not pure_technical:
            all_rules.extend(self._score_bandarmology(bandarmology))

        # ============================================================ #
        #  8. FOREIGN FLOW (Hanya jika BUKAN pure_technical)
        # ============================================================ #
        if not pure_technical:
            all_rules.extend(self._score_foreign_flow(foreign_flow))

        # ============================================================ #
        #  AGGREGATE — clamp setiap kategori ke max bobotnya
        # ============================================================ #
        result.rule_results = all_rules

        cat_scores = {}
        cat_raw = {}
        for cat, max_pts in categories.items():
            if max_pts == 0:
                cat_scores[cat] = 0.0
                cat_raw[cat] = 0.0
                continue
            cat_total = sum(r.score for r in all_rules if r.category == cat)
            cat_raw[cat]    = cat_total
            cat_scores[cat] = max(0.0, min(cat_total, max_pts))

        result.category_scores      = cat_scores
        result.category_raw_scores  = cat_raw
        result.total_score          = sum(cat_scores.values())

        # ============================================================ #
        #  MULTI-TIMEFRAME BONUS/PENALTY (if daily trend data available)
        # ============================================================ #
        daily_trend = technical.get("daily_trend_bias")
        if daily_trend and settings.DAY_TRADE_MODE:
            current_signal = self._map_signal(result.total_score, timeframe, pure_technical=pure_technical)
            is_bullish_signal = current_signal in ("STRONG BUY", "BUY", "WATCHLIST")

            if daily_trend == "bullish" and is_bullish_signal:
                # Daily trend confirms intraday signal — bonus
                mtf_bonus = 8
                result.total_score += mtf_bonus
                result.rule_results.append(
                    RuleResult("MTF Daily Bullish Alignment", mtf_bonus, 8, "trend_momentum",
                               "Daily trend bullish confirms intraday signal")
                )
                logger.info(f"[{ticker}] MTF bonus +{mtf_bonus}: daily BULLISH aligns with intraday.")
            elif daily_trend == "bearish" and is_bullish_signal:
                # Daily trend contradicts intraday signal — penalty
                mtf_penalty = -10
                result.total_score += mtf_penalty
                result.rule_results.append(
                    RuleResult("MTF Daily Bearish Conflict", mtf_penalty, 10, "trend_momentum",
                               "WARNING: Daily trend bearish conflicts with intraday bullish signal")
                )
                logger.info(f"[{ticker}] MTF penalty {mtf_penalty}: daily BEARISH conflicts with intraday.")
            elif daily_trend == "sideways":
                # Neutral — no adjustment
                pass

        # ============================================================ #
        #  IHSG REGIME CONTEXT (Informasi pasar — skor murni tanpa penyesuaian)
        # ============================================================ #
        raw_score = max(0.0, min(result.total_score, 100.0))
        
        regime_str = "sideways"
        if ihsg_regime_dict and "regime_raw" in ihsg_regime_dict:
            regime_str = ihsg_regime_dict["regime_raw"]
            
        is_intraday = (timeframe in ["15m", "60m", "1h", "60"]) or pure_technical
        final_score = apply_ihsg_regime_adjustment(raw_score, regime_str, is_intraday=is_intraday)
        
        # Log jika ada penyesuaian (default: tidak ada modifikasi skor)
        if final_score != raw_score:
            diff = final_score - raw_score
            result.rule_results.append(
                RuleResult("IHSG Regime Adjustment", diff, 0, "regime", 
                           f"Market {regime_str.upper()}: score adjusted by {diff:+.1f} pts")
            )
            logger.info(f"[{ticker}] Regime Adjustment: {raw_score:.1f} -> {final_score:.1f} ({regime_str.upper()})")
            
        result.total_score = final_score

        # Map to signal
        result.signal = self._map_signal(result.total_score, timeframe, pure_technical=pure_technical)
        result.confidence_score = self._map_confidence_score(result.total_score, pure_technical=pure_technical)
        result.confidence_label = self._map_confidence_label(result.confidence_score)

        # Volume Confirmation wajib untuk STRONG BUY
        # Sinyal hanya naik ke STRONG BUY jika ada volume breakout nyata (>= 1.3x avg)
        # Tanpa konfirmasi volume, downgrade ke BUY untuk menghindari false breakout
        if result.signal == "STRONG BUY":
            vol_ratio = technical.get("volume_ratio", 0)
            vol_breakout = technical.get("volume_breakout", False)
            if not vol_breakout and vol_ratio < 1.3:
                result.signal = "BUY"
                result.confidence_score = min(result.confidence_score, 7)
                result.confidence_label = "HIGH CONVICTION"
                logger.info(
                    f"[{ticker}] STRONG BUY downgraded to BUY: "
                    f"no volume confirmation (ratio={vol_ratio:.1f}x, breakout={vol_breakout})"
                )

        # Force verdict to AVOID if hard filters failed
        if result.hard_filter_failed:
            result.signal = "AVOID"
            result.confidence_score = 1
            result.confidence_label = "FILTERED"

        # Track signal breakdown in funnel stats
        sig = result.signal
        if sig == "STRONG BUY":
            self._scan_stats.strong_buy_count += 1
            self._scan_stats.passed_to_signal += 1
        elif sig == "BUY":
            self._scan_stats.buy_count += 1
            self._scan_stats.passed_to_signal += 1
        elif sig == "WATCHLIST":
            self._scan_stats.watchlist_count += 1
            self._scan_stats.passed_to_signal += 1
        elif sig == "AVOID":
            self._scan_stats.avoid_count += 1
        elif sig == "SELL":
            self._scan_stats.sell_count += 1

        logger.info(
            f"[{ticker}] Score: {result.total_score:.1f}/100 → "
            f"{result.signal} (Confidence: {result.confidence_score}/10)"
            f"{' [MTF: ' + daily_trend.upper() + ']' if daily_trend else ''}"
        )

        return result

    # ------------------------------------------------------------------ #
    #  Hard Filters — refactored (Masalah 1, 2, 4)
    # ------------------------------------------------------------------ #

    ADX_HARD_FILTER_THRESHOLD     = 12              # min ADX 12 untuk daily (pagi hari)
    ADX_WARMUP_DAYS               = 28              # Wilder's smoothing butuh ~28 bar untuk stabil
    DAILY_LIQUIDITY_WINDOW_DAYS   = 5               # rata-rata 5 hari untuk volume & value daily
    INTRADAY_LIQUIDITY_WINDOW_BARS = 20             # rata-rata 20 bar untuk volume & value intraday
    MIN_AVG_VOLUME_LOT            = 200_000         # 200 ribu lembar/hari (avg 5 hari) untuk daily
    MIN_AVG_VALUE_IDR             = 1_000_000_000   # Rp 1 miliar/hari (avg 5 hari) untuk daily
    MIN_AVG_VOLUME_LOT_INTRADAY   = 200_000         # 200 ribu lembar (~2.000 lot) untuk intraday
    MIN_AVG_VALUE_IDR_INTRADAY    = 2_000_000_000   # Rp 2 miliar untuk intraday
    MAX_ATR_PCT                   = 10.0            # % untuk daily (pagi hari)
    MAX_ATR_PCT_INTRADAY          = 7.0             # % untuk intraday
    MAX_PREV_DAY_GAIN_PCT         = 20.0            # % untuk daily (saham naik > 20% kemarin gugur)
    MAX_PREV_DAY_GAIN_PCT_INTRADAY = 15.0           # % untuk intraday
    MIN_PRICE                     = 10.0            # Rp (saham > 10 tetap dimasukkan, <= 10 dikeluarkan)
    MIN_PRICE_INTRADAY            = 50.0            # Rp (intraday: saham <= 50 dikeluarkan karena risiko FCA / illiquid)

    @staticmethod
    def _is_intraday(timeframe: str = "1d", pure_technical: bool = False) -> bool:
        """Tentukan apakah scan berjalan di mode intraday/pure_technical (bukan scan pagi daily 1d)."""
        return (timeframe in ["15m", "60m", "1h", "60"]) or pure_technical

    def _check_suspended_filter(self, ohlcv_df, timeframe: str = "1d", latest_market_date=None) -> HardFilterResult:
        """
        Deteksi dan gugurkan saham yang sedang suspen (pagi 1d maupun siang intraday):
        1. Tanggal perdagangan terakhir tertinggal dari IHSG (^JKSE) / pasar -> suspen/berhenti diperdagangkan.
        2. Volume 3 bar terakhir == 0 -> suspen/tidur.
        3. Volume bar terakhir (daily 1d) atau total volume sesi terakhir (intraday) == 0 -> baru suspen.
        """
        if settings.DATA_PROVIDER == "mock" or ohlcv_df is None or len(ohlcv_df) == 0:
            return HardFilterResult(passed=True)

        try:
            has_date = "date" in ohlcv_df.columns
            if latest_market_date is not None and has_date:
                stock_last_date = pd.to_datetime(ohlcv_df["date"].iloc[-1]).date()
                ref_date = (
                    latest_market_date.date()
                    if hasattr(latest_market_date, "date")
                    else pd.to_datetime(latest_market_date).date()
                )
                if stock_last_date < ref_date:
                    return HardFilterResult(
                        passed=False,
                        category="suspended",
                        reason=f"Saham suspen / tidak ada transaksi sejak {stock_last_date} (pasar {ref_date})",
                    )

            if "volume" in ohlcv_df.columns:
                if float(ohlcv_df["volume"].tail(3).sum() or 0) <= 0:
                    return HardFilterResult(
                        passed=False,
                        category="suspended",
                        reason="Saham suspen atau tidak likuid (volume 3 bar terakhir = 0)",
                    )

                is_intraday = self._is_intraday(timeframe)
                if not is_intraday:
                    last_vol = float(ohlcv_df["volume"].iloc[-1] or 0)
                    if last_vol <= 0:
                        return HardFilterResult(
                            passed=False,
                            category="suspended",
                            reason="Saham suspen / tidak ada transaksi pada hari bursa terakhir (volume = 0)",
                        )
                else:
                    if has_date:
                        dates = pd.to_datetime(ohlcv_df["date"]).dt.date
                        last_day_vol = float(ohlcv_df.loc[dates == dates.iloc[-1], "volume"].sum() or 0)
                        if last_day_vol <= 0:
                            return HardFilterResult(
                                passed=False,
                                category="suspended",
                                reason="Saham suspen / tidak ada transaksi pada sesi hari terakhir (volume = 0)",
                            )
                    elif float(ohlcv_df["volume"].iloc[-1] or 0) <= 0:
                        return HardFilterResult(
                            passed=False,
                            category="suspended",
                            reason="Saham suspen / tidak ada transaksi (volume = 0)",
                        )
        except Exception as e:
            logger.warning(f"[HardFilter] Gagal mengecek suspended_filter: {e}")

        return HardFilterResult(passed=True)

    def _check_min_price_filter(self, ohlcv_df, timeframe: str = "1d") -> HardFilterResult:
        """
        Filter harga minimal:
        - Daily: harga > 10 tetap dimasukkan, <= 10 dikeluarkan.
        - Intraday (15m/60m): harga > 50 dimasukkan, <= 50 dikeluarkan (hindari saham gocap/FCA).
        """
        if settings.DATA_PROVIDER == "mock" or ohlcv_df is None or len(ohlcv_df) == 0:
            return HardFilterResult(passed=True)

        try:
            last_price = float(ohlcv_df["close"].iloc[-1])
            is_intraday = self._is_intraday(timeframe)
            min_p = self.MIN_PRICE_INTRADAY if is_intraday else self.MIN_PRICE
            if last_price <= min_p:
                return HardFilterResult(
                    passed=False,
                    category="min_price",
                    reason=f"Harga saham Rp{last_price:.0f} <= Rp{min_p:.0f} (terlalu rendah untuk {'intraday' if is_intraday else 'pasar'})"
                )
        except Exception as e:
            logger.warning(f"[HardFilter] Gagal mengecek min_price: {e}")

        return HardFilterResult(passed=True)

    def _check_ara_filter(self, ohlcv_df, timeframe: str = "1d") -> HardFilterResult:
        """
        Filter tolak saham yang sudah ARA atau hampir menyentuh batas ARA (Auto Rejection Atas).
        Batas ARA BEI Simetris:
          - Harga <= Rp 200: 35%
          - Rp 200 < Harga <= Rp 5.000: 25%
          - Harga > Rp 5.000: 20%
        Saham yang sudah ARA atau sisa ruang kenaikan < 3.5% (atau gain >= 85% dari batas ARA)
        ditolak karena risiko rejection/climax selling dan Risk:Reward sangat buruk.
        """
        if settings.DATA_PROVIDER == "mock" or ohlcv_df is None or len(ohlcv_df) < 2:
            return HardFilterResult(passed=True)

        try:
            prev_close = 0.0
            current_price = float(ohlcv_df["close"].iloc[-1])
            high_today = float(ohlcv_df["high"].iloc[-1])

            if timeframe == "1d" or "date" not in ohlcv_df.columns:
                prev_close = float(ohlcv_df["close"].iloc[-2])
                high_today = float(ohlcv_df["high"].iloc[-1])
            else:
                # Intraday (15m / 60m): Pisahkan bar hari ini vs kemarin
                dates = pd.to_datetime(ohlcv_df["date"]).dt.date
                unique_dates = dates.unique()
                if len(unique_dates) >= 2:
                    today_date = unique_dates[-1]
                    prev_date = unique_dates[-2]
                    today_bars = ohlcv_df[dates == today_date]
                    prev_bars = ohlcv_df[dates == prev_date]
                    if not prev_bars.empty and not today_bars.empty:
                        prev_close = float(prev_bars["close"].iloc[-1])
                        high_today = float(today_bars["high"].max())
                    else:
                        prev_close = float(ohlcv_df["close"].iloc[-2])
                else:
                    prev_close = float(ohlcv_df["close"].iloc[-2])

            if prev_close <= 0 or current_price <= 0:
                return HardFilterResult(passed=True)

            # 1. Tentukan persentase batas ARA berdasarkan regulasi BEI
            if prev_close <= 200:
                ara_pct = 35.0
            elif prev_close <= 5000:
                ara_pct = 25.0
            else:
                ara_pct = 20.0

            # 2. Hitung harga ARA teoritis dengan pembulatan fraksi tick BEI (floor)
            if prev_close < 200:
                tick = 1.0
            elif prev_close < 500:
                tick = 2.0
            elif prev_close < 2000:
                tick = 5.0
            elif prev_close < 5000:
                tick = 10.0
            else:
                tick = 25.0

            ara_raw = prev_close * (1.0 + ara_pct / 100.0)
            ara_price = np.floor(ara_raw / tick) * tick

            gain_today = ((current_price - prev_close) / prev_close) * 100.0
            high_gain_today = ((high_today - prev_close) / prev_close) * 100.0

            # 3. Kriteria Penolakan (Sudah ARA atau Hampir Menyentuh ARA)
            # A. Sudah menyentuh / lock ARA:
            if current_price >= ara_price or high_today >= ara_price:
                return HardFilterResult(
                    passed=False,
                    category="ara_limit",
                    reason=f"Saham sudah menyentuh/terkunci ARA (+{high_gain_today:.1f}% vs batas ARA +{ara_pct:.0f}%, max Rp{ara_price:,.0f}) — rawan profit taking ekstrim"
                )

            # B. Hampir menyentuh ARA:
            # - Sisa kenaikan ke harga ARA <= 3.5%
            # - Atau gain saat ini sudah >= 85% dari batas ARA (misal 35% -> >= 29.75%, 25% -> >= 21.25%, 20% -> >= 17%)
            pct_to_ara = ((ara_price - current_price) / ara_price) * 100.0
            ratio_to_ara = gain_today / ara_pct if ara_pct > 0 else 0

            if pct_to_ara <= 3.5 or ratio_to_ara >= 0.85:
                return HardFilterResult(
                    passed=False,
                    category="ara_limit",
                    reason=f"Saham hampir menyentuh ARA (+{gain_today:.1f}% vs batas ARA +{ara_pct:.0f}%, sisa ke ARA {pct_to_ara:.1f}%) — upside terbatas & R:R buruk"
                )

        except Exception as e:
            logger.warning(f"[HardFilter] Gagal mengecek ara_filter: {e}")

        return HardFilterResult(passed=True)

    def _check_prev_day_gain_filter(self, ohlcv_df, timeframe: str = "1d", pure_technical: bool = False) -> HardFilterResult:
        """
        Filter tolak saham yang sudah naik melebihi batas pada hari perdagangan sebelumnya:
        - Daily (pagi hari): maks +20%
        - Intraday (siang): maks +15%
        """
        if settings.DATA_PROVIDER == "mock" or ohlcv_df is None or len(ohlcv_df) < 2:
            return HardFilterResult(passed=True)

        max_gain = (
            self.MAX_PREV_DAY_GAIN_PCT_INTRADAY
            if self._is_intraday(timeframe, pure_technical=pure_technical)
            else self.MAX_PREV_DAY_GAIN_PCT
        )

        try:
            prev_gain = 0.0
            if timeframe == "1d" or "date" not in ohlcv_df.columns:
                c_last = ohlcv_df["close"].iloc[-1]
                c_prev = ohlcv_df["close"].iloc[-2]
                if c_prev > 0:
                    prev_gain = ((c_last - c_prev) / c_prev) * 100.0
            else:
                # Intraday: kelompokkan per tanggal untuk melihat return hari kemarin
                dates = pd.to_datetime(ohlcv_df["date"]).dt.date
                daily_closes = ohlcv_df.groupby(dates)["close"].last()
                if len(daily_closes) >= 3:
                    c_kemarin = daily_closes.iloc[-2]
                    c_lusa = daily_closes.iloc[-3]
                    if c_lusa > 0:
                        prev_gain = ((c_kemarin - c_lusa) / c_lusa) * 100.0
                elif len(daily_closes) >= 2:
                    c_last = daily_closes.iloc[-1]
                    c_prev = daily_closes.iloc[-2]
                    if c_prev > 0:
                        prev_gain = ((c_last - c_prev) / c_prev) * 100.0

            if prev_gain > max_gain:
                return HardFilterResult(
                    passed=False,
                    category="prev_day_surge",
                    reason=f"Saham naik > {max_gain:.0f}% di hari sebelumnya (+{prev_gain:.1f}%) — risiko profit taking / climax"
                )
        except Exception as e:
            logger.warning(f"[HardFilter] Gagal mengecek prev_day_gain: {e}")

        return HardFilterResult(passed=True)

    def _check_adx_filter(self, technical: Dict, data_len: int, timeframe: str = "1d", pure_technical: bool = False) -> HardFilterResult:
        """
        ADX Hard Filter sadar warm-up period:
        - Jika data < 28 bar, ADX belum stabil → SKIP filter (jangan gugurkan).
        - Daily (pagi hari): wajib ADX >= 12.
        - Intraday (siang): dinilai via scoring engine (tidak menggugurkan).
        """
        if settings.DATA_PROVIDER == "mock":
            return HardFilterResult(passed=True)

        if data_len < self.ADX_WARMUP_DAYS:
            logger.debug(f"[HardFilter] ADX warm-up skip (data={data_len} bar < {self.ADX_WARMUP_DAYS})")
            return HardFilterResult(passed=True, category="adx_warmup_skip",
                                    reason=f"ADX skip — data {data_len} bar belum cukup warm-up")

        if self._is_intraday(timeframe, pure_technical=pure_technical):
            return HardFilterResult(
                passed=True,
                category="adx_scoring_only",
                reason="ADX intraday dinilai via scoring engine (tidak menggugurkan)",
            )

        adx = technical.get("adx", 0) or 0
        if adx < self.ADX_HARD_FILTER_THRESHOLD:
            return HardFilterResult(
                passed=False,
                category="adx",
                reason=f"ADX terlalu rendah ({adx:.1f} < {self.ADX_HARD_FILTER_THRESHOLD}) — tren belum terbentuk",
            )
        return HardFilterResult(passed=True)

    def _check_liquidity_filter(self, technical: Dict, ohlcv_df, timeframe: str = "1d", pure_technical: bool = False) -> HardFilterResult:
        """
        Volume DAN Value check dengan threshold & window adaptif:
        - Daily (1d / pagi hari): rata-rata 5 hari — volume min 200.000 lembar, value min Rp 1 Miliar
        - Intraday (15m/60m / pure technical): rata-rata 20 bar — volume min 200.000 lembar, value min Rp 2 Miliar
        """
        if settings.DATA_PROVIDER == "mock":
            return HardFilterResult(passed=True)

        is_intraday = self._is_intraday(timeframe, pure_technical=pure_technical)
        min_vol = self.MIN_AVG_VOLUME_LOT_INTRADAY if is_intraday else self.MIN_AVG_VOLUME_LOT
        min_val = self.MIN_AVG_VALUE_IDR_INTRADAY if is_intraday else self.MIN_AVG_VALUE_IDR
        window = self.INTRADAY_LIQUIDITY_WINDOW_BARS if is_intraday else self.DAILY_LIQUIDITY_WINDOW_DAYS
        unit_label = "bar" if is_intraday else "hari"

        if is_intraday:
            vol_avg = technical.get("volume_avg_20", 0) or 0
        else:
            if "volume_avg_5" in technical and technical["volume_avg_5"] is not None:
                vol_avg = technical["volume_avg_5"] or 0
            elif ohlcv_df is not None and len(ohlcv_df) > 0 and "volume" in ohlcv_df.columns and "volume_avg_20" not in technical:
                vol_avg = float(ohlcv_df["volume"].tail(window).mean())
            else:
                vol_avg = technical.get("volume_avg_20", 0) or 0
        volume_passed = vol_avg >= min_vol

        value_passed = True  # default jika kolom tidak tersedia
        avg_value_display = 0.0
        if ohlcv_df is not None and len(ohlcv_df) > 0 and "value" in ohlcv_df.columns:
            avg_value_display = float(ohlcv_df["value"].tail(window).mean())
            value_passed = avg_value_display >= min_val

        if not volume_passed and not value_passed:
            return HardFilterResult(
                passed=False, category="volume_and_value",
                reason=(
                    f"Gagal volume avg {window} {unit_label} ({vol_avg:,.0f} < {min_vol:,.0f}) "
                    f"DAN value (Rp{avg_value_display/1e9:.2f}M < Rp{min_val/1e9:.1f}M)"
                )
            )
        if not volume_passed:
            return HardFilterResult(
                passed=False, category="volume",
                reason=f"Volume avg {window} {unit_label} terlalu rendah ({vol_avg:,.0f}) — minimum {min_vol:,.0f}"
            )
        if not value_passed:
            return HardFilterResult(
                passed=False, category="value",
                reason=f"Nilai transaksi rata-rata {window} {unit_label} terlalu rendah (Rp{avg_value_display/1e9:.2f}M) — minimum Rp{min_val/1e9:.1f}M"
            )
        return HardFilterResult(passed=True)

    def _check_atr_filter(self, technical: Dict, timeframe: str = "1d", pure_technical: bool = False) -> HardFilterResult:
        """ATR filter: tolak saham yang terlalu volatile (> 10% untuk daily, > 7% untuk intraday)."""
        if settings.DATA_PROVIDER == "mock":
            return HardFilterResult(passed=True)

        max_atr = (
            self.MAX_ATR_PCT_INTRADAY
            if self._is_intraday(timeframe, pure_technical=pure_technical)
            else self.MAX_ATR_PCT
        )
        atr_pct = technical.get("atr_percent", 0) or 0
        if atr_pct > max_atr:
            return HardFilterResult(
                passed=False, category="atr",
                reason=f"ATR terlalu tinggi ({atr_pct:.1f}% > {max_atr:.1f}%) — risiko terlalu besar, R:R buruk"
            )
        return HardFilterResult(passed=True)

    def _run_hard_filters(self, technical: Dict, ohlcv_df, data_len: int, timeframe: str = "1d", pure_technical: bool = False, latest_market_date=None) -> HardFilterResult:
        """
        Orkestrasi semua Hard Filter secara berurutan.
        Mengembalikan HardFilterResult pertama yang gagal, atau passed=True jika semua lolos.
        """
        market_ref = latest_market_date if latest_market_date is not None else technical.get("_latest_market_date")
        for check_fn in [
            lambda: self._check_suspended_filter(ohlcv_df, timeframe=timeframe, latest_market_date=market_ref),
            lambda: self._check_min_price_filter(ohlcv_df, timeframe=timeframe),
            lambda: self._check_prev_day_gain_filter(ohlcv_df, timeframe=timeframe, pure_technical=pure_technical),
            lambda: self._check_ara_filter(ohlcv_df, timeframe=timeframe),
            lambda: self._check_adx_filter(technical, data_len, timeframe=timeframe, pure_technical=pure_technical),
            lambda: self._check_liquidity_filter(technical, ohlcv_df, timeframe=timeframe, pure_technical=pure_technical),
            lambda: self._check_atr_filter(technical, timeframe=timeframe, pure_technical=pure_technical),
        ]:
            result = check_fn()
            if not result.passed:
                return result
        return HardFilterResult(passed=True)

    # -- Backward-compat alias (agar kode lain yang memanggil tidak error) --
    def _check_hard_filters(self, technical: Dict, ohlcv_df=None, timeframe: str = "1d", pure_technical: bool = False, latest_market_date=None) -> Optional[str]:
        data_len = technical.get("_data_length", 60)
        r = self._run_hard_filters(
            technical, ohlcv_df, data_len,
            timeframe=timeframe, pure_technical=pure_technical,
            latest_market_date=latest_market_date,
        )
        return None if r.passed else r.reason

    # ------------------------------------------------------------------ #
    #  ADX Tiered Scorer (standalone, bisa dipanggil dari mana saja)
    # ------------------------------------------------------------------ #

    @staticmethod
    def score_adx(adx_value: float, day_index_in_window: int) -> Dict[str, Any]:
        """
        Hitung skor ADX dengan warm-up guard dan tiered threshold.

        Latar belakang teknis:
        - ADX adalah LAGGING indicator — ia mencerminkan tren yang SUDAH terjadi,
          bukan yang akan terjadi. Nilai ekstrem tinggi (>40) tidak boleh diperlakukan
          sama dengan sinyal kuat baru terbentuk.
        - Untuk prediksi D+1 (1 hari ke depan), ADX 25-40 adalah sweet spot terbaik:
          trend kuat yang belum di fase klimaks, entry risk-reward masih baik.
        - ADX > 40 mengindikasikan tren sudah tua/ekstrem dan rawan pembalikan,
          sehingga skor diturunkan untuk mencegah chasing di puncak tren.
        - Sebelum 28 bar data, ADX belum stabil (perlu smoothing berhari-hari),
          sehingga skornya diabaikan agar tidak merusak keputusan sinyal.

        Args:
            adx_value          : Nilai ADX saat ini dari technical engine
            day_index_in_window: Jumlah bar data yang tersedia (= data_length)

        Returns:
            dict dengan keys:
                score          (int) : Poin yang dikontribusikan ke Trend & Momentum
                label          (str) : Label deskriptif fase tren
                low_confidence (bool): True jika ADX belum melewati warm-up period
        """
        ADX_WARMUP_DAYS = 28

        # Guard: ADX belum stabil sebelum 28 bar
        if day_index_in_window < ADX_WARMUP_DAYS:
            return {
                "score": 0,
                "label": "low_confidence",
                "low_confidence": True,
                "reason": (
                    f"ADX belum stabil "
                    f"(data={day_index_in_window} bar, butuh min {ADX_WARMUP_DAYS})"
                ),
            }

        if adx_value is None:
            return {"score": 0, "label": "no_data", "low_confidence": False}

        # Tiered scoring
        if adx_value < 15:
            # Market choppy/sideways total, tidak ada tren yang bisa diandalkan
            return {"score": 0, "label": "no_trend", "low_confidence": False}
        elif adx_value < 20:
            # Tren mulai terbentuk, tapi masih sangat lemah
            return {"score": 1, "label": "early_trend", "low_confidence": False}
        elif adx_value < 25:
            # Tren moderat, layak tapi belum ideal untuk entry agresif
            return {"score": 2, "label": "moderate_trend", "low_confidence": False}
        elif adx_value <= 40:
            # SWEET SPOT: tren kuat, fresh, risk-reward entry masih bagus
            return {"score": 3, "label": "strong_trend", "low_confidence": False}
        elif adx_value <= 50:
            # Overextended: tren sudah tua, potensi reversal meningkat
            return {"score": 2, "label": "overextended", "low_confidence": False}
        else:
            # Ekstrem: ADX > 50, fase klimaks tren, hindari entry baru
            return {"score": 1, "label": "climax_trend", "low_confidence": False}

    # ------------------------------------------------------------------ #
    #  Category Scorers
    # ------------------------------------------------------------------ #

    def _score_trend_momentum(self, t: Dict) -> List[RuleResult]:
        """Trend & Momentum — Max 25 poin (FREE mode) / 20 poin (PREMIUM mode).

        Redesigned for 60-day window:
        - EMA alignment: EMA10 > EMA20 > EMA50 (bukan EMA200 — invalid di 60 hari)
        - MACD: hanya aktif jika data >= 35 bar (warm-up guard)
        - ADX: tiered scoring via score_adx(), hanya valid setelah 28 bar
          Sweet spot ADX 25-40 (max +3 pts), overextended ADX >40 (diturunkan)
        """
        rules = []
        cat = "trend_momentum"
        data_len = t.get("_data_length", 60)

        # --- EMA Alignment: EMA10 > EMA20 > EMA50 (max +7) ---
        if t.get("ema_alignment_bullish"):
            label = "EMA10>EMA20>EMA50" if t.get("ema_50") else "EMA10>EMA20 (partial)"
            rules.append(RuleResult("EMA Alignment Bullish", 7, 7, cat, label))
        elif t.get("ema_alignment_bearish"):
            rules.append(RuleResult("EMA Alignment Bearish", -4, 7, cat, "EMA bearish alignment"))

        # --- Price above EMA20: +3 ---
        if t.get("price_above_ema20"):
            rules.append(RuleResult("Price > EMA20", 3, 3, cat, "Harga di atas EMA20"))

        # --- MACD: hanya valid setelah 35 hari warm-up ---
        if data_len >= 35:
            if t.get("macd_bullish_cross"):
                rules.append(RuleResult("MACD Bullish Cross", 4, 4, cat,
                                        "MACD golden cross (validated)"))
            elif t.get("macd_bearish_cross"):
                rules.append(RuleResult("MACD Bearish Cross", -3, 4, cat,
                                        "MACD death cross"))

        # --- ADX: tiered scoring via score_adx() ---
        adx_val  = t.get("adx", 0) or 0
        adx_result = self.score_adx(adx_val, data_len)
        adx_score  = adx_result["score"]
        adx_label  = adx_result["label"]
        adx_low_conf = adx_result["low_confidence"]

        if adx_low_conf:
            # Warm-up period: abaikan ADX, tidak kontribusikan skor
            logger.debug(f"[ADX] Skipped — {adx_result.get('reason', 'low confidence')}")
        elif adx_score > 0:
            detail = f"ADX {adx_val:.0f} — {adx_label}"
            if adx_label == "overextended":
                detail += " (tren sudah tua, entry berisiko)"
            elif adx_label == "climax_trend":
                detail += " (fase klimaks, hindari chasing!)"
            elif adx_label == "strong_trend":
                detail += " (sweet spot D+1 — ideal entry)"
            rules.append(RuleResult("ADX Trend Strength", adx_score, 3, cat, detail))
        # ADX score 0 (no_trend / no_data): tidak perlu append rule apapun

        # +DI > -DI bonus: hanya jika ADX sudah dalam zona trending (>= moderate_trend)
        # dan tidak dalam kondisi warm-up
        if (not adx_low_conf
                and adx_label in ("moderate_trend", "strong_trend")
                and t.get("di_bullish")):
            rules.append(RuleResult("+DI > -DI", 2, 2, cat,
                                    "Directional bullish (+DI lebih besar dari -DI)"))

        # --- RSI Scoring Sesuai 4 Logika Spesifik User ---
        # 1. If RSI > 80 dan konsisten > 80 selama 4 periode = + poin (+4)
        # 2. If RSI > 80 dan ada pembalikan arah ke < 80 = - poin (-4)
        # 3. If RSI < 30 dan konsisten < 30 selama 4 periode = - poin (-4)
        # 4. If RSI < 30 dan ada pembalikan arah ke > 30 = + poin (+4)
        rsi = t.get("rsi")
        rsi_consistent_above_80 = t.get("rsi_consistent_above_80", False)
        rsi_reversal_down_80 = t.get("rsi_reversal_down_from_80", False)
        rsi_consistent_below_30 = t.get("rsi_consistent_below_30", False)
        rsi_reversal_up_30 = t.get("rsi_reversal_up_from_30", False)

        # Fallback check jika t hanya dipanggil dengan nilai float rsi & rsi_prev (tanpa precomputed flags)
        if rsi is not None and not (rsi_consistent_above_80 or rsi_reversal_down_80 or rsi_consistent_below_30 or rsi_reversal_up_30):
            rsi_prev = t.get("rsi_prev")
            rsi_last_4 = t.get("rsi_last_4", [])
            if len(rsi_last_4) == 4 and all(x > 80.0 for x in rsi_last_4):
                rsi_consistent_above_80 = True
            elif len(rsi_last_4) == 4 and all(x < 30.0 for x in rsi_last_4):
                rsi_consistent_below_30 = True
            elif rsi_prev is not None and rsi_prev >= 80.0 and rsi < 80.0:
                rsi_reversal_down_80 = True
            elif rsi_prev is not None and rsi_prev <= 30.0 and rsi > 30.0:
                rsi_reversal_up_30 = True

        if rsi_consistent_above_80:
            rules.append(RuleResult(
                "RSI Super Momentum (>80 x4)", 4, 4, cat,
                f"RSI {rsi:.1f} konsisten >80 selama 4 periode — super bullish momentum"
            ))
        elif rsi_reversal_down_80:
            rules.append(RuleResult(
                "RSI Overbought Reversal (<80)", -4, 4, cat,
                f"RSI {rsi:.1f} pembalikan arah turun ke <80 — sinyal koreksi/taking profit"
            ))
        elif rsi_consistent_below_30:
            rules.append(RuleResult(
                "RSI Persistent Oversold (<30 x4)", -4, 4, cat,
                f"RSI {rsi:.1f} konsisten <30 selama 4 periode — tekanan jual ekstrem (falling knife)"
            ))
        elif rsi_reversal_up_30:
            rules.append(RuleResult(
                "RSI Oversold Reversal (>30)", 4, 4, cat,
                f"RSI {rsi:.1f} pembalikan arah naik ke >30 — konfirmasi rebound / bullish bounce"
            ))
        elif rsi is not None and 50.0 <= rsi < 80.0:
            rules.append(RuleResult(
                "RSI Healthy Bullish Zone", 2, 4, cat,
                f"RSI {rsi:.1f} — tren bullish sehat"
            ))
        elif rsi is not None and 40.0 <= rsi < 50.0:
            rules.append(RuleResult(
                "RSI Neutral Zone", 1, 2, cat,
                f"RSI {rsi:.1f} — zona netral"
            ))
        if t.get("rsi_divergence") == "bullish":
            rules.append(RuleResult("RSI Bullish Divergence", 2, 2, cat,
                                    "Price LL, RSI HL"))

        # --- VWAP bias ---
        if t.get("price_above_vwap") is True:
            rules.append(RuleResult("Price > VWAP", 3, 3, cat,
                                    "Harga di atas VWAP — bullish bias"))
        elif t.get("price_below_vwap") is True or ("price_below_vwap" not in t and t.get("price_above_vwap") is False):
            rules.append(RuleResult("Price < VWAP", -2, 3, cat,
                                    "Harga di bawah VWAP — bearish bias"))

        return rules

    def _score_volume_liquidity(self, t: Dict, ohlcv_df=None) -> List[RuleResult]:
        rules = []
        cat = "volume_liquidity"

        # Volume breakout: >= 2x avg20 → +8
        if t.get("volume_breakout"):
            rules.append(RuleResult("Volume Breakout (≥2x Avg20)", 8, 8, cat,
                                    f"Volume {t.get('volume_ratio', 0):.1f}x rata-rata 20H (breakout nyata)"))

        # Avg volume 5H > avg volume 20H → volume tren naik → +3
        if t.get("volume_5_above_20"):
            avg5 = t.get("volume_avg_5", 0)
            avg20 = t.get("volume_avg_20", 0)
            rules.append(RuleResult("Avg Vol 5H > Avg Vol 20H", 3, 3, cat,
                                    f"Tren volume naik: avg5={avg5:,.0f} > avg20={avg20:,.0f}"))

        # Volume Buying Pressure: konfirmasi breakout bullish (+2 bonus)
        if t.get("volume_is_buying"):
            rules.append(RuleResult("Volume Buying Pressure", 2, 2, cat,
                                    "Volume tinggi + candle hijau = buying pressure nyata"))
        # Volume Selling Pressure: distribusi terselubung (-3 penalti)
        elif t.get("volume_is_selling"):
            rules.append(RuleResult("Volume Selling Pressure", -3, 2, cat,
                                    "Volume tinggi + candle merah = selling/distribusi"))

        # Volume increasing trend (legacy check): +2
        if t.get("volume_increasing") and not t.get("volume_5_above_20"):
            # Hanya tambahkan jika vol_5_above_20 belum dihitung untuk menghindari double count
            rules.append(RuleResult("Volume Increasing", 2, 2, cat, "Volume trend naik (5-bar vs 10-bar)"))

        # OBV rising: +4
        if t.get("obv_rising"):
            rules.append(RuleResult("OBV Rising", 4, 4, cat, "On Balance Volume naik"))

        # Volume dry-up (negative)
        if t.get("volume_dry_up"):
            rules.append(RuleResult("Volume Dry Up", -3, 3, cat, "Volume terlalu rendah"))

        # Value Liquidity Confirmation: avg daily value tinggi = saham blue chip / likuid
        # Rule ini menutup gap antara max achievable (~19) dan bobot kategori (28)
        if ohlcv_df is not None and "value" in ohlcv_df.columns and len(ohlcv_df) >= 20:
            avg_value = ohlcv_df["value"].tail(20).mean()
            if avg_value >= 100_000_000_000:  # > Rp 100 miliar / hari
                rules.append(RuleResult("High Value Liquidity", 5, 5, cat,
                                        f"Avg daily value Rp{avg_value/1e9:.0f}B — very liquid, slippage minimal"))
            elif avg_value >= 50_000_000_000:  # > Rp 50 miliar / hari
                rules.append(RuleResult("Good Value Liquidity", 3, 5, cat,
                                        f"Avg daily value Rp{avg_value/1e9:.0f}B — good liquidity"))

        # Volume-Price Divergence: volume naik tapi harga turun = akumulasi terselubung (+3)
        if ohlcv_df is not None and len(ohlcv_df) >= 10:
            vol_trend_up = t.get("volume_5_above_20") or t.get("volume_increasing")
            price_5d_change = (ohlcv_df["close"].iloc[-1] / ohlcv_df["close"].iloc[-5] - 1) if len(ohlcv_df) >= 5 else 0
            if vol_trend_up and price_5d_change < -0.01:
                rules.append(RuleResult("Volume-Price Divergence", 3, 3, cat,
                                        "Volume naik tapi harga turun — potensi akumulasi terselubung"))

        return rules

    def _score_patterns(self, pattern: Dict, candle: Dict) -> List[RuleResult]:
        rules = []
        cat = "pattern"

        # Chart pattern score
        p_score = pattern.get("pattern_score", 0)
        p_bias = pattern.get("pattern_bias", "neutral")

        if p_bias == "bullish" and p_score > 0:
            rules.append(RuleResult(
                "Chart Pattern Bullish", min(p_score, 8), 8, cat,
                f"Patterns: {', '.join(pattern.get('patterns', []))}"
            ))
        elif p_bias == "bearish" and p_score < 0:
            rules.append(RuleResult(
                "Chart Pattern Bearish", max(p_score, -8), 8, cat,
                f"Patterns: {', '.join(pattern.get('patterns', []))}"
            ))

        # Candlestick pattern score
        c_score = candle.get("candle_score", 0)
        c_bias = candle.get("candle_bias", "neutral")

        if c_bias == "bullish" and c_score > 0:
            rules.append(RuleResult(
                "Candle Pattern Bullish", min(c_score, 7), 7, cat,
                f"Candles: {', '.join(candle.get('candle_patterns', []))}"
            ))
        elif c_bias == "bearish" and c_score < 0:
            rules.append(RuleResult(
                "Candle Pattern Bearish", max(c_score, -7), 7, cat,
                f"Candles: {', '.join(candle.get('candle_patterns', []))}"
            ))

        return rules

    def _score_gap_analysis(self, gap: Dict) -> List[RuleResult]:
        """Gap Analysis \u2014 max 5 poin (berlaku di kedua mode).
        
        Gap = selisih open hari ini vs close kemarin (>= 1% dianggap signifikan).
        - Gap Up + volume confirm  : sinyal momentum kuat    (+5)
        - Gap Up tanpa konfirmasi  : risiko fade / reversal  (-2)
        - Gap Down                 : tekanan jual awal sesi  (-3)
        """
        rules = []
        cat = "gap_analysis"
        gap_type = gap.get("gap_type", "none")
        gap_pct   = gap.get("gap_pct", 0)

        if gap_type == "gap_up_confirmed":
            rules.append(RuleResult(
                "Gap Up Confirmed", 5, 5, cat,
                f"Gap up {gap_pct:.1f}% dengan konfirmasi volume (momentum nyata)"
            ))
        elif gap_type == "gap_up_unconfirmed":
            rules.append(RuleResult(
                "Gap Up Unconfirmed", -2, 5, cat,
                f"Gap up {gap_pct:.1f}% TANPA konfirmasi volume (risiko reversal)"
            ))
        elif gap_type == "gap_down":
            rules.append(RuleResult(
                "Gap Down", -3, 5, cat,
                f"Gap down {gap_pct:.1f}% — tekanan jual di awal sesi"
            ))

        return rules

    def _score_sector_correlation(self, sector: Dict) -> List[RuleResult]:
        """Sector/Market Correlation \u2014 max 4 poin (berlaku di kedua mode).
        
        Mengukur relative strength saham vs IHSG dalam 5 hari terakhir.
        - RS > +2% vs IHSG  : outperform  (+4)
        - RS 0% to +2%      : inline pos  (+2)
        - RS -2% to 0%      : inline neut  (0)
        - RS < -2% vs IHSG  : underperform (-2)
        """
        rules = []
        cat = "sector_correlation"
        signal = sector.get("corr_signal", "neutral")
        rs     = sector.get("relative_strength", 0)

        if signal == "outperform":
            rules.append(RuleResult(
                "Outperform IHSG", 4, 4, cat,
                f"RS vs IHSG: +{rs:.1f}% dalam 5 hari (saham lebih kuat dari market)"
            ))
        elif signal in ("inline_positive", "strong_5d_return", "positive_5d_return"):
            rules.append(RuleResult(
                "Inline / Slight Outperform", 2, 4, cat,
                f"RS vs IHSG: +{rs:.1f}% (inline dengan market)"
            ))
        elif signal in ("underperform", "weak_5d_return"):
            rules.append(RuleResult(
                "Underperform IHSG", 0, 4, cat,
                f"RS vs IHSG: {rs:.1f}% (saham underperform market, skor tidak dipotong)"
            ))

        return rules

    def _score_support_resistance(self, t: Dict, ohlcv_df=None) -> List[RuleResult]:

        rules = []
        cat = "support_resistance"

        # Bollinger Band position
        bb_pct = t.get("bb_percent_b", 0.5)
        if bb_pct is not None:
            if t.get("price_below_lower_bb"):
                rules.append(RuleResult("Below Lower BB", 5, 5, cat,
                                        "Harga di bawah lower BB (potential bounce)"))
            elif bb_pct < 0.3:
                rules.append(RuleResult("Near Lower BB", 3, 3, cat,
                                        f"BB %B = {bb_pct:.2f} (near support)"))

        # BB Squeeze
        if t.get("bb_squeeze"):
            rules.append(RuleResult("BB Squeeze", 3, 3, cat,
                                    "Bollinger Band squeeze (breakout imminent)"))

        # Stochastic oversold
        if t.get("stoch_oversold"):
            rules.append(RuleResult("Stoch Oversold", 2, 2, cat,
                                    f"Stoch %K = {t.get('stoch_k', 0):.0f}"))

        if t.get("stoch_bullish_cross"):
            rules.append(RuleResult("Stoch Bullish Cross", 2, 2, cat,
                                    "Stochastic bullish crossover"))

        return rules

    def _score_bandarmology(self, b: Dict) -> List[RuleResult]:
        """Bandarmology (Broker Summary) — Max 15 poin (15%).
        
        Scoring berdasarkan data performance nyata (Bandarmology Winning Combos dataset):
        
        1. Base signal score (akumulasi/distribusi):  max ±20
        2. Broker Confidence Score (lead buyer WR):   max ±3
        3. Winning Combo Match:                       max +2
        4. Toxic Seller Penalty:                      max -2
        5. Danger Broker Penalty (MG di top 3):       max -1
        6. Foreign Broker Bonus (top 3 buyers):       max +2
        
        Data WR basis (dari dataset 458 resolved signals, Jun 10-19 2026):
        - Asing lead buyer: 93.5% WR, +5.07% avg P/L
        - Lokal lead buyer: 76.6% WR
        - 7 combo dengan 100% WR
        """
        rules = []
        cat = "bandarmology"

        signal = b.get("bandar_signal", "neutral")

        # ── 1. Base Accumulation/Distribution Signal ──
        if signal == "strong_accumulation":
            rules.append(RuleResult("Strong Accumulation", 15, 15, cat,
                                    "Smart money akumulasi kuat"))
        elif signal == "accumulation":
            rules.append(RuleResult("Accumulation", 10, 15, cat,
                                    "Deteksi akumulasi"))
        elif signal == "distribution":
            rules.append(RuleResult("Distribution", -8, 15, cat,
                                    "Deteksi distribusi"))
        elif signal == "strong_distribution":
            rules.append(RuleResult("Strong Distribution", -15, 15, cat,
                                    "Distribusi kuat terdeteksi"))

        # Smart vs retail divergence bonus (+4)
        if b.get("smart_vs_retail_divergence"):
            rules.append(RuleResult("Smart vs Retail Divergence", 4, 4, cat,
                                    "Smart money beli, retail jual"))

        # ── 2. Broker Confidence Score (berdasarkan lead buyer WR) ──
        # Data: Elite buyers punya WR 97-100%, Good buyers 83-88%, Danger buyers 46-54%
        top_buyers = b.get("top_buyers", [])
        top_sellers = b.get("top_sellers", [])
        lead_buyer = top_buyers[0] if top_buyers else None

        # Elite + Strong buyers (97-100% WR) → confidence +3
        ELITE_BUYERS = {"AK", "RX", "DP", "NI", "YP"}
        # Good buyers (83-88% WR) → confidence +2
        GOOD_BUYERS = {"BK", "CC", "BB"}
        # Danger buyers (46-54% WR) → confidence -2
        DANGER_BUYERS = {"XL", "MG", "PD", "CP"}
        # Danger broker extra: MG (Semesta Indovest) di mana pun di top 3 → extra -1
        EXTRA_DANGER = {"MG"}

        if lead_buyer:
            if lead_buyer in ELITE_BUYERS:
                rules.append(RuleResult("Elite Lead Buyer", 3, 3, cat,
                                        f"Lead buyer {lead_buyer} — Elite (WR 97-100%)"))
            elif lead_buyer in GOOD_BUYERS:
                rules.append(RuleResult("Good Lead Buyer", 2, 3, cat,
                                        f"Lead buyer {lead_buyer} — Good (WR 83-88%)"))
            elif lead_buyer in DANGER_BUYERS:
                rules.append(RuleResult("Danger Lead Buyer", -2, 3, cat,
                                        f"Lead buyer {lead_buyer} — Danger (WR 46-54%) ⚠️"))

        # ── 3. Foreign Broker in Top 3 Buyers → +2 ──
        # Data: Asing lead buyer 93.5% WR >> Lokal 76.6%. Foreign = strongest signal
        FOREIGN_BROKERS = {"AK", "BK", "KZ", "RX", "AG", "YU", "DP"}
        foreign_in_top3 = sum(1 for br in top_buyers[:3] if br in FOREIGN_BROKERS)
        if foreign_in_top3 >= 2:
            rules.append(RuleResult("Foreign Broker Dominance", 2, 2, cat,
                                    f"{foreign_in_top3} asing di top 3 buyers — signal terkuat (WR 93.5%)"))

        # ── 4. Winning Combo Match → +2 ──
        # Data: 7 combo dengan 100% WR (AK+XL, RX+CC, BB+CC, CC+ZP, AK+UBS, CC+AK, LG+BK)
        WINNING_COMBOS = [
            ("AK", "XL"), ("RX", "CC"), ("BB", "CC"),
            ("CC", "ZP"), ("AK", "AK"), ("CC", "AK"), ("LG", "BK"),
        ]
        lead_seller = top_sellers[-1] if top_sellers else None  # tail = biggest seller
        if lead_buyer and lead_seller:
            for combo_buy, combo_sell in WINNING_COMBOS:
                if lead_buyer == combo_buy and lead_seller == combo_sell:
                    rules.append(RuleResult("Winning Combo Match", 2, 2, cat,
                                            f"Combo {lead_buyer}→{lead_seller} — 100% WR historis 🏆"))
                    break

        # ── 5. Toxic Seller Penalty → -2 ──
        # Data: KI (0% WR), YP seller (16.7% WR), AZ (28.6% WR), DX (33.3% WR)
        TOXIC_SELLERS = {"KI", "YP", "AZ", "DX"}
        lead_seller_code = top_sellers[0] if top_sellers else None  # head of sorted tail
        # Sebenarnya top_sellers adalah tail (sorted ascending by net), jadi index -1 = paling negatif
        biggest_seller = top_sellers[-1] if top_sellers else None
        if biggest_seller and biggest_seller in TOXIC_SELLERS:
            rules.append(RuleResult("Toxic Lead Seller", -2, 2, cat,
                                    f"Lead seller {biggest_seller} — Toxic (WR 0-33%) ⚠️ Jangan beli!"))

        # ── 6. MG (Semesta Indovest) Anywhere in Top 3 Buyers → extra -1 ──
        # Data: MG overall WR 46.2%, risk of losing
        if any(br in EXTRA_DANGER for br in top_buyers[:3]):
            rules.append(RuleResult("MG Danger Buyer", -1, 1, cat,
                                    "MG (Semesta Indovest) di top 3 buyers — extra penalty (WR 46.2%)"))

        return rules

    def _score_foreign_flow(self, ff: Dict) -> List[RuleResult]:
        """Foreign Flow — Max 10 poin (10%)."""
        rules = []
        cat = "foreign_flow"

        signal = ff.get("ff_signal", "neutral")

        if signal == "strong_foreign_buy":
            rules.append(RuleResult("Strong Foreign Buy", 10, 10, cat,
                                    "Net foreign buy kuat — asing borong agresif"))
        elif signal == "foreign_buy":
            rules.append(RuleResult("Foreign Buy", 6, 10, cat,
                                    "Net foreign buy 5H positif"))
        elif signal == "foreign_sell":
            rules.append(RuleResult("Foreign Sell", -5, 10, cat,
                                    "Net foreign sell — asing dominan jual"))
        elif signal == "strong_foreign_sell":
            rules.append(RuleResult("Strong Foreign Sell", -10, 10, cat,
                                    "Net foreign sell kuat — asing buang agresif"))

        return rules

    def _score_risk_reward(self, t: Dict, ohlcv_df=None) -> List[RuleResult]:
        """Support/Resistance & Risk-Reward — digabung jadi satu kategori 'support_resistance', max 15 poin.
        
        Catatan: method ini masih dipanggil dengan nama lama, tapi category-nya
        diubah ke 'support_resistance' agar sesuai dengan CATEGORIES baru.
        """
        rules = []
        cat = "support_resistance"  # Digabung ke SR category
        data_len = t.get("_data_length", 60)

        # ATR Volatility (valid setelah 14 hari)
        atr_pct = t.get("atr_percent", 0)
        if atr_pct and 1.5 <= atr_pct <= 4.0:
            rules.append(RuleResult("Healthy Volatility (ATR)", 4, 4, cat,
                                    f"ATR% = {atr_pct:.1f}% (optimal untuk entry)"))
        elif atr_pct and atr_pct > 6.0:
            rules.append(RuleResult("Too Volatile (ATR)", -3, 4, cat,
                                    f"ATR% = {atr_pct:.1f}% — risiko terlalu besar"))

        # MACD histogram + zero (hanya valid setelah 35 hari warm-up)
        if data_len >= 35 and t.get("macd_histogram_rising") and t.get("macd_above_zero"):
            rules.append(RuleResult("Positive Momentum", 3, 3, cat,
                                    "MACD histogram naik di atas zero"))

        # OBV bullish divergence (selalu valid)
        if t.get("obv_divergence_bullish"):
            rules.append(RuleResult("OBV Bullish Divergence", 2, 2, cat,
                                    "Volume akumulasi diam-diam"))

        # --- R/R Ratio scoring berdasarkan Indicator Power Ranking ---
        # Data WR: RR < 0.8 = 73.3% (#9), RR 0.8-1.0 = 62.5% (#22),
        #          RR 1.0-1.2 = 57.5% (#27), RR 1.2-1.5 = 52.9% (#32)
        # Lower RR = closer to support = better entry, higher WR
        rr_ratio = t.get("risk_reward_ratio", 0)
        if rr_ratio and rr_ratio > 0:
            if rr_ratio < 0.8:
                rules.append(RuleResult("Excellent R/R Ratio", 4, 4, cat,
                                        f"R/R = {rr_ratio:.2f} — dekat support (WR 73.3%)"))
            elif rr_ratio < 1.0:
                rules.append(RuleResult("Good R/R Ratio", 2, 4, cat,
                                        f"R/R = {rr_ratio:.2f} — reasonable entry (WR 62.5%)"))
            elif rr_ratio < 1.2:
                rules.append(RuleResult("Fair R/R Ratio", 1, 4, cat,
                                        f"R/R = {rr_ratio:.2f} — fair entry (WR 57.5%)"))
            elif rr_ratio >= 1.5:
                rules.append(RuleResult("Poor R/R Ratio", -2, 4, cat,
                                        f"R/R = {rr_ratio:.2f} — terlalu jauh dari support"))

        return rules

    # ------------------------------------------------------------------ #
    #  Signal Mapping
    # ------------------------------------------------------------------ #

    @staticmethod
    def _map_signal(score: float, timeframe: str = "1d", pure_technical: bool = False) -> str:
        """
        Map skor ke sinyal:
        Pure Technical mode (Siang / Intraday 60m):
        - >= 75 : STRONG BUY
        - >= 60 : BUY
        - >= 40 : WATCHLIST
        - < 40  : AVOID

        Standard mode (Pagi / EOD):
        - >= strong_buy_threshold (90) : STRONG BUY
        - >= buy_threshold (75) : BUY
        - >= 55 : WATCHLIST
        - < 55  : AVOID
        """
        if pure_technical:
            if score >= 75.0:
                return "STRONG BUY"
            elif score >= 60.0:
                return "BUY"
            elif score >= 40.0:
                return "WATCHLIST"
            else:
                return "AVOID"

        thresholds = _load_adaptive_thresholds(timeframe)
        strong_buy_thresh = thresholds.get("strong_buy_threshold", 90.0)
        buy_thresh = thresholds.get("buy_threshold", 75.0)

        if score >= strong_buy_thresh:
            return "STRONG BUY"
        elif score >= buy_thresh:
            return "BUY"
        elif score >= 55:
            return "WATCHLIST"
        else:
            return "AVOID"

    @staticmethod
    def _map_confidence_score(score: float, pure_technical: bool = False) -> int:
        if pure_technical:
            if score >= 80:
                return 10
            elif score >= 70:
                return 9
            elif score >= 60:
                return 8
            elif score >= 50:
                return 7
            elif score >= 40:
                return 6
            elif score >= 35:
                return 5
            elif score >= 25:
                return 4
            elif score >= 20:
                return 3
            elif score >= 10:
                return 2
            else:
                return 1

        if score >= 90:
            return 10
        elif score >= 80:
            return 9
        elif score >= 70:
            return 8
        elif score >= 65:
            return 7
        elif score >= 55:
            return 6
        elif score >= 50:
            return 5
        elif score >= 40:
            return 4
        elif score >= 30:
            return 3
        elif score >= 20:
            return 2
        else:
            return 1

    @staticmethod
    def _map_confidence_label(confidence: int) -> str:
        if confidence >= 8:
            return "VERY HIGH"
        elif confidence >= 6:
            return "HIGH CONVICTION"
        elif confidence >= 4:
            return "MEDIUM"
        else:
            return "LOW"
