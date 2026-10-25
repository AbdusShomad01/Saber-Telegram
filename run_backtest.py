import os, sys
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import json
import logging
import time
from datetime import datetime

# Setup logging minimal agar tidak banjir output
logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Import bot modules ──────────────────────────────────────────────
from services.data_provider_service import DataProviderService
from services.backtest_engine import BacktestEngine
from services.stock_universe_service import DEFAULT_STOCK_UNIVERSE

from datetime import date, datetime

# Ambil 20 saham paling likuid dari universe untuk backtest cepat
# (bisa ubah ke DEFAULT_STOCK_UNIVERSE untuk full run)
SAMPLE_UNIVERSE = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM",
    "ASII", "UNTR", "ADRO", "PTBA", "ANTM",
    "MDKA", "AMMN", "INDF", "ICBP", "KLBF",
    "CPIN", "TOWR", "EXCL", "BRIS", "PGAS",
]

START_DATE    = date(2013, 1, 1)   # Backtest dari tahun 2013
PERIOD_DAYS   = (date.today() - START_DATE).days
MAX_HOLDING   = 10    # maksimal holding 10 hari sebelum force exit
MIN_LOOKBACK  = 60    # minimal 60 bar sebelum mulai score


def fmt_pct(val: float) -> str:
    return f"{val:+.2f}%" if val != 0 else "0.00%"


