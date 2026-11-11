"""
IDX AI Signal Bot - IHSG Regime Filter Engine
Analyzes the market regime based on the Jakarta Composite Index (IHSG).
"""

import logging
from typing import Dict, Any, Optional, List
import numpy as np
import pandas as pd
from services.data_provider_service import DataProviderService

logger = logging.getLogger(__name__)

def get_ihsg_regime(ihsg_close_prices: List[float]) -> str:
    """
    Menghitung regime IHSG berdasarkan MA5, MA20 dan persentase perubahan 20 hari terakhir.
    - bullish: MA5 > MA20 dan change_20d_pct > 2%
    - bearish: MA5 < MA20 dan change_20d_pct < -2%
    - sideways: kondisi selain di atas
    """
    prices = pd.Series(ihsg_close_prices, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(prices) < 20:
        return "sideways"
        
    ma5 = float(prices.tail(5).mean())
    ma20 = float(prices.tail(20).mean())
    
    current_close = float(prices.iloc[-1])
    close_20d_ago = float(prices.iloc[-20])
    
    if close_20d_ago > 0:
        change_20d_pct = ((current_close - close_20d_ago) / close_20d_ago) * 100
    else:
        change_20d_pct = 0.0
    
    if ma5 > ma20 and change_20d_pct > 2.0:
        return "bullish"
    elif ma5 < ma20 and change_20d_pct < -2.0:
        return "bearish"
    else:
        return "sideways"

def apply_ihsg_regime_adjustment(saham_score: float, ihsg_regime: str, is_intraday: bool = False) -> float:
    """
    IHSG murni sebagai informasi konteks pasar, tidak memodifikasi skor saham.
    Mengembalikan skor saham murni tanpa penambahan atau pengurangan poin (multiplier 1.0).
    """
    return max(0.0, min(100.0, float(saham_score)))


class RegimeEngine:
    """Computes overall market regime from IHSG (^JKSE) index data."""

    def __init__(self, data_provider: Optional[DataProviderService] = None):
        self.data_provider = data_provider or DataProviderService()
        self._cached_regime = None

    def get_ihsg_regime(self) -> Dict[str, Any]:
        """
        Fetches IHSG data and computes the trend regime.
        Returns a dictionary with details.
        """
        if self._cached_regime is not None:
            return self._cached_regime

        try:
            df_ihsg = self.data_provider.get_ohlcv("^JKSE", period_days=30)
            if not df_ihsg.empty and "close" in df_ihsg.columns:
                df_ihsg = df_ihsg.dropna(subset=["close"]).reset_index(drop=True)
            if df_ihsg.empty or len(df_ihsg) < 20:
                self._cached_regime = self._default_regime("Data IHSG tidak cukup (< 20 hari)")
                return self._cached_regime
                
            close_prices = [float(x) for x in df_ihsg["close"].tolist() if pd.notna(x) and np.isfinite(x)]
            if len(close_prices) < 20:
                self._cached_regime = self._default_regime("Data IHSG valid tidak cukup (< 20 hari)")
                return self._cached_regime
            regime_str = get_ihsg_regime(close_prices)
            
            last_close = float(close_prices[-1])
            prev_close = float(close_prices[-2])
            daily_change_pct = ((last_close - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
            
            ma5 = sum(close_prices[-5:]) / 5
            ma20 = sum(close_prices[-20:]) / 20
            change_20d_pct = ((last_close - close_prices[-20]) / close_prices[-20]) * 100 if close_prices[-20] > 0 else 0.0
            
            description = (
                f"Prediksi IHSG: {regime_str.upper()}. "
                f"MA5 ({ma5:.0f}) vs MA20 ({ma20:.0f}), "
                f"Perubahan 20 Hari: {change_20d_pct:+.2f}%."
            )
            
            self._cached_regime = {
                "ticker": "^JKSE",
                "name": "Indeks Harga Saham Gabungan (IHSG)",
                "last_price": round(last_close, 2),
                "daily_change_pct": round(daily_change_pct, 2),
                "ema_20": round(ma20, 2),
                "ema_50": 0.0,
                "regime": regime_str.upper(),
                "description": description,
                "regime_raw": regime_str
            }
            return self._cached_regime

        except Exception as e:
            logger.error(f"Error calculating IHSG regime: {e}", exc_info=True)
            self._cached_regime = self._default_regime(str(e))
            return self._cached_regime

    def _default_regime(self, reason: str) -> Dict[str, Any]:
        """Fallback default regime if analysis fails."""
        return {
            "ticker": "^JKSE",
            "name": "Indeks Harga Saham Gabungan (IHSG)",
            "last_price": 7000.0,
            "daily_change_pct": 0.0,
            "ema_20": 7000.0,
            "ema_50": 7000.0,
            "regime": "SIDEWAYS",
            "description": f"IHSG diasumsikan SIDEWAYS (Default). Alasan: {reason}.",
            "regime_raw": "sideways"
        }
