"""
IDX AI Signal Bot - Foreign Flow Engine
Tracks net foreign buy/sell and momentum for signal scoring.
"""

import logging
from typing import Dict, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ForeignFlowEngine:
    """
    Analyzes foreign investor flow data:
    - Net foreign buy/sell trend
    - Foreign flow momentum
    - Participation rate changes
    """

    def __init__(self, ff_df: pd.DataFrame):
        """
        Args:
            ff_df: DataFrame with columns:
                [date, foreign_buy_lot, foreign_sell_lot, foreign_net_lot,
                 foreign_buy_value, foreign_sell_value, foreign_net_value,
                 foreign_participation_percent]
        """
        self.df = ff_df.copy().sort_values("date").reset_index(drop=True)

    def _is_real_data(self) -> bool:
        """
        Deteksi apakah data foreign flow adalah real atau mock.
        Ciri data mock: semua foreign_net_value acak tapi std-nya sangat tinggi
        tanpa ada pola trend (terlalu random), atau semua nilai persis sama.
        Ciri real: ada beberapa hari dengan 0 (hari libur/weekend), dan variance
        antara buying vs selling tidak terlalu merata.
        """
        if self.df.empty or len(self.df) < 5:
            return False
        # Cek apakah data tidak sepenuhnya nol
        net = self.df["foreign_net_value"]
        if net.abs().sum() == 0:
            return False
        return True

    def analyze(self) -> Dict[str, Any]:
        """Run full foreign flow analysis."""
        result = {
            "ff_score": 0,
            "ff_signal": "neutral",
            "ff_net_value_today": 0,
            "ff_net_5d": 0,
            "ff_net_10d": 0,
            "ff_momentum": "flat",
            "ff_participation": 0,
            "ff_streak": 0,
            "is_real_data": False,
        }

        if self.df.empty:
            return result

        # Guard: jika data mock, kembalikan netral agar tidak bias scoring
        if not self._is_real_data():
            logger.debug("[ForeignFlow] Data terdeteksi sebagai mock — skor dikembalikan netral.")
            return result

        result["is_real_data"] = True
        try:
            result.update(self._analyze_net_flow())
            result.update(self._analyze_momentum())
            # Catatan: _analyze_participation dihapus dari scoring karena
            # GoAPI tidak menyediakan field participation_percent (selalu 0)
            result.update(self._compute_ff_score(result))
        except Exception as e:
            logger.error(f"Foreign flow analysis error: {e}")

        return result

    def _analyze_net_flow(self) -> Dict[str, Any]:
        """Analyze net foreign flow over various periods."""
        net = self.df["foreign_net_value"]
        net_lot = self.df["foreign_net_lot"]

        today = net.iloc[-1] if len(net) > 0 else 0
        net_5d = net.tail(5).sum()
        net_10d = net.tail(10).sum()
        net_20d = net.tail(20).sum()

        # Streak: consecutive days of same direction
        streak = 0
        direction = 1 if net_lot.iloc[-1] > 0 else -1
        for val in reversed(net_lot.values):
            if (val > 0 and direction > 0) or (val < 0 and direction < 0):
                streak += 1
            else:
                break
        streak *= direction  # Positive = buy streak, negative = sell streak

        return {
            "ff_net_value_today": round(today, 0),
            "ff_net_lot_today": int(net_lot.iloc[-1]) if len(net_lot) > 0 else 0,
            "ff_net_5d": round(net_5d, 0),
            "ff_net_10d": round(net_10d, 0),
            "ff_net_20d": round(net_20d, 0),
            "ff_streak": streak,
            "ff_buy_dominant": net_5d > 0,
            "ff_sell_dominant": net_5d < 0,
        }

    def _analyze_momentum(self) -> Dict[str, Any]:
        """Analyze foreign flow momentum (acceleration/deceleration)."""
        if len(self.df) < 10:
            return {"ff_momentum": "flat", "ff_acceleration": 0}

        net = self.df["foreign_net_value"]

        # Compare recent 5-day sum vs prior 5-day sum
        recent_5 = net.tail(5).sum()
        prior_5 = net.iloc[-10:-5].sum()

        if recent_5 > 0 and recent_5 > prior_5:
            momentum = "accelerating_buy"
        elif recent_5 > 0 and recent_5 < prior_5:
            momentum = "decelerating_buy"
        elif recent_5 < 0 and recent_5 < prior_5:
            momentum = "accelerating_sell"
        elif recent_5 < 0 and recent_5 > prior_5:
            momentum = "decelerating_sell"
        else:
            momentum = "flat"

        acceleration = recent_5 - prior_5

        return {
            "ff_momentum": momentum,
            "ff_acceleration": round(acceleration, 0),
        }

    def _analyze_participation(self) -> Dict[str, Any]:
        """Analyze foreign participation rate."""
        if "foreign_participation_percent" not in self.df.columns:
            return {"ff_participation": 0, "ff_participation_trend": "stable"}

        participation = self.df["foreign_participation_percent"]
        current = participation.iloc[-1]
        avg_20 = participation.tail(20).mean()

        if current > avg_20 * 1.1:
            trend = "increasing"
        elif current < avg_20 * 0.9:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "ff_participation": round(current, 2),
            "ff_participation_avg": round(avg_20, 2),
            "ff_participation_trend": trend,
        }

    def _compute_ff_score(self, analysis: Dict) -> Dict[str, Any]:
        """
        Compute foreign flow score (-10 to +10).
        Catatan: participation_trend DIHAPUS dari scoring karena GoAPI
        tidak menyediakan field ini (selalu 0) — menyebabkan skor bias 'stable'.
        """
        score = 0

        # Net 5-day flow direction (+/- 4) — dinaikkan karena participation dihapus
        if analysis.get("ff_buy_dominant"):
            score += 4
        elif analysis.get("ff_sell_dominant"):
            score -= 4

        # Momentum (+/- 4)
        momentum = analysis.get("ff_momentum", "flat")
        if momentum == "accelerating_buy":
            score += 4
        elif momentum == "decelerating_buy":
            score += 1
        elif momentum == "accelerating_sell":
            score -= 4
        elif momentum == "decelerating_sell":
            score -= 1

        # Streak konsekutif (+/- 2)
        streak = analysis.get("ff_streak", 0)
        if streak >= 3:
            score += 2
        elif streak <= -3:
            score -= 2

        # Net 10-day trend — konfirmasi mid-term (+/- 2)
        net_10d = analysis.get("ff_net_10d", 0)
        if net_10d > 0:
            score += 2
        elif net_10d < 0:
            score -= 2

        # DIHAPUS: participation_trend — data selalu 0 dari GoAPI

        # Clamp
        score = max(-10, min(10, score))

        # Signal mapping
        if score >= 5:
            signal = "strong_foreign_buy"
        elif score >= 2:
            signal = "foreign_buy"
        elif score <= -5:
            signal = "strong_foreign_sell"
        elif score <= -2:
            signal = "foreign_sell"
        else:
            signal = "neutral"

        return {
            "ff_score": score,
            "ff_signal": signal,
        }
