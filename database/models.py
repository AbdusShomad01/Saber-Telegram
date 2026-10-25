"""
IDX AI Signal Bot - Database Models
All SQLAlchemy models for the IDX stock signal system.
"""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, Text, Date,
    DateTime, JSON, Index, UniqueConstraint
)
from sqlalchemy.sql import func
from database.db import Base


class Stock(Base):
    """Master table of all IDX stocks."""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100), nullable=True)
    subsector = Column(String(100), nullable=True)
    board = Column(String(50), nullable=True)  # Utama, Pengembangan, Akselerasi
    is_active = Column(Boolean, default=True, nullable=False)
    is_suspended = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_stocks_sector", "sector"),
        Index("idx_stocks_is_active", "is_active"),
    )


class OHLCVDaily(Base):
    """Daily OHLCV price data."""
    __tablename__ = "ohlcv_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    value = Column(Float, nullable=True)  # Transaction value in IDR
    frequency = Column(Integer, nullable=True)  # Number of transactions

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_ohlcv_daily_ticker_date"),
        Index("idx_ohlcv_daily_ticker_date", "ticker", "date"),
    )


class OHLCVIntraday(Base):
    """Intraday OHLCV price data."""
    __tablename__ = "ohlcv_intraday"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    datetime = Column(DateTime, nullable=False, index=True)
    interval = Column(String(10), nullable=False)  # "1m", "5m", "15m", "60m"
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    value = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("ticker", "datetime", "interval", name="uq_ohlcv_intraday_ticker_dt_int"),
        Index("idx_ohlcv_intraday_ticker_datetime", "ticker", "datetime"),
    )


class BrokerSummary(Base):
    """Broker summary data for bandarmology analysis."""
    __tablename__ = "broker_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    broker_code = Column(String(10), nullable=False)
    broker_name = Column(String(255), nullable=True)
    buy_lot = Column(BigInteger, default=0)
    sell_lot = Column(BigInteger, default=0)
    net_lot = Column(BigInteger, default=0)
    buy_value = Column(Float, default=0)
    sell_value = Column(Float, default=0)
    investor_type = Column(String(20), nullable=True)  # "domestic", "foreign"
    broker_category = Column(String(10), nullable=True)  # SM, DI, FG, RT, AK, OD, SQ, KK

    __table_args__ = (
        UniqueConstraint("ticker", "date", "broker_code", name="uq_broker_summary"),
        Index("idx_broker_summary_ticker_date", "ticker", "date"),
    )


class ForeignFlow(Base):
    """Foreign investor flow data."""
    __tablename__ = "foreign_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    foreign_buy_lot = Column(BigInteger, default=0)
    foreign_sell_lot = Column(BigInteger, default=0)
    foreign_net_lot = Column(BigInteger, default=0)
    foreign_buy_value = Column(Float, default=0)
    foreign_sell_value = Column(Float, default=0)
    foreign_net_value = Column(Float, default=0)
    foreign_participation_percent = Column(Float, default=0)

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_foreign_flow_ticker_date"),
        Index("idx_foreign_flow_ticker_date", "ticker", "date"),
    )


class News(Base):
    """News articles related to stocks."""
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    source = Column(String(100), nullable=True)
    url = Column(String(1000), nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    sentiment = Column(String(20), nullable=True)  # "positive", "neutral", "negative"
    summary = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_news_ticker_published", "ticker", "published_at"),
    )


class Signal(Base):
    """Generated trading signals."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    timeframe = Column(String(20), nullable=False, default="daily")
    signal = Column(String(20), nullable=False)  # STRONG BUY, BUY, WATCHLIST, NEUTRAL, SELL, AVOID
    raw_score = Column(Float, nullable=False)
    confidence_score = Column(Integer, nullable=False)  # 1-10
    confidence_label = Column(String(30), nullable=False)  # LOW, MEDIUM, HIGH CONVICTION, VERY HIGH
    entry_price = Column(Float, nullable=True)
    tp1 = Column(Float, nullable=True)
    tp2 = Column(Float, nullable=True)
    tp3 = Column(Float, nullable=True)
    stop_loss_atr = Column(Float, nullable=True)
    stop_loss_moderate = Column(Float, nullable=True)
    stop_loss_conservative = Column(Float, nullable=True)
    technical_json = Column(JSON, nullable=True)
    pattern_json = Column(JSON, nullable=True)
    bandarmology_json = Column(JSON, nullable=True)
    foreign_flow_json = Column(JSON, nullable=True)
    category_raw_json = Column(JSON, nullable=True)
    analyst_opinion = Column(Text, nullable=True)
    
    # Outcome tracking fields
    outcome_status = Column(String(20), default="PENDING", nullable=True)
    outcome_price = Column(Float, nullable=True)
    outcome_pnl_pct = Column(Float, nullable=True)
    outcome_checked_at = Column(DateTime, nullable=True)
    outcome_date = Column(Date, nullable=True)
    tp_hit = Column(Boolean, default=False, nullable=True)
    sl_hit = Column(Boolean, default=False, nullable=True)
    tp2_hit = Column(Boolean, default=False, nullable=True)
    max_price_seen = Column(Float, nullable=True)
    min_price_seen = Column(Float, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("idx_signals_ticker_created", "ticker", "created_at"),
        Index("idx_signals_signal", "signal"),
    )


class BacktestResult(Base):
    """Backtesting results for strategy validation."""
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(100), nullable=False)
    ticker = Column(String(10), nullable=True, index=True)
    timeframe = Column(String(20), nullable=False, default="daily")
    total_trades = Column(Integer, default=0)
    win_trades = Column(Integer, default=0)
    loss_trades = Column(Integer, default=0)
    winrate = Column(Float, default=0)
    profit_factor = Column(Float, default=0)
    expectancy = Column(Float, default=0)
    max_drawdown = Column(Float, default=0)
    average_gain = Column(Float, default=0)
    average_loss = Column(Float, default=0)
    tested_from = Column(Date, nullable=True)
    tested_to = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("idx_backtest_strategy_ticker", "strategy_name", "ticker"),
    )


class TradingViewAlert(Base):
    """TradingView webhook alerts storage."""
    __tablename__ = "tradingview_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    timeframe = Column(String(20), nullable=True)
    alert_type = Column(String(50), nullable=True)
    price = Column(Float, nullable=True)
    message = Column(Text, nullable=True)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