def run_backtest():
    dp  = DataProviderService()
    bt  = BacktestEngine(max_holding_period=MAX_HOLDING)

    all_results = []
    total_trades      = 0
    total_wins        = 0
    total_losses      = 0
    total_gain_sum    = 0.0
    total_loss_sum    = 0.0
    skipped           = []

    print("\n" + "═" * 65)
    print("  Saber Trader — Historical Backtest")
    print(f"  Universe  : {len(SAMPLE_UNIVERSE)} saham")
    print(f"  Periode   : Sejak {START_DATE} ({PERIOD_DAYS} hari / ~{PERIOD_DAYS//365} tahun)")
    print(f"  Max Hold  : {MAX_HOLDING} hari")
    print(f"  Dijalankan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 65)

    for i, ticker in enumerate(SAMPLE_UNIVERSE, 1):
        sys.stdout.write(f"\r  [{i:02d}/{len(SAMPLE_UNIVERSE)}] Scanning {ticker}...     ")
        sys.stdout.flush()

        try:
            ohlcv = dp.get_ohlcv(ticker, start_date=START_DATE, interval="1d")
            if ohlcv is None or len(ohlcv) < MIN_LOOKBACK + 20:
                skipped.append((ticker, f"data tidak cukup ({len(ohlcv) if ohlcv is not None else 0} baris)"))
                continue

            report = bt.run(ticker=ticker, ohlcv_df=ohlcv, min_lookback=MIN_LOOKBACK)

            if report.total_trades == 0:
                skipped.append((ticker, "0 trades dihasilkan"))
                continue

            all_results.append(bt.report_to_dict(report))

            # Aggregate stats
            total_trades  += report.total_trades
            total_wins    += report.win_trades
            total_losses  += report.loss_trades
            wins          = [t for t in report.trades if t.is_win]
            losses        = [t for t in report.trades if not t.is_win]
            total_gain_sum += sum(t.pnl_percent for t in wins)
            total_loss_sum += sum(abs(t.pnl_percent) for t in losses)

            # Print per-stock result
            wr_emoji = "🟢" if report.winrate >= 55 else ("🟡" if report.winrate >= 45 else "🔴")
            print(f"\r  {wr_emoji} {ticker:<6} | Trades: {report.total_trades:3d} | "
                  f"WR: {report.winrate:5.1f}% | "
                  f"Avg Gain: {fmt_pct(report.average_gain)} | "
                  f"Avg Loss: -{report.average_loss:.2f}% | "
                  f"PF: {report.profit_factor:.2f} | "
                  f"Hold: {report.avg_holding_days:.1f}d")

            time.sleep(0.3)   # hindari rate limit API

        except Exception as e:
            skipped.append((ticker, str(e)[:80]))

    # ── Aggregate Summary ───────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  AGGREGATE RESULTS")
    print("═" * 65)

    if total_trades == 0:
        print("  ❌  Tidak ada trade yang dihasilkan. Periksa koneksi data.")
        return

    aggregate_wr        = (total_wins / total_trades * 100) if total_trades > 0 else 0
    avg_gain_overall    = (total_gain_sum / total_wins)    if total_wins    > 0 else 0
    avg_loss_overall    = (total_loss_sum / total_losses)  if total_losses  > 0 else 0
    profit_factor_total = (total_gain_sum / total_loss_sum) if total_loss_sum > 0 else 0
    expectancy          = (
        (aggregate_wr / 100) * avg_gain_overall
        - ((1 - aggregate_wr / 100) * avg_loss_overall)
    )

    wr_label = "BAGUS ✅" if aggregate_wr >= 55 else ("CUKUP 🟡" if aggregate_wr >= 45 else "BURUK 🔴")

    print(f"  Total saham diuji    : {len(SAMPLE_UNIVERSE)} ({len(all_results)} berhasil, {len(skipped)} skip)")
    print(f"  Total trades         : {total_trades}")
    print(f"  Win / Loss           : {total_wins} / {total_losses}")
    print(f"  Win Rate Aggregate   : {aggregate_wr:.1f}%  [{wr_label}]")
    print(f"  Avg Gain per trade   : {fmt_pct(avg_gain_overall)}")
    print(f"  Avg Loss per trade   : -{avg_loss_overall:.2f}%")
    print(f"  Profit Factor        : {profit_factor_total:.2f}  (target > 1.5)")
    print(f"  Expectancy per trade : {expectancy:+.2f}%  (positif = sistem menguntungkan)")
    print("═" * 65)

    # ── Per-stock leaderboard ───────────────────────────────────────
    all_results.sort(key=lambda x: x["winrate"], reverse=True)
    print("\n  TOP PERFORMERS:")
    for r in all_results[:5]:
        print(f"    🏆 {r['ticker']:<6} WR={r['winrate']:.1f}%  PF={r['profit_factor']:.2f}  "
              f"Trades={r['total_trades']}  AvgGain={fmt_pct(r['average_gain'])}")

    print("\n  WORST PERFORMERS:")
    for r in all_results[-5:]:
        print(f"    ⚠️  {r['ticker']:<6} WR={r['winrate']:.1f}%  PF={r['profit_factor']:.2f}  "
              f"Trades={r['total_trades']}  AvgGain={fmt_pct(r['average_gain'])}")

    if skipped:
        print(f"\n  SKIPPED ({len(skipped)} saham):")
        for ticker, reason in skipped:
            print(f"    - {ticker}: {reason}")

    # ── Save to JSON ────────────────────────────────────────────────
    output = {
        "run_at": datetime.now().isoformat(),
        "config": {
            "universe": SAMPLE_UNIVERSE,
            "start_date": str(START_DATE),
            "period_days": PERIOD_DAYS,
            "max_holding_days": MAX_HOLDING,
            "min_lookback": MIN_LOOKBACK,
        },
        "aggregate": {
            "total_stocks_tested": len(all_results),
            "total_trades": total_trades,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "win_rate_pct": round(aggregate_wr, 2),
            "avg_gain_pct": round(avg_gain_overall, 2),
            "avg_loss_pct": round(avg_loss_overall, 2),
            "profit_factor": round(profit_factor_total, 2),
            "expectancy_pct": round(expectancy, 2),
        },
        "per_stock": all_results,
        "skipped": [{"ticker": t, "reason": r} for t, r in skipped],
    }

    with open("backtest_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  💾 Hasil lengkap disimpan ke: backtest_results.json")
    print("═" * 65 + "\n")


if __name__ == "__main__":
    run_backtest()
