"""
IDX AI Signal Bot - Data Provider Service
Fetches OHLCV, broker summary, and foreign flow from multiple sources.
Supports: mock (for testing), csv, yfinance API.
"""

import logging
import threading
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_YFINANCE_DOWNLOAD_LOCK = threading.Lock()

# Monkeypatch yfinance User-Agent to bypass Yahoo Finance 429 rate limit
try:
    import yfinance.data as yfd
    yfd.YfData.user_agent_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
except Exception as e:
    logger.warning(f"Failed to monkeypatch yfinance User-Agent: {e}")


class DataProviderService:
    """
    Unified data provider that abstracts the data source.
    In production: fetches from IDX API or yfinance.
    In development/testing: returns synthetic mock data.
    """

    _current_key_index = 0
    _last_exhausted_time = None
    _ohlcv_cache = {}

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.DATA_PROVIDER
        goapi_key_str = settings.GOAPI_KEY or ""
        self.goapi_keys = [k.strip() for k in goapi_key_str.split(",") if k.strip()]
        self.supabase_project_id = getattr(settings, "SUPABASE_PROJECT_ID", "")
        self.supabase_key = getattr(settings, "SUPABASE_API_KEY", "")
        self.supabase_url = getattr(settings, "SUPABASE_URL", "")
        if not self.supabase_url and self.supabase_project_id:
            self.supabase_url = f"https://{self.supabase_project_id}.supabase.co"

    def _make_goapi_request(self, url: str, params: dict) -> dict:
        """
        Makes a request to GoAPI with automatic key rotation on failure (e.g. 429, 403, 401).
        """
        import httpx
        import time

        if DataProviderService._last_exhausted_time and (time.time() - DataProviderService._last_exhausted_time < 300):
            raise RuntimeError("GoAPI previously failed or ran out of quota recently. Skipping to prevent delay.")

        if not self.goapi_keys:
            raise ValueError("No GoAPI keys configured.")

        num_keys = len(self.goapi_keys)
        for attempt in range(num_keys):
            active_key = self.goapi_keys[DataProviderService._current_key_index]
            headers = {
                "X-API-KEY": active_key,
                "Accept": "application/json"
            }
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(url, params=params, headers=headers)
                    
                    if resp.status_code in [401, 403, 429]:
                        logger.warning(
                            f"GoAPI Key index {DataProviderService._current_key_index} failed with status {resp.status_code}. "
                            "Rotating to next key..."
                        )
                        DataProviderService._current_key_index = (DataProviderService._current_key_index + 1) % num_keys
                        continue
                    
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as hse:
                if hse.response.status_code in [401, 403, 429]:
                    logger.warning(
                        f"GoAPI HTTPStatusError {hse.response.status_code} with key index {DataProviderService._current_key_index}. "
                        "Rotating key..."
                    )
                    DataProviderService._current_key_index = (DataProviderService._current_key_index + 1) % num_keys
                    continue
                else:
                    raise hse
            except Exception as e:
                logger.warning(
                    f"GoAPI request error with key index {DataProviderService._current_key_index}: {e}. "
                    "Rotating key..."
                )
                DataProviderService._current_key_index = (DataProviderService._current_key_index + 1) % num_keys
                continue

        DataProviderService._last_exhausted_time = time.time()
        raise RuntimeError("All configured GoAPI keys failed or ran out of quota.")

    # ------------------------------------------------------------------ #
    #  OHLCV
    # ------------------------------------------------------------------ #

    def get_ohlcv(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        period_days: int = 365,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Returns OHLCV DataFrame with columns:
        [date, open, high, low, close, volume, value, frequency]
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=period_days)

        cache_key = (ticker, start_date, end_date, interval)
        if cache_key in DataProviderService._ohlcv_cache:
            logger.debug(f"Using cached OHLCV for {ticker}")
            return DataProviderService._ohlcv_cache[cache_key].copy()

        if self.provider == "yfinance":
            df = self._fetch_yfinance(ticker, start_date, end_date, interval)
        elif self.provider == "csv":
            df = self._fetch_csv(ticker, start_date, end_date)
        else:
            df = self._generate_mock_ohlcv(ticker, start_date, end_date, interval)

        if not df.empty:
            DataProviderService._ohlcv_cache[cache_key] = df

        return df

    def _fetch_yfinance(self, ticker: str, start: date, end: date, interval: str = "1d") -> pd.DataFrame:
        """Fetch from Yahoo Finance (IDX tickers use .JK suffix)."""
        try:
            import yfinance as yf

            if ticker.startswith("^") or ticker.endswith(".JK") or "=" in ticker or "." in ticker or ticker == "EIDO":
                yf_ticker = ticker
            else:
                yf_ticker = f"{ticker}.JK"
                
            import time
            import random
            
            # Anti rate-limit delay
            time.sleep(random.uniform(0.5, 1.5))
            
            # Intraday limits: 1m max 7d, 5m/15m/30m max 60d, 60m/1h max 730d
            if interval in ["1m", "5m", "15m", "30m", "60m", "1h"]:
                if interval == "1m":
                    period = "7d"
                    with _YFINANCE_DOWNLOAD_LOCK:
                        data = yf.download(yf_ticker, period=period, interval=interval, progress=False)
                elif interval in ["5m", "15m", "30m"]:
                    period = "60d"
                    with _YFINANCE_DOWNLOAD_LOCK:
                        data = yf.download(yf_ticker, period=period, interval=interval, progress=False)
                else:
                    with _YFINANCE_DOWNLOAD_LOCK:
                        data = yf.download(yf_ticker, start=str(start), end=str(end), interval=interval, progress=False)
            else:
                with _YFINANCE_DOWNLOAD_LOCK:
                    data = yf.download(yf_ticker, start=str(start), end=str(end), interval=interval, progress=False)

            if data.empty:
                logger.warning(f"No yfinance data for {ticker}")
                return pd.DataFrame()

            # Flatten multi-level columns if present
            if hasattr(data.columns, "levels"):
                data.columns = data.columns.get_level_values(0)

            # Date column should contain the full index (datetime) for intraday, or date for daily
            if interval in ["1m", "5m", "15m", "30m", "60m", "1h"]:
                date_vals = data.index
            else:
                date_vals = data.index.date

            # Helper to safely extract 1D numpy array
            def safe_1d(col_name):
                col_data = data[col_name]
                if hasattr(col_data, "values"):
                    val = col_data.values
                else:
                    val = col_data
                if hasattr(val, "ravel"):
                    return val.ravel()
                return val

            # Also flatten date_vals
            if hasattr(date_vals, "values"):
                date_vals_1d = date_vals.values.ravel()
            elif hasattr(date_vals, "ravel"):
                date_vals_1d = date_vals.ravel()
            else:
                date_vals_1d = date_vals

            # For volume values: replace NaNs/Infs before casting to int64
            vol_raw = safe_1d("Volume")
            if np.issubdtype(vol_raw.dtype, np.number):
                vol_raw = np.nan_to_num(vol_raw, nan=0.0, posinf=0.0, neginf=0.0)
            volume_1d = vol_raw.astype('int64')

            close_1d = safe_1d("Close")
            open_1d = safe_1d("Open")
            high_1d = safe_1d("High")
            low_1d = safe_1d("Low")
            value_1d = (close_1d * volume_1d)

            df = pd.DataFrame({
                "date": date_vals_1d,
                "open": open_1d,
                "high": high_1d,
                "low": low_1d,
                "close": close_1d,
                "volume": volume_1d,
                "value": value_1d,
                "frequency": np.random.randint(50, 5000, size=len(data)),
            })
            df = df.reset_index(drop=True)
            logger.info(f"Fetched {len(df)} rows ({interval}) for {ticker} from yfinance")
            return df

        except Exception as e:
            logger.error(f"yfinance error for {ticker}: {e}")
            try:
                logger.error(f"Data columns: {list(data.columns)}")
                logger.error(f"Data shape: {data.shape}")
            except Exception:
                pass
            return pd.DataFrame()

    def _fetch_csv(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        """Load OHLCV from local CSV file."""
        import os

        csv_path = os.path.join(settings.CSV_DATA_DIR, f"{ticker}.csv")
        if not os.path.exists(csv_path):
            logger.warning(f"CSV file not found: {csv_path}")
            return pd.DataFrame()

        df = pd.read_csv(csv_path, parse_dates=["date"])
        df["date"] = df["date"].dt.date
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        return df.reset_index(drop=True)

    def _generate_mock_ohlcv(
        self, ticker: str, start: date, end: date, interval: str = "1d"
    ) -> pd.DataFrame:
        """Generate realistic-looking mock OHLCV for testing."""
        import zlib
        seed = zlib.adler32(ticker.encode('utf-8'))
        np.random.seed(seed)

        # Generate business days/times
        if interval in ["1m", "5m", "15m", "30m", "60m", "1h"]:
            dates = pd.date_range(start=str(start) + " 00:00:00", end=str(end) + " 23:59:59", freq=interval)
            dates = dates[dates.dayofweek < 5]
            dates = dates[(dates.hour >= 9) & (dates.hour < 16)]
        else:
            dates = pd.bdate_range(start=start, end=end)
            
        n = len(dates)
        if n == 0:
            return pd.DataFrame()

        # Random walk for prices
        base_price = np.random.uniform(500, 15000)
        returns = np.random.normal(0.0005, 0.02, n)
        prices = base_price * np.cumprod(1 + returns)

        # OHLCV generation
        daily_range = prices * np.random.uniform(0.01, 0.04, n)
        opens = prices + np.random.uniform(-0.5, 0.5, n) * daily_range
        highs = np.maximum(prices, opens) + np.abs(np.random.normal(0, 1, n)) * daily_range * 0.5
        lows = np.minimum(prices, opens) - np.abs(np.random.normal(0, 1, n)) * daily_range * 0.5
        closes = prices

        # Round to IDX tick sizes
        closes = np.round(closes / 5) * 5
        opens = np.round(opens / 5) * 5
        highs = np.round(highs / 5) * 5
        lows = np.round(lows / 5) * 5

        volumes = np.random.lognormal(mean=16, sigma=1.5, size=n).astype('int64')
        values = closes * volumes
        freqs = np.random.randint(50, 10000, size=n)
        
        # Use direct index (including time) for intraday, and dates for daily
        if interval in ["1m", "5m", "15m", "30m", "60m", "1h"]:
            date_col = dates
        else:
            date_col = dates.date

        df = pd.DataFrame({
            "date": date_col,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "value": values,
            "frequency": freqs,
        })

        logger.info(f"Generated {len(df)} mock OHLCV rows ({interval}) for {ticker}")
        return df

    # ------------------------------------------------------------------ #
    #  Broker Summary (for Bandarmology)
    # ------------------------------------------------------------------ #

    def get_broker_summary(
        self, ticker: str, target_date: Optional[date] = None, days: int = 20
    ) -> pd.DataFrame:
        """
        Returns broker summary DataFrame with columns:
        [date, broker_code, buy_lot, sell_lot, net_lot, buy_value, sell_value,
         investor_type, broker_category]
        """
        if target_date is None:
            target_date = date.today()

        # 1. Supabase (Primary)
        if self.supabase_key and self.supabase_url:
            try:
                df = self._fetch_supabase_broker_summary(ticker, target_date, days)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.error(f"Supabase broker summary failed for {ticker}: {e}.")

        # 2. GoAPI (Fallback)
        if self.goapi_keys:
            try:
                return self._fetch_goapi_broker_summary(ticker, target_date, days)
            except Exception as e:
                logger.error(f"GoAPI broker summary failed for {ticker}: {e}. Falling back to mock.")

        if self.provider in ("yfinance", "api"):
            logger.warning("Broker summary not available via yfinance and Supabase/GOAPI_KEY not set — using mock")

        return self._generate_mock_broker_summary(ticker, target_date, days)

    def _get_cached_broker_summary(self, ticker: str, query_date: date) -> Optional[pd.DataFrame]:
        """Check if broker summary for ticker and date is cached in the SQLite DB."""
        if hasattr(query_date, "date"):
            query_date = getattr(query_date, "date")()
        elif isinstance(query_date, str):
            query_date = pd.to_datetime(query_date).date()
            
        import sqlite3
        import os
        db_url = settings.DATABASE_URL_SYNC
        db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "./idx_signal_bot.db"
        
        if not os.path.exists(db_path):
            return None
            
        try:
            conn = sqlite3.connect(db_path)
            query = """
                SELECT date, broker_code, buy_lot, sell_lot, net_lot, buy_value, sell_value, investor_type, broker_category
                FROM broker_summary
                WHERE ticker = ? AND date = ?
            """
            df = pd.read_sql_query(query, conn, params=(ticker, str(query_date)))
            conn.close()
            
            if not df.empty:
                logger.info(f"Loaded broker summary cache for {ticker} on {query_date} from SQLite DB ({len(df)} rows)")
                # Convert date column to dates
                df["date"] = pd.to_datetime(df["date"]).dt.date
                return df
        except Exception as e:
            logger.warning(f"Error checking broker summary cache: {e}")
            
        return None

    def _save_broker_summary_cache(self, ticker: str, query_date: date, df: pd.DataFrame):
        """Save broker summary to SQLite DB cache."""
        if df.empty:
            return
            
        import sqlite3
        import os
        db_url = settings.DATABASE_URL_SYNC
        db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "./idx_signal_bot.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            insert_rows = [
                (
                    ticker,
                    str(r["date"]),
                    str(r["broker_code"]),
                    int(r.get("buy_lot", 0) or 0),
                    int(r.get("sell_lot", 0) or 0),
                    int(r.get("net_lot", 0) or 0),
                    float(r.get("buy_value", 0) or 0),
                    float(r.get("sell_value", 0) or 0),
                    str(r.get("investor_type", "domestic") or "domestic"),
                    str(r.get("broker_category", "RT") or "RT"),
                )
                for _, r in df.iterrows()
            ]
            
            cursor.executemany("""
                INSERT OR IGNORE INTO broker_summary 
                (ticker, date, broker_code, buy_lot, sell_lot, net_lot, buy_value, sell_value, investor_type, broker_category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, insert_rows)
            conn.commit()
            conn.close()
            logger.info(f"Saved {len(df)} broker summary rows to cache for {ticker}")
        except Exception as e:
            logger.warning(f"Failed to save broker summary cache to DB: {e}")

    def _fetch_supabase_broker_summary(self, ticker: str, target_date: date, days: int = 20) -> pd.DataFrame:
        """Fetch broker summary from Supabase."""
        if hasattr(target_date, "date"):
            target_date = getattr(target_date, "date")()
        elif isinstance(target_date, str):
            target_date = pd.to_datetime(target_date).date()

        import httpx
        from datetime import datetime
        import pytz

        tz_jakarta = pytz.timezone('Asia/Jakarta')
        now_jakarta = datetime.now(tz_jakarta)
        today = now_jakarta.date()

        query_date = target_date
        if query_date > today:
            query_date = today

        url = f"{self.supabase_url}/rest/v1/broker_summary"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Accept": "application/json",
        }
        params = {
            "ticker": f"eq.{ticker.upper()}",
            "date": f"lte.{query_date}",
            "order": "date.desc",
            "limit": "1000",
        }

        logger.info(f"[DataProvider] Fetching broker summary for {ticker} from Supabase (target_date={target_date})...")

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            results = resp.json()

        if not results:
            logger.warning(f"[DataProvider] No broker summary found in Supabase for {ticker} (date <= {query_date})")
            return pd.DataFrame(columns=[
                "date", "broker_code", "buy_lot", "sell_lot", "net_lot",
                "buy_value", "sell_value", "investor_type", "broker_category"
            ])

        foreign_brokers = {"AK", "BK", "KZ", "RX", "AG", "YU"}

        rows = []
        for row in results:
            broker_code = str(row.get("broker") or "UNKNOWN").strip().upper()
            buy_lot = abs(int(row.get("buy_lot") or 0))
            sell_lot = abs(int(row.get("sell_lot") or 0))
            net_lot = buy_lot - sell_lot
            buy_value = abs(float(row.get("buy_val") or 0))
            sell_value = abs(float(row.get("sell_val") or 0))

            if broker_code in {"CC", "BK", "KZ", "AK", "AG", "RX"}:
                broker_cat = "SM"
            elif broker_code in {"AK", "BK", "KZ", "RX", "AG", "YU"}:
                broker_cat = "FG"
            elif broker_code in {"NI", "ZP", "LG", "MG", "OD", "SQ", "DX", "GR", "CP", "TP", "EP", "IF", "BB"}:
                broker_cat = "DI"
            elif broker_code in {"XL", "PD", "YP", "XC", "KK"}:
                broker_cat = "RT"
            else:
                broker_cat = "RT"

            row_date = pd.to_datetime(row["date"]).date()

            rows.append({
                "date": row_date,
                "broker_code": broker_code,
                "buy_lot": buy_lot,
                "sell_lot": sell_lot,
                "net_lot": net_lot,
                "buy_value": buy_value,
                "sell_value": sell_value,
                "investor_type": "foreign" if broker_code in foreign_brokers else "domestic",
                "broker_category": broker_cat,
            })

        df = pd.DataFrame(rows)

        # Filter by top N unique dates (up to `days`)
        unique_dates = df["date"].unique()
        if len(unique_dates) > days:
            allowed_dates = set(unique_dates[:days])
            df = df[df["date"].isin(allowed_dates)].copy()

        logger.info(f"[DataProvider] Fetched {len(df)} broker rows ({len(df['date'].unique())} dates) for {ticker} from Supabase")

        if not df.empty:
            self._save_broker_summary_cache(ticker, query_date, df)

        return df


    def _fetch_goapi_broker_summary(self, ticker: str, target_date: date, days: int) -> pd.DataFrame:
        """Fetch broker summary from GoAPI."""
        if hasattr(target_date, "date"):
            target_date = getattr(target_date, "date")()
        elif isinstance(target_date, str):
            target_date = pd.to_datetime(target_date).date()
            
        import httpx
        from datetime import datetime
        import pytz
        import os
        
        # GoAPI broker summary is End-of-Day (EOD).
        # Data hanya tersedia setelah market close (~16:00 WIB).
        # Kita HARUS selalu gunakan tanggal trading terakhir yang EOD-nya sudah final.
        tz_jakarta = pytz.timezone('Asia/Jakarta')
        now_jakarta = datetime.now(tz_jakarta)
        today = now_jakarta.date()
        
        query_date = target_date
        
        # RULE 1: Jika query_date >= hari ini, shift ke kemarin karena
        # EOD hari ini belum tersedia (market belum tutup atau baru tutup).
        # Bahkan jika sudah lewat jam 16:00, GoAPI kadang delay 1-2 jam.
        if query_date >= today:
            query_date = today - timedelta(days=1)
        
        # RULE 2: Selalu skip weekend (Sabtu/Minggu → mundur ke Jumat)
        while query_date.weekday() >= 5:
            query_date = query_date - timedelta(days=1)
        
        logger.info(f"[DataProvider] Broker summary {ticker}: target_date={target_date} → query_date={query_date}")

        # ------------------------------------------------------------------ #
        #  Cache check: Look backwards up to 10 hari untuk menemukan data cache
        # ------------------------------------------------------------------ #
        temp_date = query_date
        for attempt in range(10):
            cached_df = self._get_cached_broker_summary(ticker, temp_date)
            if cached_df is not None:
                logger.info(f"[DataProvider] Cache HIT: broker summary {ticker} on {temp_date} (attempt {attempt+1})")
                return cached_df
            
            # Go back one day
            temp_date = temp_date - timedelta(days=1)
            while temp_date.weekday() >= 5:
                temp_date = temp_date - timedelta(days=1)

        url = f"https://api.goapi.io/stock/idx/{ticker}/broker_summary"
        results = []
        
        # Loop backwards up to 5 days to handle holidays
        for attempt in range(5):
            params = {
                "date": str(query_date)
            }
            try:
                data = self._make_goapi_request(url, params)
                results = data.get("data", {}).get("results", [])
                if results:
                    logger.info(f"Found GoAPI broker summary for {ticker} on date {query_date}")
                    break
            except Exception as e:
                logger.warning(f"Failed to fetch GoAPI broker summary for {query_date}: {e}")
                if "All configured GoAPI keys failed" in str(e):
                    raise e
                
            # Go back one day
            query_date = query_date - timedelta(days=1)
            # Skip weekends
            while query_date.weekday() >= 5:
                query_date = query_date - timedelta(days=1)
        
        foreign_brokers = {"AK", "BK", "KZ", "RX", "AG", "YU"}
        
        rows = []
        for row in results:
            # GoAPI fields: code (broker code), side (BUY/SELL), lot (in lots), value (in IDR)
            broker_code = row.get("code", "UNKNOWN")
            side = row.get("side") or "BUY"
            lot = abs(int(row.get("lot") or 0))
            value = abs(float(row.get("value") or 0))
            
            # Map based on BUY or SELL side
            if side == "BUY":
                buy_lot = lot
                sell_lot = 0
                net_lot = lot
                buy_value = value
                sell_value = 0.0
            else:
                buy_lot = 0
                sell_lot = lot
                net_lot = -lot
                buy_value = 0.0
                sell_value = value
            
            # Broker categories:
            # SM: CC, BK, KZ, AK, AG, RX
            # FG: AK, BK, KZ, RX, AG, YU
            # DI: NI, ZP, LG, MG, OD, SQ, DX, GR, CP, TP, EP, IF, BB
            # RT: XL, PD, YP, XC, KK
            if broker_code in {"CC", "BK", "KZ", "AK", "AG", "RX"}:
                broker_cat = "SM"
            elif broker_code in {"AK", "BK", "KZ", "RX", "AG", "YU"}:
                broker_cat = "FG"
            elif broker_code in {"NI", "ZP", "LG", "MG", "OD", "SQ", "DX", "GR", "CP", "TP", "EP", "IF", "BB"}:
                broker_cat = "DI"
            elif broker_code in {"XL", "PD", "YP", "XC", "KK"}:
                broker_cat = "RT"
            else:
                broker_cat = "RT"
            
            rows.append({
                "date": query_date,
                "broker_code": broker_code,
                "buy_lot": buy_lot,
                "sell_lot": sell_lot,
                "net_lot": net_lot,
                "buy_value": buy_value,
                "sell_value": sell_value,
                "investor_type": "foreign" if broker_code in foreign_brokers else "domestic",
                "broker_category": broker_cat,
            })
            
        df = pd.DataFrame(rows)
        logger.info(f"Fetched {len(df)} broker rows for {ticker} from GoAPI")
        
        # Save EOD broker summary to SQLite DB cache
        if not df.empty:
            self._save_broker_summary_cache(ticker, query_date, df)
            
        return df

    # ------------------------------------------------------------------ #
    #  Foreign Flow Cache (SQLite)
    # ------------------------------------------------------------------ #

    def _get_cached_foreign_flow(self, ticker: str, query_date: date) -> Optional[pd.DataFrame]:
        """Check if foreign flow for ticker/date is cached in SQLite."""
        import sqlite3, os
        db_url = settings.DATABASE_URL_SYNC
        db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "./idx_signal_bot.db"
        if not os.path.exists(db_path):
            return None
        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query("""
                SELECT date, foreign_buy_lot, foreign_sell_lot, foreign_net_lot,
                       foreign_buy_value, foreign_sell_value, foreign_net_value,
                       foreign_participation_percent
                FROM foreign_flow_cache
                WHERE ticker = ? AND date = ?
            """, conn, params=(ticker, str(query_date)))
            conn.close()
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"]).dt.date
                logger.info(f"[DataProvider] Cache HIT: foreign flow {ticker} on {query_date}")
                return df
        except Exception:
            pass  # Tabel belum ada, akan dibuat saat save
        return None

    def _save_foreign_flow_cache(self, ticker: str, data_rows: list):
        """Save foreign flow rows to SQLite cache table."""
        if not data_rows:
            return
        import sqlite3, os
        db_url = settings.DATABASE_URL_SYNC
        db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "./idx_signal_bot.db"
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Buat tabel jika belum ada
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS foreign_flow_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    foreign_buy_lot INTEGER DEFAULT 0,
                    foreign_sell_lot INTEGER DEFAULT 0,
                    foreign_net_lot INTEGER DEFAULT 0,
                    foreign_buy_value REAL DEFAULT 0,
                    foreign_sell_value REAL DEFAULT 0,
                    foreign_net_value REAL DEFAULT 0,
                    foreign_participation_percent REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, date)
                )
            """)
            for row in data_rows:
                cursor.execute("""
                    INSERT OR REPLACE INTO foreign_flow_cache
                    (ticker, date, foreign_buy_lot, foreign_sell_lot, foreign_net_lot,
                     foreign_buy_value, foreign_sell_value, foreign_net_value, foreign_participation_percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticker, str(row["date"]),
                    int(row.get("foreign_buy_lot", 0)),
                    int(row.get("foreign_sell_lot", 0)),
                    int(row.get("foreign_net_lot", 0)),
                    float(row.get("foreign_buy_value", 0)),
                    float(row.get("foreign_sell_value", 0)),
                    float(row.get("foreign_net_value", 0)),
                    float(row.get("foreign_participation_percent", 0)),
                ))
            conn.commit()
            conn.close()
            logger.info(f"[DataProvider] Saved {len(data_rows)} foreign flow rows to cache for {ticker}")
        except Exception as e:
            logger.warning(f"[DataProvider] Failed to save foreign flow cache: {e}")

    def _generate_mock_broker_summary(
        self, ticker: str, target_date: date, days: int
    ) -> pd.DataFrame:
        """Generate mock broker summary data."""
        import zlib
        seed = zlib.adler32((ticker + "broker").encode('utf-8'))
        np.random.seed(seed)

        broker_codes = ["YP", "CC", "DX", "AK", "KS", "MS", "RX", "GR", "PD", "BK",
                        "AI", "DB", "CG", "ML", "NI", "OD", "SQ", "KK", "TP", "ZP"]
        categories = ["SM", "DI", "FG", "RT", "AK", "OD"]
        inv_types = ["domestic", "foreign"]

        dates = pd.bdate_range(end=target_date, periods=days)
        rows = []

        for d in dates:
            n_brokers = np.random.randint(5, 15)
            selected = np.random.choice(broker_codes, n_brokers, replace=False)
            for bc in selected:
                buy_lot = int(np.random.lognormal(8, 2))
                sell_lot = int(np.random.lognormal(8, 2))
                avg_price = np.random.uniform(500, 15000)
                rows.append({
                    "date": d.date(),
                    "broker_code": bc,
                    "buy_lot": buy_lot,
                    "sell_lot": sell_lot,
                    "net_lot": buy_lot - sell_lot,
                    "buy_value": buy_lot * 100 * avg_price,
                    "sell_value": sell_lot * 100 * avg_price,
                    "investor_type": np.random.choice(inv_types, p=[0.7, 0.3]),
                    "broker_category": np.random.choice(categories),
                })

        df = pd.DataFrame(rows)
        logger.info(f"Generated {len(df)} mock broker rows for {ticker}")
        return df

    # ------------------------------------------------------------------ #
    #  Foreign Flow
    # ------------------------------------------------------------------ #

    def get_foreign_flow(
        self, ticker: str, target_date: Optional[date] = None, days: int = 30
    ) -> pd.DataFrame:
        """
        Returns foreign flow DataFrame — prioritas: real data (cache + GoAPI).
        Hanya fallback ke mock jika tidak ada GoAPI key dan provider bukan yfinance.
        
        Logika baru:
        1. Kumpulkan data real dari SQLite cache untuk setiap trading day
        2. Untuk hari yang cache miss, coba GoAPI (max 5 API calls)
        3. Sisanya fill dari broker_summary cache (fallback)
        4. Jika total data real < 5 hari, fallback ke mock penuh
        """
        from datetime import datetime
        import pytz

        if target_date is None:
            target_date = date.today()

        # Pastikan target_date tidak di masa depan dan skip weekend
        tz_jakarta = pytz.timezone('Asia/Jakarta')
        now_jakarta = datetime.now(tz_jakarta)
        today = now_jakarta.date()

        if target_date >= today:
            target_date = today - timedelta(days=1)
        while target_date.weekday() >= 5:
            target_date = target_date - timedelta(days=1)

        # Jika tidak punya Supabase key maupun GoAPI keys, langsung mock
        if not self.supabase_key and not self.goapi_keys:
            if self.provider in ("yfinance", "api"):
                logger.warning("Foreign flow not available via yfinance and Supabase/GOAPI_KEY not set — using mock")
            return self._generate_mock_foreign_flow(ticker, target_date, days)

        # --- Kumpulkan data real dari cache + GoAPI ---
        real_rows = []
        goapi_calls = 0
        max_goapi_calls = 5  # Limit API calls per ticker

        # Generate list of business days to check
        check_date = target_date
        dates_to_check = []
        for _ in range(days):
            dates_to_check.append(check_date)
            check_date = check_date - timedelta(days=1)
            while check_date.weekday() >= 5:
                check_date = check_date - timedelta(days=1)

        foreign_brokers = {"AK", "BK", "KZ", "RX", "AG", "YU"}

        for q_date in dates_to_check:
            # 1. Cek SQLite foreign_flow_cache
            cached_ff = self._get_cached_foreign_flow(ticker, q_date)
            if cached_ff is not None and not cached_ff.empty:
                row = cached_ff.iloc[0]
                real_rows.append({
                    "date": q_date,
                    "foreign_buy_lot": int(row["foreign_buy_lot"]),
                    "foreign_sell_lot": int(row["foreign_sell_lot"]),
                    "foreign_net_lot": int(row["foreign_net_lot"]),
                    "foreign_buy_value": float(row["foreign_buy_value"]),
                    "foreign_sell_value": float(row["foreign_sell_value"]),
                    "foreign_net_value": float(row["foreign_net_value"]),
                    "foreign_participation_percent": float(row.get("foreign_participation_percent", 0)),
                })
                continue

            # 2. Cek broker_summary cache (derive FF dari sana)
            cached_broker = self._get_cached_broker_summary(ticker, q_date)
            if cached_broker is not None and not cached_broker.empty:
                foreign_rows = cached_broker[cached_broker["broker_code"].isin(foreign_brokers)]
                buy_lot = int(foreign_rows["buy_lot"].sum())
                sell_lot = int(foreign_rows["sell_lot"].sum())
                buy_val = float(foreign_rows["buy_value"].sum())
                sell_val = float(foreign_rows["sell_value"].sum())
                real_rows.append({
                    "date": q_date,
                    "foreign_buy_lot": buy_lot,
                    "foreign_sell_lot": sell_lot,
                    "foreign_net_lot": buy_lot - sell_lot,
                    "foreign_buy_value": buy_val,
                    "foreign_sell_value": sell_val,
                    "foreign_net_value": buy_val - sell_val,
                    "foreign_participation_percent": 0,
                })
                continue

            # 3. Live GoAPI call (hanya jika ada goapi_keys dan limit belum habis)
            if not self.goapi_keys or goapi_calls >= max_goapi_calls:
                continue

            url = f"https://api.goapi.io/stock/idx/{ticker}/broker_summary"
            try:
                data = self._make_goapi_request(url, {"date": str(q_date)})
                results = data.get("data", {}).get("results", [])
                if results:
                    buy_lot = sum(abs(int(r.get("lot") or 0)) for r in results if r.get("side") == "BUY" and r.get("code", "") in foreign_brokers)
                    sell_lot = sum(abs(int(r.get("lot") or 0)) for r in results if r.get("side") == "SELL" and r.get("code", "") in foreign_brokers)
                    buy_val = sum(abs(float(r.get("value") or 0)) for r in results if r.get("side") == "BUY" and r.get("code", "") in foreign_brokers)
                    sell_val = sum(abs(float(r.get("value") or 0)) for r in results if r.get("side") == "SELL" and r.get("code", "") in foreign_brokers)
                    real_rows.append({
                        "date": q_date,
                        "foreign_buy_lot": buy_lot,
                        "foreign_sell_lot": sell_lot,
                        "foreign_net_lot": buy_lot - sell_lot,
                        "foreign_buy_value": buy_val,
                        "foreign_sell_value": sell_val,
                        "foreign_net_value": buy_val - sell_val,
                        "foreign_participation_percent": 0,
                    })
                    goapi_calls += 1
            except Exception as e:
                logger.warning(f"GoAPI foreign flow fetch failed for {ticker} on {q_date}: {e}")
                if "All configured GoAPI keys failed" in str(e):
                    break
                goapi_calls += 1  # Count failed attempts too

        # --- Build DataFrame ---
        if len(real_rows) >= 5:
            # Simpan data baru ke cache
            new_rows = [r for r in real_rows if self._get_cached_foreign_flow(ticker, r["date"]) is None]
            if new_rows:
                self._save_foreign_flow_cache(ticker, new_rows)

            df = pd.DataFrame(real_rows)
            df = df.sort_values("date").reset_index(drop=True)
            logger.info(f"[DataProvider] Foreign flow {ticker}: {len(df)} real data rows collected")
            return df
        else:
            # Tidak cukup data real, fallback ke mock
            logger.warning(f"[DataProvider] Foreign flow {ticker}: only {len(real_rows)} real rows, falling back to mock")
            return self._generate_mock_foreign_flow(ticker, target_date, days)

    def _generate_mock_foreign_flow(
        self, ticker: str, target_date: date, days: int
    ) -> pd.DataFrame:
        """Generate mock foreign flow data."""
        import zlib
        seed = zlib.adler32((ticker + "ff").encode('utf-8'))
        np.random.seed(seed)

        dates = pd.bdate_range(end=target_date, periods=days)
        rows = []

        for d in dates:
            fb = int(np.random.lognormal(9, 1.5))
            fs = int(np.random.lognormal(9, 1.5))
            avg_price = np.random.uniform(500, 15000)
            rows.append({
                "date": d.date(),
                "foreign_buy_lot": fb,
                "foreign_sell_lot": fs,
                "foreign_net_lot": fb - fs,
                "foreign_buy_value": fb * 100 * avg_price,
                "foreign_sell_value": fs * 100 * avg_price,
                "foreign_net_value": (fb - fs) * 100 * avg_price,
                "foreign_participation_percent": np.random.uniform(5, 45),
            })

        df = pd.DataFrame(rows)
        logger.info(f"Generated {len(df)} mock foreign flow rows for {ticker}")
        return df
