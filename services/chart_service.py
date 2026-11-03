"""
IDX AI Signal Bot - Chart Service
Generates beautiful TradingView-style dark-mode stock charts using matplotlib.
"""

import os
import tempfile
if 'MPLCONFIGDIR' not in os.environ:
    os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()
import logging
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class ChartService:
    """Generates visual charts of stock prices and indicators."""

    @staticmethod
    def generate_chart(ticker: str, ohlcv_df: pd.DataFrame, output_dir: str = "temp_charts") -> str:
        """
        Generates a 3-subplot dark mode chart for a stock:
        - Subplot 1: Price Candlesticks + EMA 20 + EMA 50
        - Subplot 2: Volume Bars
        - Subplot 3: RSI (14)
        
        Returns the path to the saved PNG image.
        """
        if ohlcv_df.empty or len(ohlcv_df) < 15:
            logger.warning(f"Not enough data to plot chart for {ticker}")
            return ""

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        chart_path = os.path.join(output_dir, f"{ticker.lower()}_chart.png")

        try:
            # We only want to plot the last 60 trading days for clear visibility
            plot_df = ohlcv_df.tail(60).copy().reset_index(drop=True)
            n_rows = len(plot_df)

            # Compute technical indicators for plotting
            close_prices = plot_df["close"]
            ema_20 = close_prices.ewm(span=20, adjust=False).mean()
            ema_50 = close_prices.ewm(span=50, adjust=False).mean()

            # Compute VWAP
            tp = (plot_df["high"] + plot_df["low"] + plot_df["close"]) / 3
            tp_vol = tp * plot_df["volume"]
            
            try:
                dates_only = pd.to_datetime(plot_df["date"]).dt.date
            except Exception:
                dates_only = plot_df["date"]
                
            plot_df["_tp_vol"] = tp_vol
            plot_df["_date_only"] = dates_only
            
            cum_tp_vol = plot_df.groupby("_date_only")["_tp_vol"].cumsum()
            cum_vol = plot_df.groupby("_date_only")["volume"].cumsum()
            vwap = cum_tp_vol / cum_vol.replace(0, np.nan)
            vwap = vwap.fillna(tp)

            # Compute RSI (14) for plotting
            delta = close_prices.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.rolling(window=14, min_periods=14).mean()
            avg_loss = loss.rolling(window=14, min_periods=14).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            rsi = rsi.fillna(50)

            # Create Figure with subplots
            fig, (ax1, ax2, ax3) = plt.subplots(
                nrows=3, 
                ncols=1, 
                figsize=(10, 8), 
                sharex=True, 
                gridspec_kw={"height_ratios": [3, 1, 1.2]}
            )

            # Define Theme Colors (Dark Slate theme)
            bg_color = "#161a25"       # Main background
            panel_color = "#1e222d"    # Subplot panel background
            grid_color = "#2a2e39"     # Grid lines
            text_color = "#d1d4dc"     # Axis label/title text
            up_color = "#26a69a"       # Bullish candle/vol (Teal)
            down_color = "#ef5350"     # Bearish candle/vol (Red)
            ema20_color = "#ffb300"    # EMA 20 (Amber)
            ema50_color = "#2196f3"    # EMA 50 (Blue)
            vwap_color = "#e91e63"     # VWAP (Pink/Magenta)
            rsi_color = "#9c27b0"      # RSI (Purple)

            fig.patch.set_facecolor(bg_color)

            # ----------------------------------------------------
            #  SUBPLOT 1: PRICE CANDLESTICKS, EMAs & VWAP
            # ----------------------------------------------------
            ax1.set_facecolor(panel_color)
            ax1.grid(True, color=grid_color, linestyle="--", linewidth=0.5)

            # Draw Candlesticks using index as X to avoid weekend gaps
            for idx in range(n_rows):
                row = plot_df.iloc[idx]
                is_bullish = row["close"] >= row["open"]
                candle_color = up_color if is_bullish else down_color

                # Wick (High/Low)
                ax1.vlines(idx, row["low"], row["high"], color=candle_color, linewidth=1.2)
                # Body (Open/Close)
                body_bottom = min(row["open"], row["close"])
                body_top = max(row["open"], row["close"])
                body_height = max(body_top - body_bottom, (row["close"] * 0.001))
                ax1.bar(idx, body_height, bottom=body_bottom, color=candle_color, width=0.6, align="center")

            # Plot EMAs & VWAP
            ax1.plot(ema_20, color=ema20_color, label="EMA 20", linewidth=1.2)
            ax1.plot(ema_50, color=ema50_color, label="EMA 50", linewidth=1.2)
            ax1.plot(vwap, color=vwap_color, label="VWAP", linewidth=1.5, linestyle="--")

            # Check if dataset has intraday time components
            is_intraday = False
            if len(plot_df) > 0:
                first_date = plot_df["date"].iloc[0]
                if not isinstance(first_date, pd.Timestamp) and ":" in str(first_date):
                    is_intraday = True
                elif hasattr(first_date, "hour") and (first_date.hour != 0 or first_date.minute != 0):
                    is_intraday = True

            from app.config import get_settings
            interval_setting = get_settings().CHART_INTERVAL
            timeframe_label = f"Intraday ({interval_setting})" if is_intraday else "60D"
            ax1.set_title(f"{ticker.upper()} - {timeframe_label} Candlestick Chart", color=text_color, fontsize=14, fontweight="bold", pad=10)
            ax1.legend(loc="upper left", facecolor=panel_color, edgecolor=grid_color, labelcolor=text_color)
            ax1.tick_params(colors=text_color)
            ax1.yaxis.label.set_color(text_color)
            ax1.set_ylabel("Price (IDR)", fontsize=10)

            # ----------------------------------------------------
            #  SUBPLOT 2: VOLUME
            # ----------------------------------------------------
            ax2.set_facecolor(panel_color)
            ax2.grid(True, color=grid_color, linestyle="--", linewidth=0.5)

            # Volume bars colored by daily close direction
            vol_colors = [up_color if plot_df.iloc[i]["close"] >= plot_df.iloc[i]["open"] else down_color for i in range(n_rows)]
            ax2.bar(range(n_rows), plot_df["volume"], color=vol_colors, width=0.6)
            ax2.tick_params(colors=text_color)
            ax2.yaxis.label.set_color(text_color)
            ax2.set_ylabel("Volume", fontsize=10)

            # ----------------------------------------------------
            #  SUBPLOT 3: RSI
            # ----------------------------------------------------
            ax3.set_facecolor(panel_color)
            ax3.grid(True, color=grid_color, linestyle="--", linewidth=0.5)

            # Plot RSI Line
            ax3.plot(rsi, color=rsi_color, linewidth=1.5, label="RSI 14")
            
            # Reference Lines
            ax3.axhline(70, color=down_color, linestyle=":", alpha=0.7, linewidth=1)
            ax3.axhline(30, color=up_color, linestyle=":", alpha=0.7, linewidth=1)
            ax3.axhline(50, color=text_color, linestyle="--", alpha=0.3, linewidth=0.8)

            # Fill RSI between 30 and 70
            ax3.fill_between(range(n_rows), 30, 70, color=rsi_color, alpha=0.05)
            
            ax3.tick_params(colors=text_color)
            ax3.yaxis.label.set_color(text_color)
            ax3.set_ylabel("RSI", fontsize=10)
            ax3.set_ylim(10, 90)

            # ----------------------------------------------------
            #  X-AXIS LABELS (DATES / TIMES)
            # ----------------------------------------------------
            tick_step = max(1, n_rows // 6)
            ticks = range(0, n_rows, tick_step)
            
            date_labels = []
            for t in ticks:
                date_val = plot_df.iloc[t]["date"]
                if hasattr(date_val, "strftime"):
                    try:
                        # Show time if it's intraday (non-zero hour/minute)
                        if hasattr(date_val, "hour") and (date_val.hour != 0 or date_val.minute != 0):
                            date_labels.append(date_val.strftime("%d %b %H:%M"))
                        else:
                            date_labels.append(date_val.strftime("%d %b"))
                    except Exception:
                        date_labels.append(date_val.strftime("%d %b"))
                else:
                    date_labels.append(str(date_val)[:16])

            plt.xticks(ticks, date_labels, rotation=0, color=text_color)
            ax3.tick_params(colors=text_color)

            # Adjust layout
            plt.tight_layout()
            
            # Save chart
            plt.savefig(chart_path, facecolor=bg_color, edgecolor="none", dpi=150)
            plt.close(fig)
            
            logger.info(f"Successfully generated stock chart for {ticker} at {chart_path}")
            return chart_path

        except Exception as e:
            logger.error(f"Error generating chart for {ticker}: {e}", exc_info=True)
            return ""
