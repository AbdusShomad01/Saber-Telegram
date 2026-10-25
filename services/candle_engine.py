"""
IDX AI Signal Bot - Candlestick Pattern Engine
Detects Japanese candlestick patterns from OHLCV data.
"""

import logging
from typing import Dict, Any, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CandleEngine:
    """
    Detects candlestick patterns:
    Engulfing, Doji, Hammer, Shooting Star, Morning Star,
    Evening Star, Harami, Three White Soldiers, Three Black Crows.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.o = df["open"]
        self.h = df["high"]
        self.l = df["low"]
        self.c = df["close"]

    def detect_all(self) -> Dict[str, Any]:
        """Run all candlestick pattern detections."""
        patterns_found: List[str] = []
        result = {
            "candle_patterns": patterns_found,
            "candle_score": 0,
            "candle_bias": "neutral",
        }

        if len(self.df) < 5:
            return result

        detections = [
            self._detect_bullish_engulfing,
            self._detect_bearish_engulfing,
            # Doji DIHAPUS: bias neutral (score 0) hanya menambah noise
            self._detect_hammer,
            self._detect_shooting_star,
            self._detect_morning_star,
            self._detect_evening_star,
            self._detect_bullish_harami,
            self._detect_bearish_harami,
            self._detect_three_white_soldiers,
            self._detect_three_black_crows,
            self._detect_dragonfly_doji,
            self._detect_gravestone_doji,
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
                logger.debug(f"Candle pattern error in {detect_fn.__name__}: {e}")

        net_score = bullish_score - bearish_score
        result["candle_score"] = net_score
        result["candle_count"] = len(patterns_found)

        if net_score > 2:
            result["candle_bias"] = "bullish"
        elif net_score < -2:
            result["candle_bias"] = "bearish"

        return result

    def _body_size(self, idx: int) -> float:
        return abs(self.c.iloc[idx] - self.o.iloc[idx])

    def _candle_range(self, idx: int) -> float:
        return self.h.iloc[idx] - self.l.iloc[idx]

    def _upper_shadow(self, idx: int) -> float:
        return self.h.iloc[idx] - max(self.o.iloc[idx], self.c.iloc[idx])

    def _lower_shadow(self, idx: int) -> float:
        return min(self.o.iloc[idx], self.c.iloc[idx]) - self.l.iloc[idx]

    def _is_bullish(self, idx: int) -> bool:
        return self.c.iloc[idx] > self.o.iloc[idx]

    def _is_bearish(self, idx: int) -> bool:
        return self.c.iloc[idx] < self.o.iloc[idx]

    def _avg_body_size(self, lookback: int = 10) -> float:
        bodies = [self._body_size(-i) for i in range(1, min(lookback + 1, len(self.df)))]
        return np.mean(bodies) if bodies else 1.0

    # ------------------------------------------------------------------ #
    #  Individual Pattern Detectors
    # ------------------------------------------------------------------ #

    def _detect_bullish_engulfing(self) -> Dict:
        i = -1
        if not self._is_bearish(-2) or not self._is_bullish(-1):
            return {"detected": False, "name": "Bullish Engulfing", "bias": "bullish", "score": 0}

        if (self.o.iloc[i] < self.c.iloc[i - 1] and
                self.c.iloc[i] > self.o.iloc[i - 1] and
                self._body_size(i) > self._body_size(i - 1) * 1.1):
            return {"detected": True, "name": "Bullish Engulfing", "bias": "bullish", "score": 5}

        return {"detected": False, "name": "Bullish Engulfing", "bias": "bullish", "score": 0}

    def _detect_bearish_engulfing(self) -> Dict:
        i = -1
        if not self._is_bullish(-2) or not self._is_bearish(-1):
            return {"detected": False, "name": "Bearish Engulfing", "bias": "bearish", "score": 0}

        if (self.o.iloc[i] > self.c.iloc[i - 1] and
                self.c.iloc[i] < self.o.iloc[i - 1] and
                self._body_size(i) > self._body_size(i - 1) * 1.1):
            return {"detected": True, "name": "Bearish Engulfing", "bias": "bearish", "score": 5}

        return {"detected": False, "name": "Bearish Engulfing", "bias": "bearish", "score": 0}

    def _detect_doji(self) -> Dict:
        i = -1
        body = self._body_size(i)
        rng = self._candle_range(i)

        if rng > 0 and body / rng < 0.1:
            return {"detected": True, "name": "Doji", "bias": "neutral", "score": 0}

        return {"detected": False, "name": "Doji", "bias": "neutral", "score": 0}

    def _is_near_support(self) -> bool:
        """
        Cek apakah candle terakhir berada di dekat area support.
        Support didefinisikan sebagai: harga di bawah/dekat lower Bollinger Band
        atau RSI di bawah 40 (area oversold/near-oversold).
        """
        try:
            close = self.c
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            lower_bb = sma20 - 2 * std20
            current_price = close.iloc[-1]
            current_lower_bb = lower_bb.iloc[-1]

            # Near lower BB: harga dalam 2% dari lower band
            near_lower_bb = current_price <= current_lower_bb * 1.02

            # RSI oversold
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.rolling(14).mean()
            avg_loss = loss.rolling(14).mean()
            rs = avg_gain / avg_loss.replace(0, float('nan'))
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
            near_oversold = current_rsi < 40

            return near_lower_bb or near_oversold
        except Exception:
            return False

    def _detect_hammer(self) -> Dict:
        """Hammer: small body at top, long lower shadow.
        Score ditingkatkan jika terjadi di dekat area support (near lower BB atau RSI < 40).
        """
        i = -1
        body = self._body_size(i)
        rng = self._candle_range(i)
        lower = self._lower_shadow(i)
        upper = self._upper_shadow(i)

        if rng == 0:
            return {"detected": False, "name": "Hammer", "bias": "bullish", "score": 0}

        if (body / rng < 0.3 and
                lower > body * 2 and
                upper < body * 0.5):
            # Bonus konteks posisi: Hammer di support lebih reliable
            score = 6 if self._is_near_support() else 3
            name = "Hammer at Support" if self._is_near_support() else "Hammer"
            return {"detected": True, "name": name, "bias": "bullish", "score": score}

        return {"detected": False, "name": "Hammer", "bias": "bullish", "score": 0}

    def _detect_shooting_star(self) -> Dict:
        """Shooting Star: small body at bottom, long upper shadow (bearish at resistance)."""
        i = -1
        body = self._body_size(i)
        rng = self._candle_range(i)
        lower = self._lower_shadow(i)
        upper = self._upper_shadow(i)

        if rng == 0:
            return {"detected": False, "name": "Shooting Star", "bias": "bearish", "score": 0}

        if (body / rng < 0.3 and
                upper > body * 2 and
                lower < body * 0.5):
            return {"detected": True, "name": "Shooting Star", "bias": "bearish", "score": 4}

        return {"detected": False, "name": "Shooting Star", "bias": "bearish", "score": 0}

    def _detect_morning_star(self) -> Dict:
        """Morning Star: 3-candle bullish reversal."""
        if len(self.df) < 3:
            return {"detected": False, "name": "Morning Star", "bias": "bullish", "score": 0}

        # Day 1: large bearish, Day 2: small body (gap down), Day 3: large bullish
        if (self._is_bearish(-3) and
                self._body_size(-3) > self._avg_body_size() * 0.8 and
                self._body_size(-2) < self._avg_body_size() * 0.3 and
                self._is_bullish(-1) and
                self._body_size(-1) > self._avg_body_size() * 0.8 and
                self.c.iloc[-1] > (self.o.iloc[-3] + self.c.iloc[-3]) / 2):
            return {"detected": True, "name": "Morning Star", "bias": "bullish", "score": 7}

        return {"detected": False, "name": "Morning Star", "bias": "bullish", "score": 0}

    def _detect_evening_star(self) -> Dict:
        """Evening Star: 3-candle bearish reversal."""
        if len(self.df) < 3:
            return {"detected": False, "name": "Evening Star", "bias": "bearish", "score": 0}

        if (self._is_bullish(-3) and
                self._body_size(-3) > self._avg_body_size() * 0.8 and
                self._body_size(-2) < self._avg_body_size() * 0.3 and
                self._is_bearish(-1) and
                self._body_size(-1) > self._avg_body_size() * 0.8 and
                self.c.iloc[-1] < (self.o.iloc[-3] + self.c.iloc[-3]) / 2):
            return {"detected": True, "name": "Evening Star", "bias": "bearish", "score": 7}

        return {"detected": False, "name": "Evening Star", "bias": "bearish", "score": 0}

    def _detect_bullish_harami(self) -> Dict:
        if len(self.df) < 2:
            return {"detected": False, "name": "Bullish Harami", "bias": "bullish", "score": 0}

        if (self._is_bearish(-2) and
                self._is_bullish(-1) and
                self.o.iloc[-1] > self.c.iloc[-2] and
                self.c.iloc[-1] < self.o.iloc[-2] and
                self._body_size(-1) < self._body_size(-2) * 0.5):
            return {"detected": True, "name": "Bullish Harami", "bias": "bullish", "score": 3}

        return {"detected": False, "name": "Bullish Harami", "bias": "bullish", "score": 0}

    def _detect_bearish_harami(self) -> Dict:
        if len(self.df) < 2:
            return {"detected": False, "name": "Bearish Harami", "bias": "bearish", "score": 0}

        if (self._is_bullish(-2) and
                self._is_bearish(-1) and
                self.o.iloc[-1] < self.c.iloc[-2] and
                self.c.iloc[-1] > self.o.iloc[-2] and
                self._body_size(-1) < self._body_size(-2) * 0.5):
            return {"detected": True, "name": "Bearish Harami", "bias": "bearish", "score": 3}

        return {"detected": False, "name": "Bearish Harami", "bias": "bearish", "score": 0}

    def _detect_three_white_soldiers(self) -> Dict:
        if len(self.df) < 3:
            return {"detected": False, "name": "Three White Soldiers", "bias": "bullish", "score": 0}

        if (self._is_bullish(-3) and self._is_bullish(-2) and self._is_bullish(-1) and
                self.c.iloc[-2] > self.c.iloc[-3] and
                self.c.iloc[-1] > self.c.iloc[-2] and
                self._body_size(-3) > self._avg_body_size() * 0.5 and
                self._body_size(-2) > self._avg_body_size() * 0.5 and
                self._body_size(-1) > self._avg_body_size() * 0.5):
            return {"detected": True, "name": "Three White Soldiers", "bias": "bullish", "score": 6}

        return {"detected": False, "name": "Three White Soldiers", "bias": "bullish", "score": 0}

    def _detect_three_black_crows(self) -> Dict:
        if len(self.df) < 3:
            return {"detected": False, "name": "Three Black Crows", "bias": "bearish", "score": 0}

        if (self._is_bearish(-3) and self._is_bearish(-2) and self._is_bearish(-1) and
                self.c.iloc[-2] < self.c.iloc[-3] and
                self.c.iloc[-1] < self.c.iloc[-2] and
                self._body_size(-3) > self._avg_body_size() * 0.5 and
                self._body_size(-2) > self._avg_body_size() * 0.5 and
                self._body_size(-1) > self._avg_body_size() * 0.5):
            return {"detected": True, "name": "Three Black Crows", "bias": "bearish", "score": 6}

        return {"detected": False, "name": "Three Black Crows", "bias": "bearish", "score": 0}

    def _detect_dragonfly_doji(self) -> Dict:
        """Dragonfly Doji: open ≈ close ≈ high, long lower shadow (bullish)."""
        i = -1
        body = self._body_size(i)
        rng = self._candle_range(i)
        lower = self._lower_shadow(i)
        upper = self._upper_shadow(i)

        if rng == 0:
            return {"detected": False, "name": "Dragonfly Doji", "bias": "bullish", "score": 0}

        if body / rng < 0.1 and lower > rng * 0.6 and upper < rng * 0.1:
            return {"detected": True, "name": "Dragonfly Doji", "bias": "bullish", "score": 4}

        return {"detected": False, "name": "Dragonfly Doji", "bias": "bullish", "score": 0}

    def _detect_gravestone_doji(self) -> Dict:
        """Gravestone Doji: open ≈ close ≈ low, long upper shadow (bearish)."""
        i = -1
        body = self._body_size(i)
        rng = self._candle_range(i)
        lower = self._lower_shadow(i)
        upper = self._upper_shadow(i)

        if rng == 0:
            return {"detected": False, "name": "Gravestone Doji", "bias": "bearish", "score": 0}

        if body / rng < 0.1 and upper > rng * 0.6 and lower < rng * 0.1:
            return {"detected": True, "name": "Gravestone Doji", "bias": "bearish", "score": 4}

        return {"detected": False, "name": "Gravestone Doji", "bias": "bearish", "score": 0}
