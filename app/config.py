"""
IDX AI Signal Bot - Application Configuration
Centralized configuration management using pydantic-settings.
All secrets loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/idx_signal_bot"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/idx_signal_bot"

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_MESSAGE_THREAD_ID: Optional[str] = None

    # --- BSJP Telegram (Beli Sore Jual Profit) ---
    BSJP_BOT_TOKEN: str = "9261989934:AAFO3q5Bs32pp4ElVyxYf-VufWaYj66rwPo"
    BSJP_CHAT_ID: str = "-1004302595573"
    BSJP_THREAD_ID: Optional[int] = 107

    # --- LLM API Keys ---
    CLAUDE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER: str = "claude"  # "claude" or "gemini"

    # --- TradingView Webhook ---
    TRADINGVIEW_WEBHOOK_SECRET: str = ""

    # --- GoAPI ---
    GOAPI_KEY: str = ""

    # --- Supabase ---
    SUPABASE_PROJECT_ID: str = ""
    SUPABASE_API_KEY: str = ""
    SUPABASE_URL: str = ""

    # --- Google Spreadsheet (SPS) Recap ---
    GOOGLE_SHEET_WEBHOOK_URL: str = ""
    GOOGLE_SHEET_VIEW_URL: str = ""

    # --- App Settings ---
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DAY_TRADE_MODE: bool = False
    CHART_INTERVAL: str = "1d"

    # --- Data Provider ---
    DATA_PROVIDER: str = "yfinance"  # "mock", "csv", "api", "yfinance"
    CSV_DATA_DIR: str = "./data/csv"

    # --- Liquidity Thresholds ---
    MIN_VALUE_BUY: float = 500_000_000  # Rp500 juta
    MIN_VALUE_CONFIDENCE: float = 1_000_000_000  # Rp1 miliar
    MIN_FREQUENCY: int = 50

    # --- Backtest Settings ---
    BACKTEST_MIN_SAMPLE: int = 30
    BACKTEST_MIN_WINRATE: float = 70.0
    BACKTEST_HIGH_WINRATE: float = 80.0
    MAX_HOLDING_PERIOD: int = 10

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
