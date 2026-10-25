"""
IDX AI Signal Bot - Backtest Engine
Simulates the scoring engine on historical data to measure performance.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

from services.technical_engine import TechnicalEngine
from services.pattern_engine import PatternEngine
from services.candle_engine import CandleEngine
from services.scoring_engine import ScoringEngine
from services.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a simulated trade."""
    ticker: str
    entry_date: date
    entry_price: float
    exit_date: Optional[date] = None
    exit_price: float = 0
    signal: str = "BUY"
    tp1: float = 0
    stop_loss: float = 0
    pnl_percent: float = 0
    is_win: bool = False
    holding_days: int = 0
    exit_reason: str = ""


@dataclass
class BacktestReport:
    """Complete backtest results."""
    strategy_name: str
    ticker: str
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    winrate: float = 0
    profit_factor: float = 0
    expectancy: float = 0
    max_drawdown: float = 0
    average_gain: float = 0
    average_loss: float = 0
    avg_holding_days: float = 0
    sharpe_ratio: float = 0
    tested_from: Optional[date] = None
    tested_to: Optional[date] = None
    trades: List[Trade] = field(default_factory=list)


class BacktestEngine:
    """
    Simulates the scoring engine on historical data.
    Uses walk-forward methodology to avoid overfitting.
    """

    def __init__(self, max_holding_period: int = 10):
        self.max_holding = max_holding_period
        self.scoring_engine = ScoringEngine()
        self.risk_engine = RiskEngine()

    def run(
        self,
        ticker: str,
        ohlcv_df: pd.DataFrame,
        broker_df: pd.DataFrame = None,
        ff_df: pd.DataFrame = None,
        min_lookback: int = 60,
    ) -> BacktestReport:
        """
        Run backtest on historical OHLCV data.
        Simulates day-by-day scoring and trade execution.
        """
        report = BacktestReport(
            strategy_name="Saber Trader_v1",
            ticker=ticker,
            tested_from=ohlcv_df["date"].iloc[min_lookback] if len(ohlcv_df) > min_lookback else None,
            tested_to=ohlcv_df["date"].iloc[-1] if len(ohlcv_df) > 0 else None,
        )

        if len(ohlcv_df) < min_lookback + 20:
            logger.warning(f"[{ticker}] Insufficient data for backtest")
            return report

        trades: List[Trade] = []
        in_trade = False
        current_trade: Optional[Trade] = None

        # Walk through each trading day
        for i in range(min_lookback, len(ohlcv_df)):
            current_date = ohlcv_df["date"].iloc[i]
            current_close = ohlcv_df["close"].iloc[i]
            current_high = ohlcv_df["high"].iloc[i]
            current_low = ohlcv_df["low"].iloc[i]

            # Check exit conditions if in a trade
            if in_trade and current_trade:
                holding = (current_date - current_trade.entry_date).days

                # Check stop loss hit
                if current_low <= current_trade.stop_loss:
                    current_trade.exit_date = current_date
                    current_trade.exit_price = current_trade.stop_loss
                    current_trade.exit_reason = "stop_loss"
                    self._finalize_trade(current_trade)
                    trades.append(current_trade)
                    in_trade = False
                    continue

                # Check TP hit
                if current_high >= current_trade.tp1:
                    current_trade.exit_date = current_date
                    current_trade.exit_price = current_trade.tp1
                    current_trade.exit_reason = "tp1_hit"
                    self._finalize_trade(current_trade)
                    trades.append(current_trade)
                    in_trade = False
                    continue

                # Check max holding period
                if holding >= self.max_holding:
                    current_trade.exit_date = current_date
                    current_trade.exit_price = current_close
                    current_trade.exit_reason = "max_holding"
                    self._finalize_trade(current_trade)
                    trades.append(current_trade)
                    in_trade = False
                    continue

            # Generate signal if not in trade
            if not in_trade:
                window = ohlcv_df.iloc[max(0, i - min_lookback):i + 1].copy()
                window = window.reset_index(drop=True)

                try:
                    technical = TechnicalEngine(window).compute_all()
                    patterns = PatternEngine(window).detect_all()
                    candles = CandleEngine(window).detect_all()

                    # Catatan: backtest tidak punya data broker/asing real-time.
                    # Menggunakan {} untuk keduanya → skor bandarmology & foreign flow = 0.
                    # Ini adalah WORST-CASE scenario (hanya teknikal murni).
                    # Threshold sinyal diturunkan ke WATCHLIST agar backtest tetap bisa menghasilkan
                    # trade dan memberikan gambaran WR teknikal engine secara isolated.
                    score_result = self.scoring_engine.score(
                        ticker=ticker, technical=technical,
                        pattern=patterns, candle=candles,
                        bandarmology={}, foreign_flow={},
                        ohlcv_df=window,
                    )

                    # Tangkap BUY, STRONG BUY, dan WATCHLIST (atau total_score >= 45 untuk technical murni tanpa data broker)
                    BACKTEST_ENTRY_SIGNALS = {"BUY", "STRONG BUY", "WATCHLIST"}
                    trade_signal = score_result.signal if score_result.signal in BACKTEST_ENTRY_SIGNALS else ("BUY" if score_result.total_score >= 45.0 else None)
                    if trade_signal and not score_result.hard_filter_failed:
                        risk = self.risk_engine.calculate_from_ohlcv(window, signal=trade_signal)
                        current_trade = Trade(
                            ticker=ticker,
                            entry_date=current_date,
                            entry_price=current_close,
                            signal=trade_signal,
                            tp1=risk.tp1,
                            stop_loss=risk.stop_loss_conservative,
                        )
                        in_trade = True

                except Exception as e:
                    logger.debug(f"Backtest scoring error at {current_date}: {e}")

        # Close any open trade at end
        if in_trade and current_trade:
            current_trade.exit_date = ohlcv_df["date"].iloc[-1]
            current_trade.exit_price = ohlcv_df["close"].iloc[-1]
            current_trade.exit_reason = "end_of_data"
            self._finalize_trade(current_trade)
            trades.append(current_trade)

        # Compute metrics
        report.trades = trades
        self._compute_metrics(report)

        logger.info(
            f"[{ticker}] Backtest: {report.total_trades} trades, "
            f"WR: {report.winrate:.1f}%, PF: {report.profit_factor:.2f}"
        )

        return report

    def _finalize_trade(self, trade: Trade):
        """Calculate P&L for a completed trade."""
        if trade.entry_price > 0:
            trade.pnl_percent = ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100
        trade.is_win = trade.pnl_percent > 0
        if trade.entry_date and trade.exit_date:
            trade.holding_days = (trade.exit_date - trade.entry_date).days

    def _compute_metrics(self, report: BacktestReport):
        """Compute all backtest performance metrics."""
        trades = report.trades
        report.total_trades = len(trades)

        if not trades:
            return

        wins = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]

        report.win_trades = len(wins)
        report.loss_trades = len(losses)
        report.winrate = (len(wins) / len(trades)) * 100

        gains = [t.pnl_percent for t in wins]
        loss_vals = [abs(t.pnl_percent) for t in losses]

        report.average_gain = np.mean(gains) if gains else 0
        report.average_loss = np.mean(loss_vals) if loss_vals else 0

        total_gain = sum(gains) if gains else 0
        total_loss = sum(loss_vals) if loss_vals else 1
        report.profit_factor = total_gain / total_loss if total_loss > 0 else 0

        # Expectancy
        if report.total_trades > 0:
            wr = report.winrate / 100
            report.expectancy = (wr * report.average_gain) - ((1 - wr) * report.average_loss)

        # Max drawdown
        pnls = [t.pnl_percent for t in trades]
        cumulative = np.cumsum(pnls)
        peak = np.maximum.accumulate(cumulative)
        drawdown = peak - cumulative
        report.max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0

        # Average holding days
        report.avg_holding_days = np.mean([t.holding_days for t in trades])

        # Sharpe ratio (simplified — daily returns)
        if len(pnls) > 1:
            report.sharpe_ratio = round(np.mean(pnls) / np.std(pnls) * np.sqrt(252), 2) if np.std(pnls) > 0 else 0

    def report_to_dict(self, report: BacktestReport) -> Dict[str, Any]:
        """Convert report to dict for storage/API."""
        return {
            "strategy_name": report.strategy_name,
            "ticker": report.ticker,
            "total_trades": report.total_trades,
            "win_trades": report.win_trades,
            "loss_trades": report.loss_trades,
            "winrate": round(report.winrate, 2),
            "profit_factor": round(report.profit_factor, 2),
            "expectancy": round(report.expectancy, 2),
            "max_drawdown": round(report.max_drawdown, 2),
            "average_gain": round(report.average_gain, 2),
            "average_loss": round(report.average_loss, 2),
            "avg_holding_days": round(report.avg_holding_days, 1),
            "sharpe_ratio": report.sharpe_ratio,
            "tested_from": str(report.tested_from),
            "tested_to": str(report.tested_to),
        }
