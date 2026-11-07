"""
IDX AI Signal Bot - Technical Analysis Engine
Computes all technical indicators using pandas-ta.
Returns standardized dict for the scoring engine.
"""

import logging
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalEngine:
    """
    Computes technical indicators from OHLCV data.
    All indicators are deterministic — no LLM involvement.
    """

    def __init__(self, df: pd.DataFrame, ihsg_df: Optional[pd.DataFrame] = None):
        """
        Args:
            df: OHLCV DataFrame with columns [date, open, high, low, close, volume]
                Must be sorted by date ascending.
            ihsg_df: Optional IHSG OHLCV DataFrame for Beta computation.
        """
        self.df = df.copy()
        self.ihsg_df = ihsg_df.copy() if ihsg_df is not None else None
        self._validate()

    def _validate(self):
        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            if col not in self.df.columns:
                raise ValueError(f"Missing required column: {col}")
        if len(self.df) < 30:
            logger.warning(f"Only {len(self.df)} rows — some indicators may be unreliable")

    # ------------------------------------------------------------------ #
    #  Moving Averages
    # ------------------------------------------------------------------ #

    def compute_ema(self, periods: Optional[list] = None) -> Dict[str, float]:
        """Compute Exponential Moving Averages.
        
        Window 60-hari: EMA10/EMA20/EMA50 digunakan sebagai hierarki utama.
        EMA200 dihapus dari alignment check (butuh 200+ hari untuk konverge).
        """
        if periods is None:
            # EMA10 ditambahkan, EMA200 tetap dihitung tapi tidak dipakai untuk alignment
            periods = [5, 9, 10, 20, 21, 50, 100]

        result = {}
        close = self.df["close"]
        current_price = close.iloc[-1]
        data_len = len(self.df)

        for p in periods:
            if data_len >= p:
                ema = close.ewm(span=p, adjust=False).mean()
                result[f"ema_{p}"] = round(ema.iloc[-1], 2)
                result[f"ema_{p}_slope"] = round(ema.iloc[-1] - ema.iloc[-2], 2)
            else:
                result[f"ema_{p}"] = None
                result[f"ema_{p}_slope"] = None

        # Alignment check: EMA10 > EMA20 > EMA50 (valid di 60-day window)
        # EMA50 hanya dianggap valid jika data >= 55 hari (warm-up ~100 bar untuk fully converge)
        ema10 = result.get("ema_10")
        ema20 = result.get("ema_20")
        ema50 = result.get("ema_50")

        if ema10 and ema20 and ema50 and data_len >= 55:
            # Full alignment dengan EMA50 tervalidasi
            result["ema_alignment_bullish"] = ema10 > ema20 > ema50
            result["ema_alignment_bearish"] = ema10 < ema20 < ema50
        elif ema10 and ema20:
            # Partial alignment: hanya EMA10 vs EMA20 (data < 55 hari)
            result["ema_alignment_bullish"] = ema10 > ema20
            result["ema_alignment_bearish"] = ema10 < ema20
        else:
            result["ema_alignment_bullish"] = False
            result["ema_alignment_bearish"] = False

        result["price_above_ema20"] = bool(ema20 and current_price > ema20)
        result["price_above_ema50"] = bool(ema50 and current_price > ema50)
        result["price_above_ema10"] = bool(ema10 and current_price > ema10)
        # EMA200 tidak dihitung, set False agar kode lama tidak error
        result["price_above_ema200"] = False

        return result

    # ------------------------------------------------------------------ #
    #  RSI
    # ------------------------------------------------------------------ #

    def compute_rsi(self, period: int = 14) -> Dict[str, Any]:
        """Compute Relative Strength Index."""
        close = self.df["close"]
        delta = close.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        # Handle zero loss (runaway uptrend -> RSI 100) vs zero gain (runaway downtrend -> RSI 0)
        rsi = rsi.fillna(pd.Series(np.where(avg_gain > 0, 100.0, 50.0), index=close.index))

        current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0

        # Deteksi 4 kondisi khusus RSI:
        # 1. RSI > 80 konsisten selama 4 periode
        # 2. RSI > 80 lalu ada pembalikan arah ke < 80
        # 3. RSI < 30 konsisten selama 4 periode
        # 4. RSI < 30 lalu ada pembalikan arah ke > 30
        rsi_clean = rsi.dropna()
        rsi_last_4 = [round(float(x), 2) for x in rsi_clean.iloc[-4:]] if len(rsi_clean) >= 4 else []
        rsi_prev = round(float(rsi_clean.iloc[-2]), 2) if len(rsi_clean) > 1 else None

        rsi_consistent_above_80 = (len(rsi_last_4) == 4 and all(x > 80.0 for x in rsi_last_4))

        rsi_reversal_down_from_80 = False
        if len(rsi_clean) >= 2:
            if current_rsi < 80.0 and (
                (rsi_prev is not None and rsi_prev >= 80.0) or
                (len(rsi_clean) >= 3 and any(x >= 80.0 for x in rsi_clean.iloc[-3:-1]) and current_rsi < rsi_clean.iloc[-2])
            ):
                rsi_reversal_down_from_80 = True

        rsi_consistent_below_30 = (len(rsi_last_4) == 4 and all(x < 30.0 for x in rsi_last_4))

        rsi_reversal_up_from_30 = False
        if len(rsi_clean) >= 2:
            if current_rsi > 30.0 and (
                (rsi_prev is not None and rsi_prev <= 30.0) or
                (len(rsi_clean) >= 3 and any(x <= 30.0 for x in rsi_clean.iloc[-3:-1]) and current_rsi > rsi_clean.iloc[-2])
            ):
                rsi_reversal_up_from_30 = True

        return {
            "rsi": round(current_rsi, 2),
            "rsi_prev": rsi_prev,
            "rsi_last_4": rsi_last_4,
            "rsi_consistent_above_80": rsi_consistent_above_80,
            "rsi_reversal_down_from_80": rsi_reversal_down_from_80,
            "rsi_consistent_below_30": rsi_consistent_below_30,
            "rsi_reversal_up_from_30": rsi_reversal_up_from_30,
            "rsi_overbought": current_rsi > 70,
            "rsi_oversold": current_rsi < 30,
            "rsi_bullish_zone": 40 <= current_rsi <= 60,
            "rsi_divergence": self._check_rsi_divergence(rsi),
        }

    def _check_rsi_divergence(self, rsi: pd.Series) -> Optional[str]:
        """Check for bullish/bearish RSI divergence."""
        if len(self.df) < 20:
            return None

        close = self.df["close"]
        lookback = 14

        close_recent = close.iloc[-lookback:]
        rsi_recent = rsi.iloc[-lookback:]

        # Bullish divergence: price making lower low, RSI making higher low
        if close_recent.iloc[-1] < close_recent.min() * 1.02:
            if rsi_recent.iloc[-1] > rsi_recent.min() * 1.05:
                return "bullish"

        # Bearish divergence: price making higher high, RSI making lower high
        if close_recent.iloc[-1] > close_recent.max() * 0.98:
            if rsi_recent.iloc[-1] < rsi_recent.max() * 0.95:
                return "bearish"

        return None

    # ------------------------------------------------------------------ #
    #  MACD
    # ------------------------------------------------------------------ #

    def compute_macd(
        self, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, Any]:
        """Compute MACD, Signal Line, and Histogram."""
        close = self.df["close"]

        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        macd_val = macd_line.iloc[-1]
        signal_val = signal_line.iloc[-1]
        hist_val = histogram.iloc[-1]

        # Crossover detection
        bullish_cross = (
            macd_line.iloc[-1] > signal_line.iloc[-1]
            and macd_line.iloc[-2] <= signal_line.iloc[-2]
        ) if len(macd_line) > 1 else False

        bearish_cross = (
            macd_line.iloc[-1] < signal_line.iloc[-1]
            and macd_line.iloc[-2] >= signal_line.iloc[-2]
        ) if len(macd_line) > 1 else False

        return {
            "macd": round(macd_val, 2),
            "macd_signal": round(signal_val, 2),
            "macd_histogram": round(hist_val, 2),
            "macd_bullish_cross": bullish_cross,
            "macd_bearish_cross": bearish_cross,
            "macd_above_zero": macd_val > 0,
            "macd_histogram_rising": (
                hist_val > histogram.iloc[-2] if len(histogram) > 1 else False
            ),
        }

    # ------------------------------------------------------------------ #
    #  Bollinger Bands
    # ------------------------------------------------------------------ #

    def compute_bollinger(self, period: int = 20, std_dev: float = 2.0) -> Dict[str, Any]:
        """Compute Bollinger Bands."""
        close = self.df["close"]
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()

        upper = sma + std_dev * std
        lower = sma - std_dev * std

        current_price = close.iloc[-1]
        bb_upper = upper.iloc[-1]
        bb_lower = lower.iloc[-1]
        bb_middle = sma.iloc[-1]

        # %B — position within bands
        bb_width = bb_upper - bb_lower
        percent_b = (current_price - bb_lower) / bb_width if bb_width > 0 else 0.5

        return {
            "bb_upper": round(bb_upper, 2),
            "bb_middle": round(bb_middle, 2),
            "bb_lower": round(bb_lower, 2),
            "bb_width": round(bb_width, 2),
            "bb_percent_b": round(percent_b, 4),
            "bb_squeeze": bb_width < close.iloc[-1] * 0.03,  # Tight squeeze
            "price_above_upper_bb": current_price > bb_upper,
            "price_below_lower_bb": current_price < bb_lower,
        }

    # ------------------------------------------------------------------ #
    #  Stochastic Oscillator
    # ------------------------------------------------------------------ #

    def compute_stochastic(self, k_period: int = 14, d_period: int = 3) -> Dict[str, Any]:
        """Compute Stochastic %K and %D."""
        high = self.df["high"]
        low = self.df["low"]
        close = self.df["close"]

        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()

        denom = highest_high - lowest_low
        k = 100 * (close - lowest_low) / denom.replace(0, np.nan)
        d = k.rolling(window=d_period).mean()

        k_val = k.iloc[-1] if not pd.isna(k.iloc[-1]) else 50.0
        d_val = d.iloc[-1] if not pd.isna(d.iloc[-1]) else 50.0

        return {
            "stoch_k": round(k_val, 2),
            "stoch_d": round(d_val, 2),
            "stoch_overbought": k_val > 80,
            "stoch_oversold": k_val < 20,
            "stoch_bullish_cross": (
                k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]
            ) if len(k) > 1 else False,
        }

    # ------------------------------------------------------------------ #
    #  ATR (Average True Range)
    # ------------------------------------------------------------------ #

    def compute_atr(self, period: int = 14) -> Dict[str, Any]:
        """Compute Average True Range for volatility & risk management."""
        high = self.df["high"]
        low = self.df["low"]
        close = self.df["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()
        atr_val = atr.iloc[-1]
        current_price = close.iloc[-1]

        return {
            "atr": round(atr_val, 2) if not pd.isna(atr_val) else 0,
            "atr_percent": round((atr_val / current_price) * 100, 2) if current_price > 0 and not pd.isna(atr_val) else 0,
            "atr_expanding": (
                atr.iloc[-1] > atr.iloc[-5] if len(atr) > 5 else False
            ),
        }

    # ------------------------------------------------------------------ #
    #  ADX (Average Directional Index)
    # ------------------------------------------------------------------ #

    def compute_adx(self, period: int = 14) -> Dict[str, Any]:
        """Compute ADX for trend strength."""
        high = self.df["high"]
        low = self.df["low"]
        close = self.df["close"]

        # +DM / -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        # TR
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr.replace(0, np.nan))
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr.replace(0, np.nan))

        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
        adx = dx.rolling(window=period).mean()

        adx_val = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0

        return {
            "adx": round(adx_val, 2),
            "plus_di": round(plus_di.iloc[-1], 2) if not pd.isna(plus_di.iloc[-1]) else 0,
            "minus_di": round(minus_di.iloc[-1], 2) if not pd.isna(minus_di.iloc[-1]) else 0,
            "adx_trending": adx_val > 25,
            "adx_strong_trend": adx_val > 40,
            "adx_no_trend": adx_val < 15,
            "di_bullish": plus_di.iloc[-1] > minus_di.iloc[-1] if not pd.isna(plus_di.iloc[-1]) else False,
        }

    # ------------------------------------------------------------------ #
    #  OBV (On Balance Volume)
    # ------------------------------------------------------------------ #

    def compute_obv(self) -> Dict[str, Any]:
        """Compute On Balance Volume."""
        close = self.df["close"]
        volume = self.df["volume"]

        direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        obv = (volume * direction).cumsum()

        # OBV trend — compare OBV SMA20 slope
        obv_sma = obv.rolling(window=20).mean()
        obv_rising = obv_sma.iloc[-1] > obv_sma.iloc[-5] if len(obv_sma) > 5 else False

        # Price-OBV divergence
        price_up = close.iloc[-1] > close.iloc[-10] if len(close) > 10 else False
        obv_up = obv.iloc[-1] > obv.iloc[-10] if len(obv) > 10 else False

        return {
            "obv": int(obv.iloc[-1]),
            "obv_rising": obv_rising,
            "obv_divergence_bullish": not price_up and obv_up,
            "obv_divergence_bearish": price_up and not obv_up,
        }

    # ------------------------------------------------------------------ #
    #  Volume Analysis
    # ------------------------------------------------------------------ #

    def compute_volume_analysis(self) -> Dict[str, Any]:
        """Analyze volume patterns."""
        volume = self.df["volume"]
        close = self.df["close"]

        # Average volume 20 hari
        vol_sma_20 = volume.rolling(window=20).mean()
        current_vol = volume.iloc[-1]
        avg_vol_20 = vol_sma_20.iloc[-1] if not pd.isna(vol_sma_20.iloc[-1]) else volume.mean()

        # Average volume 5 hari
        vol_sma_5 = volume.rolling(window=5).mean()
        avg_vol_5 = vol_sma_5.iloc[-1] if len(volume) >= 5 and not pd.isna(vol_sma_5.iloc[-1]) else current_vol

        # Ratio current vs avg 20 hari
        vol_ratio = current_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

        # Volume breakout: current volume >= 2x average 20 hari
        vol_breakout = vol_ratio >= 2.0

        # Volume dry-up: current volume < 0.5x average
        vol_dry = vol_ratio < 0.5

        # Volume trend: avg 5 hari > avg 20 hari (volume sedang meningkat)
        vol_5_above_20 = avg_vol_5 > avg_vol_20

        # Volume increasing (legacy: 5-bar recent vs 5-10 bars older)
        recent_avg = volume.tail(5).mean()
        older_avg = volume.iloc[-10:-5].mean() if len(volume) >= 10 else volume.mean()
        vol_increasing = recent_avg > older_avg * 1.1

        # Cek apakah volume besar ini buying atau selling pressure
        current_close = close.iloc[-1]
        current_open = self.df["open"].iloc[-1] if "open" in self.df.columns else current_close
        is_bullish_candle = current_close > current_open
        is_bearish_candle = current_close < current_open

        vol_is_buying = vol_ratio >= 1.3 and is_bullish_candle
        vol_is_selling = vol_ratio >= 1.3 and is_bearish_candle

        # 5-day volume percentage and label
        vol_5d_pct = round((current_vol / avg_vol_5) * 100, 1) if avg_vol_5 > 0 else 100.0
        if vol_5d_pct >= 200:
            vol_5d_label = f"Sangat Tinggi ({vol_5d_pct:.0f}%) 🟢"
        elif vol_5d_pct >= 120:
            vol_5d_label = f"Tinggi ({vol_5d_pct:.0f}%) 🟢"
        elif vol_5d_pct >= 80:
            vol_5d_label = f"Normal ({vol_5d_pct:.0f}%) ⚪"
        elif vol_5d_pct >= 40:
            vol_5d_label = f"Rendah ({vol_5d_pct:.0f}%) 🟡"
        else:
            vol_5d_label = f"Sangat Rendah ({vol_5d_pct:.0f}%) 🔴"

        return {
            "volume_current": int(current_vol),
            "volume_avg_20": int(avg_vol_20),
            "volume_avg_5": int(avg_vol_5),
            "volume_ratio": round(vol_ratio, 2),
            "volume_vs_5d_pct": vol_5d_pct,
            "volume_5d_label": vol_5d_label,
            "volume_breakout": vol_breakout,           # >= 2x avg20
            "volume_dry_up": vol_dry,
            "volume_increasing": vol_increasing,
            "volume_5_above_20": vol_5_above_20,        # avg5 > avg20 (tren volume naik)
            "volume_is_buying": vol_is_buying,
            "volume_is_selling": vol_is_selling,
        }


    # ------------------------------------------------------------------ #
    #  VWAP (Volume Weighted Average Price)
    # ------------------------------------------------------------------ #

    def compute_vwap(self) -> Dict[str, Any]:
        """Compute VWAP (Volume Weighted Average Price) which resets daily for intraday data."""
        df = self.df.copy()
        
        # Calculate Typical Price
        tp = (df["high"] + df["low"] + df["close"]) / 3
        tp_vol = tp * df["volume"]
        
        # Convert date column to dates to group by
        try:
            dates = pd.to_datetime(df["date"]).dt.date
        except Exception:
            dates = df["date"]
            
        df["_tp_vol"] = tp_vol
        df["_date_only"] = dates
        
        # Cumulative Typical Price * Volume and Cumulative Volume grouped by date
        cum_tp_vol = df.groupby("_date_only")["_tp_vol"].cumsum()
        cum_vol = df.groupby("_date_only")["volume"].cumsum()
        
        # Handle zero division
        vwap = cum_tp_vol / cum_vol.replace(0, np.nan)
        vwap = vwap.fillna(tp)
        
        current_vwap = vwap.iloc[-1]
        current_price = df["close"].iloc[-1]
        
        return {
            "vwap": round(current_vwap, 2),
            "price_above_vwap": bool(current_price > current_vwap),
            "vwap_slope": round(vwap.iloc[-1] - vwap.iloc[-2], 2) if len(vwap) > 1 else 0.0
        }

    # ------------------------------------------------------------------ #
    #  Master Compute — runs ALL indicators
    # ------------------------------------------------------------------ #

    def compute_all(self) -> Dict[str, Any]:
        """Compute all technical indicators and return unified dict."""
        result = {}

        try:
            result.update(self.compute_ema())
        except Exception as e:
            logger.error(f"EMA error: {e}")

        try:
            result.update(self.compute_rsi())
        except Exception as e:
            logger.error(f"RSI error: {e}")

        try:
            result.update(self.compute_macd())
        except Exception as e:
            logger.error(f"MACD error: {e}")

        try:
            result.update(self.compute_bollinger())
        except Exception as e:
            logger.error(f"Bollinger error: {e}")

        try:
            result.update(self.compute_stochastic())
        except Exception as e:
            logger.error(f"Stochastic error: {e}")

        try:
            result.update(self.compute_atr())
        except Exception as e:
            logger.error(f"ATR error: {e}")

        try:
            result.update(self.compute_adx())
        except Exception as e:
            logger.error(f"ADX error: {e}")

        try:
            result.update(self.compute_obv())
        except Exception as e:
            logger.error(f"OBV error: {e}")

        try:
            result.update(self.compute_volume_analysis())
        except Exception as e:
            logger.error(f"Volume error: {e}")

        try:
            result.update(self.compute_vwap())
        except Exception as e:
            logger.error(f"VWAP error: {e}")

        try:
            result.update(self.compute_beta_and_volatility())
        except Exception as e:
            logger.error(f"Beta and Volatility error: {e}")

        logger.info(f"Computed {len(result)} technical indicators")
        return result

    # ------------------------------------------------------------------ #
    #  Beta and Volatility Analysis
    # ------------------------------------------------------------------ #

    def compute_beta_and_volatility(self) -> Dict[str, Any]:
        """Compute annualized volatility and beta relative to IHSG (^JKSE)."""
        close = self.df["close"]
        returns = close.pct_change().dropna()
        if len(returns) >= 5 and returns.std() > 0:
            ann_vol = float(returns.std() * np.sqrt(252) * 100)
        else:
            ann_vol = 0.0

        beta = 1.0
        if (
            self.ihsg_df is not None
            and len(self.ihsg_df) >= 10
            and "date" in self.df.columns
            and "date" in self.ihsg_df.columns
        ):
            try:
                s_df = self.df[["date", "close"]].copy()
                s_df["date"] = pd.to_datetime(s_df["date"]).dt.date
                s_df["s_ret"] = s_df["close"].pct_change()

                i_df = self.ihsg_df[["date", "close"]].copy()
                i_df["date"] = pd.to_datetime(i_df["date"]).dt.date
                i_df["i_ret"] = i_df["close"].pct_change()

                merged = pd.merge(s_df, i_df, on="date").dropna()
                if len(merged) >= 10 and merged["i_ret"].var() > 0:
                    cov = merged["s_ret"].cov(merged["i_ret"])
                    var = merged["i_ret"].var()
                    beta = float(cov / var)
                elif ann_vol > 0:
                    beta = max(0.5, round(ann_vol / 43.0, 2))
            except Exception as e:
                logger.debug(f"Beta calculation error: {e}")
                if ann_vol > 0:
                    beta = max(0.5, round(ann_vol / 43.0, 2))
        elif ann_vol > 0:
            beta = max(0.5, round(ann_vol / 43.0, 2))

        beta = round(beta, 2)
        if beta >= 1.5:
            beta_label = "Very High"
        elif beta >= 1.1:
            beta_label = "High"
        elif beta >= 0.8:
            beta_label = "Moderate"
        elif beta > 0:
            beta_label = "Low"
        else:
            beta_label = "Negative"

        return {
            "volatility": round(ann_vol, 1),
            "beta": beta,
            "beta_label": beta_label,
        }

