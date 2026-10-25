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
    Uses HTML parse mode for rich formatting.
    """
    ticker = signal_data.get("ticker", "???")
    name = signal_data.get("name", "")
    signal = signal_data.get("signal", "AVOID")
    confidence = signal_data.get("confidence_score", 1)
    confidence_label = signal_data.get("confidence_label", "LOW")
    raw_score = signal_data.get("raw_score", 0)
    sector = signal_data.get("sector", "")

    emoji = SIGNAL_EMOJI.get(signal, "⚪")
    bar = CONFIDENCE_BAR.get(confidence, "░░░░░░░░░░")

    entry = signal_data.get("entry_price", 0)
    tp1 = signal_data.get("tp1", 0)
    tp2 = signal_data.get("tp2", 0)
    tp3 = signal_data.get("tp3", 0)
    sl_atr = signal_data.get("stop_loss_atr", 0)
    sl_mod = signal_data.get("stop_loss_moderate", 0)
    sl_cons = signal_data.get("stop_loss_conservative", 0)
    rr = signal_data.get("risk_reward_ratio", 0)

    # Category scores
    cat_scores = signal_data.get("category_scores", {})
    trend = cat_scores.get("trend_momentum", 0)
    vol = cat_scores.get("volume_liquidity", 0)
    pattern = cat_scores.get("pattern", 0)
    sr = cat_scores.get("support_resistance", 0)
    bandar = cat_scores.get("bandarmology", 0)
    ff = cat_scores.get("foreign_flow", 0)
    risk = cat_scores.get("risk_reward", 0)

    # Patterns
    patterns = signal_data.get("patterns", {})
    pattern_list = patterns.get("patterns", [])
    candles = signal_data.get("candles", {})
    candle_list = candles.get("candle_patterns", [])

    # Bandarmology
    bandar_data = signal_data.get("bandarmology", {})
    bandar_signal = bandar_data.get("bandar_signal", "neutral")

    # Foreign flow
    ff_data = signal_data.get("foreign_flow", {})
    ff_signal = ff_data.get("ff_signal", "neutral")

    # News
    news = signal_data.get("news", {})
    headlines = news.get("headlines", [])

    # Analyst opinion
    opinion = signal_data.get("analyst_opinion", "")
    if opinion and len(opinion) > 3200:
        opinion = opinion[:3197] + "..."

    msg = f"""
{emoji} <b>SIGNAL: {signal}</b> {emoji}
━━━━━━━━━━━━━━━━━━━━━━

📌 <b>{ticker}</b> — {name}
🏢 Sektor: {sector}"""

    ihsg = signal_data.get("ihsg_regime")
    if ihsg:
        regime_emoji = "🟢" if ihsg.get("regime") == "BULLISH" else ("🔴" if ihsg.get("regime") == "BEARISH" else "🟡")
        msg += f"\n🌍 IHSG Regime: <b>{regime_emoji} {ihsg.get('regime')}</b>"

    # Multi-Timeframe daily trend (if available)
    technical = signal_data.get("technical", {})
    daily_trend = technical.get("daily_trend_bias")
    if daily_trend:
        dtf_emoji = "🟢" if daily_trend == "bullish" else ("🔴" if daily_trend == "bearish" else "🟡")
        msg += f"\n📊 Daily Trend: <b>{dtf_emoji} {daily_trend.upper()}</b>"

    msg += f"""
📊 Score: <b>{raw_score}/100</b>
🎯 Confidence: <b>{confidence}/10 ({confidence_label})</b>
{bar}"""

    # Fibonacci levels (for WATCHLIST)
    fib_levels = signal_data.get("fib_levels", {})

    if signal in ("BUY", "STRONG BUY", "WATCHLIST"):
        if signal == "WATCHLIST" and fib_levels:
            # Display Fibonacci-based entry & TP for WATCHLIST
            swing_low  = fib_levels.get("swing_low", 0)
            swing_high = fib_levels.get("swing_high", 0)
            fib_0382   = fib_levels.get("fib_0382", 0)
            fib_05     = fib_levels.get("fib_05", 0)
            fib_0618   = fib_levels.get("fib_0618", entry)   # Entry
            fib_1618   = fib_levels.get("fib_1618", tp1)     # TP
            fib_2618   = fib_levels.get("fib_2618", 0)
            
            is_below = fib_levels.get("is_below_fib", False)
            
            msg += f"""

📌 <b>Fibonacci Analysis (WATCHLIST)</b>
📐 Swing Low : <code>Rp{swing_low:,.0f}</code>
📐 Swing High: <code>Rp{swing_high:,.0f}</code>"""

            if is_below:
                entry_discount = fib_levels.get("entry_discount", entry)
                sl_discount = fib_levels.get("sl_discount", sl_cons)
                entry_confirm = fib_levels.get("entry_confirm", fib_0618)
                sl_confirm = fib_levels.get("sl_confirm", sl_cons)
                
                rr_discount = round(abs(fib_1618 - entry_discount) / abs(entry_discount - sl_discount), 2) if (entry_discount - sl_discount) > 0 else 0
                rr_confirm = round(abs(fib_1618 - entry_confirm) / abs(entry_confirm - sl_confirm), 2) if (entry_confirm - sl_confirm) > 0 else 0
                
                msg += f"""

💡 Harga saat ini (Rp{entry_discount:,.0f}) sudah di bawah Fib 0.618 (Rp{entry_confirm:,.0f}). Pilih opsi entry berikut:

