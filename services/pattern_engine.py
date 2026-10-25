"""
IDX AI Signal Bot - Chart Pattern Engine
Detects classic chart patterns from OHLCV data.
"""

import logging
from typing import Dict, Any, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PatternEngine:
    """
    Detects chart patterns from OHLCV data.
    Active patterns (valid in 60-day window):
    - Bull/Bear Flag (20 bars)
    - Ascending/Descending Channel (40 bars)
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.close = df["close"]
        self.high = df["high"]
        self.low = df["low"]

    def detect_all(self) -> Dict[str, Any]:
        """Run all chart pattern detections.

        Active patterns (valid in 60-day window):
        - Bull/Bear Flag (lookback: 20 bars)
        - Ascending/Descending Channel (lookback: 40 bars)
        """
        patterns_found: List[str] = []
        result = {
            "patterns": patterns_found,
            "pattern_score": 0,
            "pattern_bias": "neutral",
        }

        detections = [
            self._detect_flag_pennant,
            self._detect_channel,
        ]

        bullish_score = 0
        bearish_score = 0

        for detect_fn in detections:
            try:
                detection = detect_fn()
                if detection["detected"]:
                    patterns_found.append(detection["name"])
                    if detection["bias"] == "bullish":
                        bullish_score += detection["score"]
                    elif detection["bias"] == "bearish":
                        bearish_score += detection["score"]
            except Exception as e:
                logger.debug(f"Pattern detection error in {detect_fn.__name__}: {e}")

        net_score = bullish_score - bearish_score
        result["pattern_score"] = net_score
        result["pattern_count"] = len(patterns_found)

        # Threshold lebih rendah karena hanya sedikit pola yang aktif
        if net_score > 0:
            result["pattern_bias"] = "bullish"
        elif net_score < 0:
            result["pattern_bias"] = "bearish"
        else:
            result["pattern_bias"] = "neutral"

        return result

    # ------------------------------------------------------------------ #
    #  Active Pattern Detectors (valid in 60-day window)
    # ------------------------------------------------------------------ #

    def _detect_flag_pennant(self) -> Dict[str, Any]:
        """Detect Bull/Bear Flag pattern (lookback: 20 bars)."""
        if len(self.df) < 20:
            return {"detected": False, "name": "Flag", "bias": "neutral", "score": 0}

        # Check for strong move (pole) followed by consolidation (flag)
        recent = self.df.tail(20)
        pole = recent.head(8)
        flag = recent.tail(10)

        pole_move = (pole["close"].iloc[-1] - pole["close"].iloc[0]) / pole["close"].iloc[0]
        flag_range = (flag["high"].max() - flag["low"].min()) / flag["close"].mean()

        if abs(pole_move) > 0.05 and flag_range < 0.04:
            bias = "bullish" if pole_move > 0 else "bearish"
            name = "Bull Flag" if bias == "bullish" else "Bear Flag"
            return {"detected": True, "name": name, "bias": bias, "score": 5}

        return {"detected": False, "name": "Flag", "bias": "neutral", "score": 0}

    def _detect_channel(self) -> Dict[str, Any]:
        """Detect price channel — ascending/descending (lookback: 40 bars)."""
        if len(self.df) < 30:
            return {"detected": False, "name": "Channel", "bias": "neutral", "score": 0}

        window = min(40, len(self.df))
        recent = self.df.tail(window)

        # Linear regression on highs and lows
        x = np.arange(len(recent))
        high_slope = np.polyfit(x, recent["high"].values, 1)[0]
        low_slope = np.polyfit(x, recent["low"].values, 1)[0]

        # Parallel slopes indicate a channel
        avg_price = recent["close"].mean()
        slope_diff = abs(high_slope - low_slope) / avg_price

        if slope_diff < 0.001:  # Nearly parallel
            if high_slope > 0 and low_slope > 0:
                return {"detected": True, "name": "Ascending Channel", "bias": "bullish", "score": 4}
            elif high_slope < 0 and low_slope < 0:
                return {"detected": True, "name": "Descending Channel", "bias": "bearish", "score": 4}

        return {"detected": False, "name": "Channel", "bias": "neutral", "score": 0}
