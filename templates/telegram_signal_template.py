"""
IDX AI Signal Bot - Telegram Signal Template
Formats signal output into beautiful Telegram messages.
"""

SIGNAL_EMOJI = {
    "STRONG BUY": "🟢🟢",
    "BUY": "🟢",
    "WATCHLIST": "🟡",
    "AVOID": "🟠",
    "SELL": "🔴",
}

CONFIDENCE_BAR = {
    10: "██████████",
    9: "█████████░",
    8: "████████░░",
    7: "███████░░░",
    6: "██████░░░░",
    5: "█████░░░░░",
    4: "████░░░░░░",
    3: "███░░░░░░░",
    2: "██░░░░░░░░",
    1: "█░░░░░░░░░",
}


def format_signal_message(signal_data: dict) -> str:
    """
    Format a signal into a Telegram-ready message.
    Revamped according to user specifications.
    """
    ticker = signal_data.get("ticker", "???")
    signal = signal_data.get("signal", "WATCHLIST")

    # Syariah badge
    from services.stock_universe_service import is_syariah_stock
    is_syariah = signal_data.get("is_syariah")
    if is_syariah is None:
        is_syariah = is_syariah_stock(ticker)
    syariah_badge = "🟢 SYARIAH" if is_syariah else "🔴 NON-SYARIAH"

    # Prices & Targets
    entry = float(signal_data.get("entry_price") or 0)
    tp1 = float(signal_data.get("tp1") or 0)
    tp1_pct = ((tp1 - entry) / entry * 100) if (entry > 0 and tp1 > 0) else 0.0
    tp1_sign = "+" if tp1_pct >= 0 else ""

    # Stop Loss
    sl_atr = float(signal_data.get("stop_loss_atr") or 0)
    sl_atr_pct = ((sl_atr - entry) / entry * 100) if (entry > 0 and sl_atr > 0) else 0.0

    # Moderat (-5%) and Konservatif (-3%)
    from services.risk_engine import RiskEngine
    risk_eng = RiskEngine()
    sl_mod = float(signal_data.get("stop_loss_moderate") or risk_eng._round_tick(entry * 0.95))
    sl_cons = float(signal_data.get("stop_loss_conservative") or risk_eng._round_tick(entry * 0.97))

    # Technical
    tech = signal_data.get("technical", {})

    # MACD
    macd = float(tech.get("macd") or 0.0)
    macd_sig = float(tech.get("macd_signal") or 0.0)
    is_macd_bullish = macd > macd_sig
    macd_status = "🟢 Bullish" if is_macd_bullish else "🔴 Bearish"

    # RSI (14)
    rsi = float(tech.get("rsi") or 50.0)
    if tech.get("rsi_consistent_above_80"):
        rsi_status = "🟢 Super Momentum (>80 x4)"
    elif tech.get("rsi_reversal_down_from_80"):
        rsi_status = "🔴 Reversal Down (<80)"
    elif tech.get("rsi_consistent_below_30"):
        rsi_status = "🔴 Falling Knife (<30 x4)"
    elif tech.get("rsi_reversal_up_from_30"):
        rsi_status = "🟢 Bullish Bounce (>30)"
    elif rsi >= 70:
        rsi_status = "🔴 Overbought"
    elif rsi >= 60:
        rsi_status = "🟡 Overbought"
    elif rsi >= 50:
        rsi_status = "🟢 Bullish"
    elif rsi >= 40:
        rsi_status = "🟡 Neutral"
    elif rsi >= 30:
        rsi_status = "🟡 Oversold"
    else:
        rsi_status = "🟢 Oversold"

    # Volume (vs rata2 5hr)
    vol_5d_label = tech.get("volume_5d_label")
    if not vol_5d_label:
        current_vol = float(tech.get("volume_current") or 0)
        avg_vol_5 = float(tech.get("volume_avg_5") or 0)
        vol_pct = (current_vol / avg_vol_5 * 100) if avg_vol_5 > 0 else 100.0
        if vol_pct >= 200:
            vol_5d_label = f"Sangat Tinggi ({vol_pct:.0f}%) 🟢"
        elif vol_pct >= 120:
            vol_5d_label = f"Tinggi ({vol_pct:.0f}%) 🟢"
        elif vol_pct >= 80:
            vol_5d_label = f"Normal ({vol_pct:.0f}%) ⚪"
        elif vol_pct >= 40:
            vol_5d_label = f"Rendah ({vol_pct:.0f}%) 🟡"
        else:
            vol_5d_label = f"Sangat Rendah ({vol_pct:.0f}%) 🔴"

    # EMA 20/50
    ema20 = float(tech.get("ema_20") or 0.0)
    ema50 = float(tech.get("ema_50") or 0.0)
    ema_status = "🟢 Bullish" if (ema20 >= ema50 and ema20 > 0) else "🔴 Bearish"

    # VWAP
    vwap = float(tech.get("vwap") or 0.0)
    price_above_vwap = tech.get("price_above_vwap")
    if price_above_vwap is None:
        price_above_vwap = entry >= vwap if vwap > 0 else True
    vwap_status = "🟢 Above" if price_above_vwap else "🔴 Below"

    # ADX
    adx = float(tech.get("adx") or 0.0)
    if adx >= 40:
        adx_status = "🟢 Very Strong"
    elif adx >= 25:
        adx_status = "🟢 Strong"
    elif adx >= 20:
        adx_status = "🟡 Moderate"
    else:
        adx_status = "⚪ Weak"

    # BB
    bb_lower = float(tech.get("bb_lower") or 0.0)
    bb_upper = float(tech.get("bb_upper") or 0.0)

    # ATR
    atr = float(tech.get("atr") or 0.0)

    # Patterns
    patterns = signal_data.get("patterns", {})
    pattern_list = patterns.get("patterns", [])
    candles = signal_data.get("candles", {})
    candle_list = candles.get("candle_patterns", [])

    chart_pattern_str = f"{' + '.join(pattern_list)} ⚪" if pattern_list else "Konsolidasi / Netral ⚪"
    candle_pattern_str = f"{' + '.join(candle_list)} ⚪" if candle_list else "Netral ⚪"

    # Bandarmology
    bandar_data = signal_data.get("bandarmology", {})
    is_pure_tech = bool(signal_data.get("pure_technical", False))
    is_real = bandar_data.get("is_real_data", False)

    if is_pure_tech or not is_real or not bandar_data:
        bandar_str = "Data sedang maintenance"
    else:
        bandar_sig = bandar_data.get("bandar_signal", "neutral").replace("_", " ").title()
        top_buyers = bandar_data.get("top_buyers", [])
        top_sellers = bandar_data.get("top_sellers", [])
        if top_buyers and top_sellers:
            b_str = ", ".join(top_buyers[:2])
            s_str = ", ".join(top_sellers[::-1][:2])
            bandar_str = f"{bandar_sig} (Top Buyer: {b_str} | Top Seller: {s_str})"
        elif bandar_sig and bandar_sig != "Neutral":
            bandar_str = bandar_sig
        else:
            bandar_str = "Data sedang maintenance"

    # Beta & Volatilitas
    beta = float(tech.get("beta") or signal_data.get("beta") or 1.0)
    beta_label = tech.get("beta_label") or signal_data.get("beta_label")
    if not beta_label:
        if beta >= 1.5:
            beta_label = "Very High"
        elif beta >= 1.1:
            beta_label = "High"
        elif beta >= 0.8:
            beta_label = "Moderate"
        elif beta > 0:
            beta_label = "Low"
        else:
            beta_label = "Negative"
    volatility = float(tech.get("volatility") or signal_data.get("volatility") or 0.0)

    # Analyst Opinion
    opinion = signal_data.get("analyst_opinion", "").strip()
    if opinion and len(opinion) > 3200:
        opinion = opinion[:3197] + "..."

    # News Headlines
    news = signal_data.get("news", {})
    headlines = news.get("headlines", [])

    lines = [
        f"Saham: {ticker} {syariah_badge}",
        f"Signal: {signal}",
        "",
        "",
        f"💵 Entry Price: Rp{entry:,.0f}",
        f"🎯 TP1: Rp{tp1:,.0f} ({tp1_sign}{tp1_pct:.1f}%)",
        "",
        "Stop Loss:",
        f"Default (ATR): Rp{sl_atr:,.0f} ({sl_atr_pct:.1f}%)",
        f"Moderat (-5%): Rp{sl_mod:,.0f}",
        f"Konservatif (-3%): Rp{sl_cons:,.0f}",
        "",
        "📊 Technical:",
        f"- MACD: {macd:.2f} (Sig: {macd_sig:.2f}) {macd_status}",
        f"- RSI (14): {rsi:.2f} {rsi_status}",
        f"- Volume (vs rata2 5hr): {vol_5d_label}",
        f"- EMA 20/50: Rp{ema20:,.0f} / Rp{ema50:,.0f} {ema_status}",
        f"- VWAP: Rp{vwap:,.0f} {vwap_status}",
        f"- ADX: {adx:.2f} {adx_status}",
        f"- BB: [Rp{bb_lower:,.0f} - Rp{bb_upper:,.0f}]",
        f"- ATR: Rp{atr:,.0f}",
        "",
        "👁️ Pattern:",
        f"- Chart: {chart_pattern_str}",
        f"- Candle: {candle_pattern_str}",
        "",
        f"🏦 Bandarmology: {bandar_str}",
        "",
        f"📈 Beta: {beta:.2f} ({beta_label}) | Volatilitas: {volatility:.0f}%",
    ]

    if opinion:
        lines.append("")
        lines.append("💡 Analyst Opinion:")
        lines.append(opinion)

    if headlines:
        lines.append("")
        lines.append("📰 Berita Terkait:")
        for h in headlines[:3]:
            lines.append(f"• {h}")

    return "\n".join(lines).strip()