🛒 <b>Opsi 1: Buy on Weakness (Discount)</b>
├─ Entry (Harga Sekarang): <code>Rp{entry_discount:,.0f}</code>
├─ Stop Loss            : <code>Rp{sl_discount:,.0f}</code>
└─ R:R Ratio            : <code>{rr_discount:.2f}</code>

🚀 <b>Opsi 2: Buy on Strength (Konfirmasi)</b>
├─ Entry (Trigger Rebound): <code>Rp{entry_confirm:,.0f}</code>
├─ Stop Loss            : <code>Rp{sl_confirm:,.0f}</code>
└─ R:R Ratio            : <code>{rr_confirm:.2f}</code>

🎯 <b>Target Penjualan (TP)</b>
├─ TP1 (Fib 1.618)   : <code>Rp{fib_1618:,.0f}</code>
└─ TP2 (Fib 2.618)   : <code>Rp{fib_2618:,.0f}</code>"""
            else:
                msg += f"""

💰 <b>Risk Management — Fib Based</b>
├─ Entry (Fib 0.618) : <code>Rp{fib_0618:,.0f}</code>
├─ Fib 0.5          : <code>Rp{fib_05:,.0f}</code>
├─ Fib 0.382        : <code>Rp{fib_0382:,.0f}</code>
├─ TP (Fib 1.618)   : <code>Rp{fib_1618:,.0f}</code>
├─ TP2 (Fib 2.618)  : <code>Rp{fib_2618:,.0f}</code>
├─ SL ATR           : <code>Rp{sl_atr:,.0f}</code>
├─ SL Moderat       : <code>Rp{sl_mod:,.0f}</code>
└─ R:R Ratio        : <code>{rr:.2f}</code>"""
        else:
            # BUY / STRONG BUY: tampilkan TP1/TP2/TP3 dengan panduan partial exit
            tp1_str = f"Rp{tp1:,.0f}" if tp1 else "-"
            tp2_str = f"Rp{tp2:,.0f}" if tp2 else "-"
            tp3_str = f"Rp{tp3:,.0f}" if tp3 else "-"
            msg += f"""

💰 <b>Risk Management</b>
├─ Entry        : <code>Rp{entry:,.0f}</code>
├─ TP1 (exit 50%): <code>{tp1_str}</code>
├─ TP2 (exit 30%): <code>{tp2_str}</code>
├─ TP3 (hold 20%): <code>{tp3_str}</code>
├─ SL ATR       : <code>Rp{sl_atr:,.0f}</code>
├─ SL Moderat   : <code>Rp{sl_mod:,.0f}</code>
├─ SL Konservatif: <code>Rp{sl_cons:,.0f}</code>
└─ R:R Ratio    : <code>{rr:.2f}</code>"""
    else:
        msg += f"""

⚠️ <b>Sinyal {signal}:</b> Tidak ada rekomendasi beli / rencana perdagangan. Saham dinilai kurang mendukung atau berisiko tinggi saat ini."""

    msg += f"""

📈 <b>Score Breakdown</b>
├─ Trend & Momentum: {trend:.0f}/25
├─ Volume & Liquidity: {vol:.0f}/15
├─ Pattern: {pattern:.0f}/15
├─ Support/Resistance: {sr:.0f}/10
├─ Bandarmology: {bandar:.0f}/15
├─ Foreign Flow: {ff:.0f}/10
└─ Risk/Reward: {risk:.0f}/10"""

    if pattern_list:
        msg += f"\n\n🔍 <b>Chart Patterns:</b> {', '.join(pattern_list)}"

    if candle_list:
        msg += f"\n🕯 <b>Candle Patterns:</b> {', '.join(candle_list)}"

    top_buyers = bandar_data.get("top_buyers", [])
    top_sellers = bandar_data.get("top_sellers", [])
    top_buyers_lots = bandar_data.get("top_buyers_lots", {})
    top_sellers_lots = bandar_data.get("top_sellers_lots", {})

    buyers_2 = top_buyers[:2]
    sellers_2 = top_sellers[::-1][:2]

    msg += f"\n\n🏦 <b>Bandarmology:</b> {bandar_signal.replace('_', ' ').title()}"
    if buyers_2:
        msg += "\n\n<b>Top Buyer:</b>"
        for b in buyers_2:
            lot = top_buyers_lots.get(b)
            if lot is not None and lot > 0:
                msg += f"\n- {b} : {lot:,} lot"
            else:
                msg += f"\n- {b}"
    if sellers_2:
        msg += "\n\n<b>Top Seller:</b>"
        for s in sellers_2:
            lot = top_sellers_lots.get(s)
            if lot is not None and lot > 0:
                msg += f"\n- {s} : {lot:,} lot"
            else:
                msg += f"\n- {s}"
        
    msg += f"\n\n🌐 <b>Foreign Flow:</b> {ff_signal.replace('_', ' ').title()}"

    if headlines:
        msg += "\n\n📰 <b>Berita Terkait:</b>"
        for h in headlines[:3]:
            msg += f"\n• {h}"

    if opinion:
        msg += f"\n\n💡 <b>Opini Analis:</b>\n{opinion}"

    msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━"
    msg += "\n⚠️ <i>Disclaimer: Bukan ajakan beli/jual. DYOR.</i>"
    msg += "\n🤖 <i>Saber Trader AI Signal Bot</i>"

    return msg.strip()


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
