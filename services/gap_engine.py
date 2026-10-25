"""
IDX AI Signal Bot - Gap Analysis Engine
Detects price gaps between sessions and confirms with volume.

Gap = selisih antara open hari ini vs close kemarin.
Valid untuk semua timeframe, tidak butuh warm-up period.
"""

import logging
from typing import Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)


class GapEngine:
    """
    Detects and classifies price gaps from OHLCV data.

    Gap Types:
    - gap_up_confirmed  : Open >= prev_close * 1.01 AND volume > 1.3x avg20  → bullish (+5)
    - gap_up_unconfirmed: Open >= prev_close * 1.01 BUT volume normal         → caution (-2)
    - gap_down          : Open <= prev_close * 0.99                           → bearish (-3)
    - none              : No significant gap                                   → neutral (0)
    """

    GAP_THRESHOLD_PCT = 1.0     # Minimum gap size (%) to be considered significant
    VOL_CONFIRM_RATIO = 1.3     # Volume must be 1.3x avg to confirm gap

    def __init__(self, ohlcv_df: pd.DataFrame):
        self.df = ohlcv_df.copy()

    def analyze(self) -> Dict[str, Any]:
        """Analyze gap for the most recent session."""
        result = {
            "gap_type": "none",
            "gap_pct": 0.0,
            "gap_confirmed": False,
            "gap_score": 0,
        }

        if self.df is None or len(self.df) < 2:
            return result

        try:
            today_open  = float(self.df["open"].iloc[-1])
            prev_close  = float(self.df["close"].iloc[-2])
            today_vol   = float(self.df["volume"].iloc[-1])
            avg_vol_20  = float(self.df["volume"].tail(20).mean()) if len(self.df) >= 20 else float(self.df["volume"].mean())

            if prev_close <= 0:
                return result

            gap_pct = (today_open - prev_close) / prev_close * 100
            vol_confirmed = avg_vol_20 > 0 and today_vol >= avg_vol_20 * self.VOL_CONFIRM_RATIO

            if gap_pct >= self.GAP_THRESHOLD_PCT:
                if vol_confirmed:
                    result.update({
                        "gap_type": "gap_up_confirmed",
                        "gap_pct": round(gap_pct, 2),
                        "gap_confirmed": True,
                        "gap_score": 5,
                    })
                else:
                    result.update({
                        "gap_type": "gap_up_unconfirmed",
                        "gap_pct": round(gap_pct, 2),
                        "gap_confirmed": False,
                        "gap_score": -2,
                    })
            elif gap_pct <= -self.GAP_THRESHOLD_PCT:
                result.update({
                    "gap_type": "gap_down",
                    "gap_pct": round(gap_pct, 2),
                    "gap_confirmed": False,
                    "gap_score": -3,
                })
            else:
                result["gap_pct"] = round(gap_pct, 2)

        except Exception as e:
            logger.debug(f"[GapEngine] Analysis error: {e}")

        return result
