"""
IDX AI Signal Bot - Sector/Market Correlation Engine
Measures relative strength of a stock vs IHSG (^JKSE) over 5 days.

No warm-up period needed — uses only 5-6 bars of closing prices.
Skor berkontribusi ke kategori 'sector_correlation' (4 poin).
"""

import logging
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SectorCorrelationEngine:
    """
    Computes relative strength of a stock vs IHSG in the last 5 trading days.

    Score logic:
    +4 : Stock outperforms IHSG by > 2%   (strong relative strength)
    +2 : Stock outperforms IHSG by 0-2%   (moderate outperformance)
     0 : Stock inline with IHSG ±2%       (neutral)
    -2 : Stock underperforms IHSG by > 2% (relative weakness)
    """

    def __init__(self, ohlcv_df: pd.DataFrame, ihsg_df: Optional[pd.DataFrame] = None):
        """
        Args:
            ohlcv_df  : OHLCV data for the stock being analyzed
            ihsg_df   : OHLCV data for IHSG (^JKSE). If None, uses stock 5-day return only.
        """
        self.df = ohlcv_df.copy() if ohlcv_df is not None else pd.DataFrame()
        self.ihsg_df = ihsg_df.copy() if ihsg_df is not None else None

    def analyze(self) -> Dict[str, Any]:
        """Compute relative strength score."""
        result = {
            "stock_5d_return": 0.0,
            "ihsg_5d_return": 0.0,
            "relative_strength": 0.0,
            "corr_signal": "neutral",
            "sector_score": 0,
            "ihsg_available": False,
        }

        if self.df.empty or "close" not in self.df.columns:
            return result

        clean_df = self.df.dropna(subset=["close"]).copy()
        if len(clean_df) < 6:
            return result

        try:
            # Stock 5-day return
            stock_now = float(clean_df["close"].iloc[-1])
            stock_5d = float(clean_df["close"].iloc[-6])
            if not np.isfinite(stock_now) or not np.isfinite(stock_5d) or stock_5d <= 0:
                return result

            stock_ret = (stock_now / stock_5d - 1) * 100
            if not np.isfinite(stock_ret):
                return result
            result["stock_5d_return"] = round(stock_ret, 2)

            # IHSG relative strength (if valid non-NaN data available)
            ihsg_clean = (
                self.ihsg_df.dropna(subset=["close"]).copy()
                if self.ihsg_df is not None and not self.ihsg_df.empty and "close" in self.ihsg_df.columns
                else None
            )
            ihsg_valid = False
            if ihsg_clean is not None and len(ihsg_clean) >= 6:
                ihsg_now = float(ihsg_clean["close"].iloc[-1])
                ihsg_5d = float(ihsg_clean["close"].iloc[-6])

                if np.isfinite(ihsg_now) and np.isfinite(ihsg_5d) and ihsg_5d > 0:
                    ihsg_ret = (ihsg_now / ihsg_5d - 1) * 100
                    rs = stock_ret - ihsg_ret
                    if np.isfinite(ihsg_ret) and np.isfinite(rs):
                        ihsg_valid = True
                        result["ihsg_5d_return"] = round(ihsg_ret, 2)
                        result["relative_strength"] = round(rs, 2)
                        result["ihsg_available"] = True

                        if rs > 2.0:
                            result.update({"corr_signal": "outperform", "sector_score": 4})
                        elif rs > 0:
                            result.update({"corr_signal": "inline_positive", "sector_score": 2})
                        elif rs >= -2.0:
                            result.update({"corr_signal": "inline_neutral", "sector_score": 0})
                        else:
                            result.update({"corr_signal": "underperform", "sector_score": 0})

            if not ihsg_valid:
                # Fallback: use absolute 5-day return as proxy
                result["ihsg_available"] = False
                if stock_ret > 3.0:
                    result.update({"corr_signal": "strong_5d_return", "sector_score": 2})
                elif stock_ret >= 0:
                    result.update({"corr_signal": "positive_5d_return", "sector_score": 1})
                elif stock_ret >= -3.0:
                    result.update({"corr_signal": "slight_weakness", "sector_score": 0})
                else:
                    result.update({"corr_signal": "weak_5d_return", "sector_score": 0})

        except Exception as e:
            logger.debug(f"[SectorCorrelation] Analysis error: {e}")

        return result
