"""
IDX AI Signal Bot - Risk Engine
Calculates entry price, take profit targets, and stop loss levels
based on ATR (Average True Range). Rounds to IDX tick sizes.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class RiskLevels:
    """Calculated risk management levels."""
    entry_price: float
    tp1: float
    tp2: float = 0
    tp3: float = 0
    stop_loss_atr: float = 0
    stop_loss_moderate: float = 0
    stop_loss_conservative: float = 0
    risk_reward_ratio: float = 0
    atr_value: float = 0
    fib_levels: Optional[dict] = None  # Fibonacci levels (populated for WATCHLIST signals)


class RiskEngine:
    """
    Calculates entry price, take profit targets, and stop loss levels.
    Uses ATR-based calculations with IDX tick size rounding.
    """

    # IDX Tick Size Rules (per January 2014 regulation)
    # Price Range → Tick Size
    TICK_SIZES = [
        (200, 1),
        (500, 2),
        (2000, 5),
        (5000, 10),
        (float("inf"), 25),
    ]

    def calculate(
        self,
        close: float,
        atr: float,
        signal: str = "BUY",
        support: Optional[float] = None,
        resistance: Optional[float] = None,
    ) -> RiskLevels:
        """
        Calculate risk management levels.

        Args:
            close: Current closing price
            atr: ATR(14) value
            signal: "BUY" or "SELL"
            support: Nearest support level (optional)
            resistance: Nearest resistance level (optional)
        """
        if atr <= 0:
            atr = close * 0.02  # Default 2% if ATR unavailable

        entry = close

        # BUY/LONG rules — targets above, stops below
        # TP1 diperlebar ke 2.5x ATR untuk meningkatkan Risk:Reward secara struktural
        # TP2 ke 3.5x, TP3 ke 5.5x untuk momentum dan swing runner
        tp1 = entry + (2.5 * atr)
        tp2 = entry + (3.5 * atr)
        tp3 = entry + (5.5 * atr)

        # SL levels: Default ATR, Moderat (-5%), Konservatif (-3%)
        sl_atr = entry - (3.0 * atr if atr < 5 else 2.0 * atr)
        sl_moderate = entry * 0.95
        sl_conservative = entry * 0.97


        # Round all to IDX tick sizes
        entry = self._round_tick(entry)
        tp1 = self._round_tick(tp1)
        tp2 = self._round_tick(tp2)
        tp3 = self._round_tick(tp3)
        sl_atr = self._round_tick(sl_atr)
        sl_moderate = self._round_tick(sl_moderate)
        sl_conservative = self._round_tick(sl_conservative)

        # Risk/Reward ratio (using TP1 and conservative SL)
        risk = abs(entry - sl_conservative) if sl_conservative else abs(entry - sl_atr)
        reward = abs(tp1 - entry)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0

        return RiskLevels(
            entry_price=entry,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            stop_loss_atr=sl_atr,
            stop_loss_moderate=sl_moderate,
            stop_loss_conservative=sl_conservative,
            risk_reward_ratio=rr_ratio,
            atr_value=round(atr, 2),
        )

    def calculate_fibonacci(
        self,
        swing_low: float,
        swing_high: float,
    ) -> dict:
        """
        Calculate Fibonacci retracement and extension levels.

        Retracement levels (from swing_high to swing_low):
          - 0.236, 0.382, 0.5, 0.618 (golden ratio — entry)
        Extension levels (beyond swing_high):
          - 1.0, 1.272, 1.618 (golden extension — TP)

        For WATCHLIST:
          entry  = retracement 0.618 (harga sudah koreksi ke level support kuat)
          tp     = extension 1.618  (target ekspansi setelah reversal)
        """
        diff = swing_high - swing_low
        if diff <= 0:
            return {}

        retracements = {
            "fib_0": self._round_tick(swing_high),
            "fib_0236": self._round_tick(swing_high - 0.236 * diff),
            "fib_0382": self._round_tick(swing_high - 0.382 * diff),
            "fib_05": self._round_tick(swing_high - 0.5 * diff),
            "fib_0618": self._round_tick(swing_high - 0.618 * diff),  # Entry WATCHLIST
            "fib_0786": self._round_tick(swing_high - 0.786 * diff),
            "fib_1": self._round_tick(swing_low),
        }

        extensions = {
            "fib_1272": self._round_tick(swing_low + 1.272 * diff),
            "fib_1618": self._round_tick(swing_low + 1.618 * diff),  # TP WATCHLIST
            "fib_2618": self._round_tick(swing_low + 2.618 * diff),
        }

        return {
            **retracements,
            **extensions,
            "swing_low": self._round_tick(swing_low),
            "swing_high": self._round_tick(swing_high),
            "entry_fib": retracements["fib_0618"],
            "tp_fib": extensions["fib_1618"],
        }

    def _round_tick(self, price: float) -> float:
        """Round price to the nearest valid IDX tick size."""
        if price <= 0:
            return 0

        tick = self._get_tick_size(price)
        return round(price / tick) * tick

    def _get_tick_size(self, price: float) -> int:
        """Get IDX tick size for a given price level."""
        for threshold, tick in self.TICK_SIZES:
            if price < threshold:
                return tick
        return 25

    def _find_nearest_swing_low(self, ohlcv_df: pd.DataFrame, lookback: int) -> Optional[float]:
        """
        Temukan swing low terdekat dalam N bar terakhir.
        Swing low = bar dengan low lebih rendah dari 2 bar sebelum & sesudahnya.
        """
        recent = ohlcv_df.tail(lookback).reset_index(drop=True)
        swing_lows = []
        for i in range(2, len(recent) - 2):
            low_val = recent["low"].iloc[i]
            if (low_val < recent["low"].iloc[i - 1] and
                    low_val < recent["low"].iloc[i - 2] and
                    low_val < recent["low"].iloc[i + 1] and
                    low_val < recent["low"].iloc[i + 2]):
                swing_lows.append(low_val)
        # Ambil swing low terdekat (terbesar di antara swing lows, paling dekat ke harga saat ini)
        if swing_lows:
            close = ohlcv_df["close"].iloc[-1]
            # Pilih swing low yang paling dekat di bawah harga sekarang
            valid = [sl for sl in swing_lows if sl < close]
            if valid:
                return max(valid)  # Swing low terdekat (tertinggi) di bawah close
        return None

    def _find_nearest_swing_high(self, ohlcv_df: pd.DataFrame, lookback: int) -> Optional[float]:
        """
        Temukan swing high terdekat dalam N bar terakhir.
        Swing high = bar dengan high lebih tinggi dari 2 bar sebelum & sesudahnya.
        """
        recent = ohlcv_df.tail(lookback).reset_index(drop=True)
        swing_highs = []
        for i in range(2, len(recent) - 2):
            high_val = recent["high"].iloc[i]
            if (high_val > recent["high"].iloc[i - 1] and
                    high_val > recent["high"].iloc[i - 2] and
                    high_val > recent["high"].iloc[i + 1] and
                    high_val > recent["high"].iloc[i + 2]):
                swing_highs.append(high_val)
        if swing_highs:
            close = ohlcv_df["close"].iloc[-1]
            # Pilih swing high terdekat di atas harga sekarang
            valid = [sh for sh in swing_highs if sh > close]
            if valid:
                return min(valid)  # Swing high terdekat (terendah) di atas close
        return None

    def calculate_from_ohlcv(
        self,
        ohlcv_df: pd.DataFrame,
        signal: str = "BUY",
        atr_period: int = 14,
    ) -> RiskLevels:
        """
        Calculate risk levels directly from OHLCV DataFrame.

        Args:
            ohlcv_df: DataFrame with [high, low, close] columns
            signal: Signal type
            atr_period: ATR calculation period
        """
        close = ohlcv_df["close"].iloc[-1]

        # Calculate ATR
        high = ohlcv_df["high"]
        low = ohlcv_df["low"]
        prev_close = ohlcv_df["close"].shift(1)

        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)

        atr = tr.rolling(window=atr_period).mean().iloc[-1]
        if pd.isna(atr):
            atr = close * 0.02

        # --- FIX #3: Gunakan swing pivot terdekat (20 bar), bukan 50-bar low/high
        # Ini menghasilkan support/resistance yang lebih relevan & SL lebih ketat
        pivot_lookback = min(20, len(ohlcv_df))
        recent_pivot = ohlcv_df.tail(pivot_lookback)
        support = self._find_nearest_swing_low(ohlcv_df, pivot_lookback)
        resistance = self._find_nearest_swing_high(ohlcv_df, pivot_lookback)

        # Fallback ke min/max jika swing pivot tidak ditemukan
        if support is None:
            support = recent_pivot["low"].min()
        if resistance is None:
            resistance = recent_pivot["high"].max()

        levels = self.calculate(
            close=close,
            atr=atr,
            signal=signal,
            support=support,
            resistance=resistance,
        )

        # SL levels: Default ATR, Moderat (-5%), Konservatif (-3%)
        levels.stop_loss_moderate = self._round_tick(close * 0.95)
        levels.stop_loss_conservative = self._round_tick(close * 0.97)
        levels.stop_loss_atr = self._round_tick(close - (3.0 * atr if atr < 5 else 2.0 * atr))


        # Recompute R:R setelah cap
        risk = abs(levels.entry_price - levels.stop_loss_conservative)
        reward = abs(levels.tp1 - levels.entry_price)
        levels.risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0

        # --- WATCHLIST: tetap menggunakan Fibonacci 0.618 (entry) / 1.618 (TP)
        if signal == "WATCHLIST":
            # Gunakan swing pivot terdekat terlebih dahulu untuk menangkap struktur pantulan (Higher Low)
            fib_lookback = min(50, len(ohlcv_df))
            fib_recent = ohlcv_df.tail(fib_lookback)
            
            fib_support = self._find_nearest_swing_low(ohlcv_df, fib_lookback)
            fib_resistance = self._find_nearest_swing_high(ohlcv_df, fib_lookback)
            
            # Fallback ke absolute min/max jika struktur swing tidak ditemukan
            if fib_support is None:
                fib_support = fib_recent["low"].min()
            if fib_resistance is None:
                fib_resistance = fib_recent["high"].max()
            fib = self.calculate_fibonacci(swing_low=fib_support, swing_high=fib_resistance)
            if fib and fib["entry_fib"] > 0:
                fib_entry = fib["entry_fib"]
                fib_tp = fib["tp_fib"]

                # Check if current close is below Fibonacci 0.618 entry level
                is_below_fib = close < fib_entry

                # Option 2 (Confirmation) stop loss
                sl_atr = self._round_tick(fib_entry - (1.5 * atr))
                sl_moderate = self._round_tick(fib_entry - (2.0 * atr))
                sl_conservative = self._round_tick(fib_entry - (1.0 * atr))
                if fib_support and fib_support < fib_entry:
                    sl_conservative = max(sl_conservative, self._round_tick(fib_support * 0.99))
                # Cap SL 5% dari fib entry
                max_fib_sl = fib_entry * 0.05
                if (fib_entry - sl_conservative) > max_fib_sl:
                    sl_conservative = self._round_tick(fib_entry - max_fib_sl)

                # Option 1 (Discount) stop loss
                sl_atr_discount = self._round_tick(close - (1.5 * atr))
                sl_moderate_discount = self._round_tick(close - (2.0 * atr))
                sl_conservative_discount = self._round_tick(close - (1.0 * atr))
                if fib_support and fib_support < close:
                    sl_conservative_discount = max(sl_conservative_discount, self._round_tick(fib_support * 0.99))
                # Cap SL 5% dari close
                max_close_sl = close * 0.05
                if (close - sl_conservative_discount) > max_close_sl:
                    sl_conservative_discount = self._round_tick(close - max_close_sl)

                # Save values into the fib levels dict
                fib["is_below_fib"] = is_below_fib
                fib["entry_discount"] = close
                fib["sl_discount"] = sl_conservative_discount
                fib["entry_confirm"] = fib_entry
                fib["sl_confirm"] = sl_conservative

                risk = abs(fib_entry - sl_conservative) if sl_conservative else abs(fib_entry - sl_atr)
                reward = abs(fib_tp - fib_entry)
                rr_ratio = round(reward / risk, 2) if risk > 0 else 0

                levels.entry_price = fib_entry
                levels.tp1 = fib_tp
                levels.tp2 = fib.get("fib_2618", fib_tp)
                levels.stop_loss_atr = sl_atr
                levels.stop_loss_moderate = sl_moderate
                levels.stop_loss_conservative = sl_conservative
                levels.risk_reward_ratio = rr_ratio
                levels.fib_levels = fib
                logger.info(
                    f"[RiskEngine] WATCHLIST Fibonacci — entry: {fib_entry}, "
                    f"tp(1.618): {fib_tp}, swing_low: {fib_support:.0f}, swing_high: {fib_resistance:.0f}, "
                    f"is_below_fib: {is_below_fib}"
                )

        return levels

    def to_dict(self, levels: RiskLevels) -> Dict[str, Any]:
        """Convert RiskLevels to dictionary for JSON serialization."""
        d = {
            "entry_price": levels.entry_price,
            "tp1": levels.tp1,
            "tp2": levels.tp2,
            "tp3": levels.tp3,
            "stop_loss_atr": levels.stop_loss_atr,
            "stop_loss_moderate": levels.stop_loss_moderate,
            "stop_loss_conservative": levels.stop_loss_conservative,
            "risk_reward_ratio": levels.risk_reward_ratio,
            "atr_value": levels.atr_value,
        }
        if levels.fib_levels:
            d["fib_levels"] = levels.fib_levels  # type: ignore[assignment]
        return d
