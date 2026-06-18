"""Command-line interface: `sixcycle {fetch-data,run,report}`.

Examples
--------
    sixcycle fetch-data --start 2016-06-01 --end 2025-12-31 --save-offline
    sixcycle run --strategies s1,s2,s3,s4 --out-dir outputs/run1
    sixcycle run --source csv --macro-source csv          # offline, no keys
    sixcycle report --run-dir outputs/run1 --out REPORT.md
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from . import report as report_mod
from .config import REPO_ROOT, load_config
from .data import load, make_macro_source, make_price_source
from .universe import Universe

OFFLINE_DIR = REPO_ROOT / "data" / "offline"


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default=None, help="path to a YAML config (default configs/default.yaml)")
    p.add_argument("--start", default=None, help="backtest start date YYYY-MM-DD")
    p.add_argument("--end", default=None, help="backtest end date YYYY-MM-DD")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sixcycle", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    # fetch-data ----------------------------------------------------------
    f = sub.add_parser("fetch-data", help="download + cache prices and macro")
    _add_common(f)
    f.add_argument("--source", default="tiingo", choices=["tiingo", "stooq", "csv"])
    f.add_argument("--macro-source", default="fred", choices=["fred", "csv"])
    f.add_argument("--on-missing-history", default="clamp", choices=["clamp", "proxy"])
    f.add_argument("--save-offline", action="store_true",
                   help="write data/offline/{prices,macro}.csv for the no-key path")

    # run -----------------------------------------------------------------
    r = sub.add_parser("run", help="run the backtest and write artifacts + REPORT.md")
    _add_common(r)
    r.add_argument("--strategies", default="s1,s2,s3,s4",
                   help="comma list of s1,s2,s3,s4 (benchmarks ew+spy always run)")
    r.add_argument("--source", default="tiingo", choices=["tiingo", "stooq", "csv"])
    r.add_argument("--macro-source", default="fred", choices=["fred", "csv"])
    r.add_argument("--rebalance", default=None, choices=["M", "W"])
    r.add_argument("--growth-signal", default=None, choices=["indpro", "cfnai"])
    r.add_argument("--money-signal", default=None, choices=["DGS3MO", "FEDFUNDS", "DGS2"])
    r.add_argument("--growth-etf", default=None)
    r.add_argument("--value-etf", default=None)
    r.add_argument("--commodity-etf", default=None)
    r.add_argument("--commission-bps", type=float, default=None)
    r.add_argument("--slippage-bps", type=float, default=None)
    r.add_argument("--rp-lookback", type=int, default=None)
    r.add_argument("--tv-lookback", type=int, default=None)
    r.add_argument("--target-vol", type=float, default=None)
    r.add_argument("--max-leverage", type=float, default=None)
    r.add_argument("--macro-lag-days", type=int, default=None)
    mono = r.add_mutually_exclusive_group()
    mono.add_argument("--clock-monotonic", dest="clock_monotonic", action="store_true", default=None)
    mono.add_argument("--no-clock-monotonic", dest="clock_monotonic", action="store_false")
    r.add_argument("--on-missing-history", default="clamp", choices=["clamp", "proxy"])
    r.add_argument("--out-dir", default=None)
    r.add_argument("--report", default=None, help="path for the root REPORT.md (default ./REPORT.md)")

    # report --------------------------------------------------------------
    rep = sub.add_parser("report", help="rebuild REPORT.md from a run directory")
    rep.add_argument("--run-dir", required=True)
    rep.add_argument("--out", default="REPORT.md")

    return p


def _apply_overrides(cfg, args):
    return cfg.override(**{
        "dates.start": args.start,
        "dates.end": args.end,
        "backtest.rebalance": getattr(args, "rebalance", None),
        "signals.growth_signal": getattr(args, "growth_signal", None),
        "signals.money_series": getattr(args, "money_signal", None),
        "signals.macro_lag_days": getattr(args, "macro_lag_days", None),
        "signals.clock_monotonic": getattr(args, "clock_monotonic", None),
        "universe.growth": getattr(args, "growth_etf", None),
        "universe.value": getattr(args, "value_etf", None),
        "universe.commodity": getattr(args, "commodity_etf", None),
        "costs.commission_bps": getattr(args, "commission_bps", None),
        "costs.slippage_bps": getattr(args, "slippage_bps", None),
        "backtest.rp_lookback": getattr(args, "rp_lookback", None),
        "target_vol.lookback": getattr(args, "tv_lookback", None),
        "target_vol.target": getattr(args, "target_vol", None),
        "target_vol.max_leverage": getattr(args, "max_leverage", None),
    })


def cmd_fetch_data(args) -> None:
    cfg = _apply_overrides(load_config(args.config), args)
    universe = Universe.from_config(cfg)
    data = load(cfg, universe, args.source, args.macro_source, args.on_missing_history)
    print(f"[fetch-data] prices: {data.prices.shape[0]} rows x {data.prices.shape[1]} tickers "
          f"({data.prices.index.min().date()} → {data.prices.index.max().date()})")
    print(f"[fetch-data] macro series: {sorted(data.macro)}")
    if args.save_offline:
        OFFLINE_DIR.mkdir(parents=True, exist_ok=True)
        data.prices.to_csv(OFFLINE_DIR / "prices.csv")
        macro_df = __import__("pandas").DataFrame(data.macro)
        macro_df.to_csv(OFFLINE_DIR / "macro.csv")
        print(f"[fetch-data] wrote offline data to {OFFLINE_DIR}")


def cmd_run(args) -> None:
    from .runner import run_all  # lazy (pulls matplotlib)

    cfg = _apply_overrides(load_config(args.config), args)
    strategies = [s.strip().lower() for s in args.strategies.split(",") if s.strip()]
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else (REPO_ROOT / "outputs" / f"run_{ts}")
    report_path = Path(args.report) if args.report else (REPO_ROOT / "REPORT.md")

    res = run_all(cfg, args.source, args.macro_source, strategies,
                  args.on_missing_history, out_dir, report_path)

    print("\n=== Metrics ===")
    print(report_mod._fmt_metrics(res["metrics"]).to_string())
    print(f"\nRegime mix: {res['regime_mix']}")
    print(f"Effective start: {res['effective_start']}")
    print(f"Artifacts: {out_dir}")
    print(f"Report:    {report_path}")


def cmd_report(args) -> None:
    out = report_mod.rebuild_from_run_dir(Path(args.run_dir), Path(args.out))
    print(f"[report] wrote {out}")


def main(argv: list[str] | None = None) -> int:
    from .dotenv import load_dotenv

    load_dotenv()  # pick up TIINGO_API_KEY / FRED_API_KEY from .env.local
    args = _build_parser().parse_args(argv)
    try:
        if args.cmd == "fetch-data":
            cmd_fetch_data(args)
        elif args.cmd == "run":
            cmd_run(args)
        elif args.cmd == "report":
            cmd_report(args)
    except (RuntimeError, FileNotFoundError, KeyError) as exc:
        print(f"\n[error] {exc}", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
