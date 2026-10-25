"""
IDX AI Signal Bot - Bandarmology Engine
Analyzes broker-level transaction data to detect institutional
accumulation/distribution patterns ("bandar" behavior).
"""

import logging
from typing import Dict, Any, List, cast

import numpy as np  # type: ignore
import pandas as pd  # type: ignore

logger = logging.getLogger(__name__)


class BandarmologyEngine:
    """
    Analyzes broker summary data to detect:
    - Smart money accumulation / distribution
    - Dominant broker concentration
    - Broker flow trends
    """

    # Known smart money / institutional broker codes (Indonesia)
    SMART_MONEY_BROKERS = {"CC", "BK", "KZ", "AK", "AG", "RX"}
    FOREIGN_BROKERS = {"AK", "BK", "KZ", "RX", "AG", "YU"}
    DOMESTIC_INST = {"NI", "ZP", "LG", "MG", "OD", "SQ", "DX", "GR", "CP", "TP", "EP", "IF", "BB"}
    RETAIL_BROKERS = {"XL", "PD", "YP", "XC", "KK"}

    def __init__(self, broker_df: pd.DataFrame):
        """
        Args:
            broker_df: DataFrame with columns:
                [date, broker_code, buy_lot, sell_lot, net_lot,
                 buy_value, sell_value, investor_type, broker_category]
        """
        self.df = broker_df.copy()

    def _is_real_data(self) -> bool:
        """
        Deteksi apakah data broker adalah data real atau mock.
        Ciri data mock: semua net_lot bernilai acak tapi identik dalam distribusi,
        atau jumlah tanggal unik terlalu sedikit (< 3 hari).
        """
        if self.df.empty or len(self.df) < 5:
            return False
        # Cek jumlah hari unik (boleh 1 hari karena API kadang hanya sedia EOD hari terakhir)
        if "date" in self.df.columns:
            unique_dates = self.df["date"].nunique()
            if unique_dates < 1:
                return False
        # Cek apakah broker code variety cukup (real data punya banyak broker)
        if "broker_code" in self.df.columns:
            unique_brokers = self.df["broker_code"].nunique()
            if unique_brokers < 4:
                return False
        # Cek apakah SMART_MONEY_BROKERS ada di data (real data biasanya punya CC, BK, dll)
        sm_present = self.df["broker_code"].isin(self.SMART_MONEY_BROKERS).any() if "broker_code" in self.df.columns else False
        if not sm_present:
            return False
        return True

    def analyze(self) -> Dict[str, Any]:
        """Run full bandarmology analysis."""
        result = {
            "bandar_score": 0,
            "bandar_signal": "neutral",
            "accumulation_detected": False,
            "distribution_detected": False,
            "top_buyers": [],
            "top_sellers": [],
            "top_buyers_lots": {},
            "top_sellers_lots": {},
            "smart_money_flow": 0,
            "retail_flow": 0,
            "concentration_ratio": 0,
            "is_real_data": False,
            "data_date": None,
        }

        if self.df.empty:
            return result

        # Guard: jika data terlihat mock/tidak valid, kembalikan netral
        # agar skor Bandarmology tidak bias ke positif secara artifisial
        if not self._is_real_data():
            logger.debug("[Bandarmology] Data terdeteksi sebagai mock/tidak valid — skor dikembalikan netral.")
            result["is_real_data"] = False
            try:
                result.update(self._analyze_net_flow())
            except Exception:
                pass
            return result

        result["is_real_data"] = True
        try:
            result.update(self._analyze_net_flow())
            result.update(self._analyze_smart_money())
            result.update(self._analyze_concentration())
            result.update(self._analyze_accumulation_distribution())
            result.update(self._compute_bandar_score(result))
        except Exception as e:
            logger.error(f"Bandarmology analysis error: {e}")

        return result

    def _get_latest_date_df(self) -> pd.DataFrame:
        """
        Filter dataframe to ONLY the most recent trading date (H-1).
        Ini memastikan top_buyers dan top_sellers mencerminkan data hari
        terakhir saja, bukan campuran banyak hari.
        """
        if "date" not in self.df.columns or self.df.empty:
            return self.df

        # Gunakan apply agar Pyrefly tidak mendeteksi output sebagai Timestamp tunggal
        dates = self.df["date"].apply(lambda x: pd.to_datetime(x).date())
        latest_date = dates.max()
        latest_df = self.df[dates == latest_date]
        logger.debug(f"[Bandarmology] Using only latest date: {latest_date} ({len(latest_df)} rows)")
        return cast(pd.DataFrame, latest_df)

    def _analyze_net_flow(self) -> Dict[str, Any]:
        """Analyze overall net flow by broker.
        
        PENTING: top_buyers dan top_sellers hanya menggunakan data H-1
        (hari trading terakhir) agar akurat dan tidak tercampur data lama.
        Sedangkan total buy/sell lots tetap menggunakan semua data untuk
        analisis trend multi-hari.
        """
        # ── Top Buyers / Top Sellers: HANYA dari tanggal terakhir (H-1) ──
        latest_df = self._get_latest_date_df()
        latest_date = None
        if "date" in latest_df.columns and not latest_df.empty:
            # Ambil scalar iloc[0] dan konversi ke date untuk menghindari .dt di Pyrefly
            latest_date = pd.to_datetime(latest_df["date"].iloc[0]).date()

        top_buyers = []
        top_sellers = []
        top_buyers_lots = {}
        top_sellers_lots = {}

        if not latest_df.empty:
            latest_agg = (
                latest_df.groupby("broker_code")
                .agg(
                    total_buy=("buy_lot", "sum"),
                    total_sell=("sell_lot", "sum"),
                    total_net=("net_lot", "sum"),
                )
                .sort_values("total_net", ascending=False)
            )
            top_buyers = latest_agg.head(5).index.tolist()
            top_sellers = latest_agg.tail(5).index.tolist()

            for b in top_buyers:
                row = latest_agg.loc[b]
                lot = int(row["total_net"]) if row["total_net"] > 0 else int(row["total_buy"])
                top_buyers_lots[b] = max(0, lot)

            for s in top_sellers[::-1]:
                row = latest_agg.loc[s]
                lot = abs(int(row["total_net"])) if row["total_net"] < 0 else int(row["total_sell"])
                top_sellers_lots[s] = max(0, lot)

        # ── Total buy/sell: dari SEMUA data (untuk trend analysis) ──
        all_agg = (
            self.df.groupby("broker_code")
            .agg(
                total_buy=("buy_lot", "sum"),
                total_sell=("sell_lot", "sum"),
                total_net=("net_lot", "sum"),
            )
            .sort_values("total_net", ascending=False)
        )

        return {
            "top_buyers": top_buyers,
            "top_sellers": top_sellers,
            "top_buyers_lots": top_buyers_lots,
            "top_sellers_lots": top_sellers_lots,
            "data_date": str(latest_date) if latest_date else None,
            "total_buy_lots": int(all_agg["total_buy"].sum()),
            "total_sell_lots": int(all_agg["total_sell"].sum()),
            "net_lots": int(all_agg["total_net"].sum()),
        }

    def _analyze_smart_money(self) -> Dict[str, Any]:
        """Analyze smart money vs retail flow."""
        sm_mask = self.df["broker_code"].isin(self.SMART_MONEY_BROKERS)
        rt_mask = self.df["broker_code"].isin(self.RETAIL_BROKERS)
        di_mask = self.df["broker_code"].isin(self.DOMESTIC_INST)
        fg_mask = self.df["broker_code"].isin(self.FOREIGN_BROKERS)

        sm_flow = self.df.loc[sm_mask, "net_lot"].sum() if sm_mask.any() else 0
        rt_flow = self.df.loc[rt_mask, "net_lot"].sum() if rt_mask.any() else 0
        di_flow = self.df.loc[di_mask, "net_lot"].sum() if di_mask.any() else 0
        fg_flow = self.df.loc[fg_mask, "net_lot"].sum() if fg_mask.any() else 0

        return {
            "smart_money_flow": int(sm_flow),
            "retail_flow": int(rt_flow),
            "domestic_inst_flow": int(di_flow),
            "foreign_broker_flow": int(fg_flow),
            "smart_money_buying": sm_flow > 0,
            "retail_selling": rt_flow < 0,
            "smart_vs_retail_divergence": sm_flow > 0 and rt_flow < 0,
        }

    def _analyze_concentration(self) -> Dict[str, Any]:
        """Analyze broker concentration (top 3 vs total)."""
        broker_agg = (
            self.df.groupby("broker_code")["buy_lot"]
            .sum()
            .sort_values(ascending=False)
        )

        total = broker_agg.sum()
        if total == 0:
            return {"concentration_ratio": 0, "broker_count": 0}

        top3_share = broker_agg.head(3).sum() / total

        return {
            "concentration_ratio": round(top3_share, 4),
            "high_concentration": top3_share > 0.4,  # Top 3 > 40% = concentrated
            "broker_count": len(broker_agg),
        }

    def _analyze_accumulation_distribution(self) -> Dict[str, Any]:
        """Detect multi-day accumulation or distribution patterns."""
        if "date" not in self.df.columns:
            return {"accumulation_detected": False, "distribution_detected": False}

        daily_net = self.df.groupby("date")["net_lot"].sum().sort_index()

        if len(daily_net) < 3:
            return {"accumulation_detected": False, "distribution_detected": False}

        # Accumulation: consecutive positive net flow
        recent_5 = daily_net.tail(5)
        positive_days = (recent_5 > 0).sum()
        negative_days = (recent_5 < 0).sum()

        accumulation = positive_days >= 4  # 4 out of 5 days positive
        distribution = negative_days >= 4  # 4 out of 5 days negative

        # Trend of net flow
        net_trend = daily_net.tail(10)
        if len(net_trend) >= 5:
            slope = np.polyfit(range(len(net_trend)), net_trend.values, 1)[0]
        else:
            slope = 0

        return {
            "accumulation_detected": accumulation,
            "distribution_detected": distribution,
            "positive_flow_days": int(positive_days),  # type: ignore
            "negative_flow_days": int(negative_days),  # type: ignore
            "flow_trend_slope": round(slope, 2),
        }

    def _compute_bandar_score(self, analysis: Dict) -> Dict[str, Any]:
        """Compute overall bandarmology score (-15 to +15)."""
        score = 0

        # Smart money flow (+/- 4)
        if analysis.get("smart_money_buying"):
            score += 4
        elif analysis.get("smart_money_flow", 0) < 0:
            score -= 4

        # Accumulation / distribution (+/- 4)
        if analysis.get("accumulation_detected"):
            score += 4
        elif analysis.get("distribution_detected"):
            score -= 4

        # Smart vs retail divergence (+3)
        if analysis.get("smart_vs_retail_divergence"):
            score += 3

        # High concentration (+/- 2)
        if analysis.get("high_concentration"):
            if analysis.get("net_lots", 0) > 0:
                score += 2
            else:
                score -= 2

        # Flow trend (+/- 2)
        slope = analysis.get("flow_trend_slope", 0)
        if slope > 100:
            score += 2
        elif slope < -100:
            score -= 2

        # Map to signal
        # Threshold dinaikkan sedikit agar tidak terlalu mudah capai strong_accumulation
        if score >= 7:
            signal = "strong_accumulation"
        elif score >= 3:
            signal = "accumulation"
        elif score <= -7:
            signal = "strong_distribution"
        elif score <= -3:
            signal = "distribution"
        else:
            signal = "neutral"

        return {
            "bandar_score": score,
            "bandar_signal": signal,
        }