def format_scan_summary(signals: list) -> str:
    """Format a summary of top scan results."""
    if not signals:
        return "📊 <b>Scan Result</b>\n\nTidak ada sinyal yang terdeteksi."

    msg = "📊 <b>TOP SIGNALS — IDX Market Scan</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, s in enumerate(signals, 1):
        emoji = SIGNAL_EMOJI.get(s.get("signal", ""), "⚪")
        opinion = s.get("analyst_opinion", "").strip()
        
        # Truncate opinion to prevent Telegram message length limit (4096 chars)
        if len(opinion) > 250:
            opinion = opinion[:247] + "..."
            
        opinion_formatted = f"\n   💡 <i>{opinion}</i>" if opinion else ""
        
        msg += (
            f"{i}. {emoji} <b>{s['ticker']}</b> — {s['signal']} "
            f"(Score: {s['raw_score']}/100, Confidence: {s['confidence_score']}/10)\n"
            f"   Entry: Rp{s['entry_price']:,.0f} | TP1: Rp{s['tp1']:,.0f}"
            f"{opinion_formatted}\n\n"
        )

    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 Total: {len(signals)} sinyal\n"
    msg += "🤖 <i>Saber Trader AI Signal Bot</i>"

    return msg


def format_backtest_report(report: dict) -> str:
    """Format backtest results for Telegram."""
    wr = report.get("winrate", 0)
    wr_emoji = "🟢" if wr >= 70 else ("🟡" if wr >= 50 else "🔴")

    msg = f"""
📊 <b>BACKTEST REPORT</b>
━━━━━━━━━━━━━━━━━━━━━━

📌 Strategy: <b>{report.get('strategy_name', 'N/A')}</b>
📈 Ticker: <b>{report.get('ticker', 'ALL')}</b>
📅 Period: {report.get('tested_from', 'N/A')} → {report.get('tested_to', 'N/A')}

{wr_emoji} <b>Winrate: {wr:.1f}%</b>
├─ Total Trades: {report.get('total_trades', 0)}
├─ Win: {report.get('win_trades', 0)}
├─ Loss: {report.get('loss_trades', 0)}
├─ Profit Factor: {report.get('profit_factor', 0):.2f}
├─ Expectancy: {report.get('expectancy', 0):.2f}%
├─ Max Drawdown: {report.get('max_drawdown', 0):.2f}%
├─ Avg Gain: +{report.get('average_gain', 0):.2f}%
├─ Avg Loss: -{report.get('average_loss', 0):.2f}%
├─ Avg Hold: {report.get('avg_holding_days', 0):.1f} days
└─ Sharpe Ratio: {report.get('sharpe_ratio', 0):.2f}

━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>Saber Trader AI Signal Bot</i>
"""
    return msg.strip()
