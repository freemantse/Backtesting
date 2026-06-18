"""End-to-end run orchestration: data -> classify -> backtest -> report.

Used by the CLI `run` subcommand. Produces all artifacts in an output dir and a
comprehensive REPORT.md at the project root.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from . import metrics as M
from . import plotting, report
from .backtest import riskfree_daily, run_backtest
from .classifier import STAGE_NAMES, classify
from .config import REPO_ROOT, Config
from .data import load
from .strategy import (
    AllWeather,
    BuyHold,
    Context,
    EqualWeight,
    Rotation,
    StyleRotation,
    target_vol_overlay,
)
from .universe import Universe

DISPLAY = {
    "s1_style": "S1 Style Rotation",
    "s2_allweather": "S2 All-Weather",
    "s3_rotation": "S3 Rotation",
    "s4_targetvol": "S4 Target-Vol",
    "ew": "Equal-Weight (EW) Benchmark",
}


def run_all(cfg: Config, price_source: str, macro_source: str,
            strategies: list[str], on_missing_history: str,
            out_dir: Path, report_path: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    universe = Universe.from_config(cfg)

    # ---- data ------------------------------------------------------------
    data = load(cfg, universe, price_source, macro_source, on_missing_history)
    # data provenance note (for the report's honesty banner)
    prov_file = REPO_ROOT / "data" / "offline" / "PROVENANCE.txt"
    if "csv" in (price_source, macro_source) and prov_file.exists():
        data_provenance = prov_file.read_text().strip()
    else:
        data_provenance = f"live fetch — prices: {price_source}, macro: {macro_source}"
    prices = data.prices
    returns = prices.pct_change()
    eff_start = data.effective_start
    end = cfg.dates["end"]
    target_index = returns.loc[eff_start:end].index

    # ---- classifier ------------------------------------------------------
    cls = classify(data.macro, cfg.signals, target_index)
    rf_daily = riskfree_daily(data.macro, cfg.signals["riskfree_series"], target_index)

    ctx = Context(
        returns=returns,
        stages=cls.stages,
        universe=universe,
        stage_baskets=cfg.stage_baskets,
        style_weights=cfg.style_weights,
        rp_lookback=cfg.backtest["rp_lookback"],
        vol_floor=cfg.backtest["vol_floor_daily"],
    )

    bt = cfg.backtest
    common = dict(
        ctx=ctx, start=eff_start, end=end, rebalance=bt["rebalance"],
        exec_lag_days=bt["exec_lag_days"], costs=cfg.costs, rf_daily=rf_daily,
    )

    # ---- run strategies --------------------------------------------------
    results: dict = {}
    benchmark_ticker = universe.leg_to_ticker.get("benchmark", "SPY")

    # benchmarks always run (for win-rate + comparison)
    results["ew"] = run_backtest(EqualWeight(), **common)
    spy_res = run_backtest(BuyHold(benchmark_ticker), **common)
    results[benchmark_ticker.lower()] = spy_res

    if "s1" in strategies:
        results["s1_style"] = run_backtest(StyleRotation(), **common)
    if "s2" in strategies:
        results["s2_allweather"] = run_backtest(AllWeather(), **common)

    s3_res = None
    if "s3" in strategies or "s4" in strategies:
        s3_res = run_backtest(Rotation(), **common)
        if "s3" in strategies:
            results["s3_rotation"] = s3_res
    if "s4" in strategies and s3_res is not None:
        tv = target_vol_overlay(Rotation(), s3_res.returns, cfg.target_vol, bt["annualization"])
        results["s4_targetvol"] = run_backtest(tv, **common)

    # order results sensibly
    order = ["s1_style", "s2_allweather", "s3_rotation", "s4_targetvol", "ew", benchmark_ticker.lower()]
    results = {k: results[k] for k in order if k in results}

    # ---- metrics ---------------------------------------------------------
    benchmarks = {"EW": results["ew"].returns, "SPY": spy_res.returns}
    mtable = M.metrics_table(results, rf_daily, benchmarks, bt["annualization"])

    # ---- plots -----------------------------------------------------------
    images = {
        "equity": plotting.plot_equity(results, out_dir / "equity_curves.png"),
        "drawdown": plotting.plot_drawdown(results, out_dir / "drawdown.png"),
        "regime": plotting.plot_regime(cls.stages, out_dir / "regime_timeline.png"),
        "signals": plotting.plot_signals(cls.transformed, cls.signals_monthly, out_dir / "signals.png"),
    }
    if "s3_rotation" in results:
        images["weights"] = plotting.plot_weights(results["s3_rotation"], out_dir / "weights_s3_rotation.png")

    # ---- artifacts -------------------------------------------------------
    mtable.to_csv(out_dir / "metrics.csv")
    (out_dir / "metrics.md").write_text(report._md_table(report._fmt_metrics(mtable), "Strategy"))
    regime_df = pd.DataFrame({"stage": cls.stages})
    regime_df["stage_name"] = regime_df["stage"].map(lambda s: STAGE_NAMES.get(int(s)) if pd.notna(s) else None)
    regime_df.to_csv(out_dir / "regime_timeline.csv")
    cls.signals_monthly.to_csv(out_dir / "signals_monthly.csv")
    cls.transformed.to_csv(out_dir / "signals_transformed.csv")
    for name, res in results.items():
        res.weights.to_csv(out_dir / f"weights_{name}.csv")
    pd.DataFrame({n: r.turnover for n, r in results.items()}).to_csv(out_dir / "turnover.csv")
    # stage -> basket snapshot
    sb = pd.DataFrame(
        [{"stage": st, "legs": ",".join(legs),
          "etfs": ",".join(universe.leg_to_ticker.get(l, "?") for l in legs)}
         for st, legs in cfg.stage_baskets.items()]
    )
    sb.to_csv(out_dir / "stage_weights.csv", index=False)
    pd.DataFrame(data.splice_manifest).to_csv(out_dir / "splice_manifest.csv", index=False)

    # regime mix string
    mix = cls.stages.dropna().astype(int).value_counts(normalize=True).sort_index()
    regime_mix = ", ".join(f"S{int(k)} {v*100:.0f}%" for k, v in mix.items())

    s3_sharpe = mtable.loc["s3_rotation", "Sharpe"] if "s3_rotation" in mtable.index else None

    report_info = {
        "generated": dt.date.today().isoformat(),
        "effective_start": eff_start,
        "end": end,
        "rebalance": bt["rebalance"],
        "price_source": price_source,
        "macro_source": macro_source,
        "growth_signal": cfg.signals.get("growth_signal", "indpro"),
        "macro_lag_days": cfg.signals.get("macro_lag_days", 21),
        "universe": universe.leg_to_ticker,
        "stage_baskets": {int(k): v for k, v in cfg.stage_baskets.items()},
        "rp_lookback": bt["rp_lookback"],
        "target_vol": cfg.target_vol["target"],
        "max_leverage": cfg.target_vol["max_leverage"],
        "commission_bps": cfg.costs["commission_bps"],
        "slippage_bps": cfg.costs["slippage_bps"],
        "splice_note": ("real-instrument data, no synthetic splice"
                        if on_missing_history == "clamp"
                        else "extended pre-inception via documented proxy splice"),
        "label_map": {**DISPLAY, benchmark_ticker.lower(): f"{benchmark_ticker} (Buy & Hold)"},
        "regime_mix": regime_mix,
        "s3_sharpe": f"{s3_sharpe:.2f}" if s3_sharpe is not None and pd.notna(s3_sharpe) else "—",
        "run_config_file": "run_config.json",
        "data_provenance": data_provenance,
    }

    # run_config.json (resolved params + report_info for rebuilds)
    (out_dir / "run_config.json").write_text(json.dumps(
        {"config": cfg.raw, "report_info": report_info,
         "price_source": price_source, "macro_source": macro_source,
         "strategies": strategies, "on_missing_history": on_missing_history},
        indent=2, default=str))

    # ---- report (root + out_dir copy) -----------------------------------
    out_rel = out_dir.relative_to(REPO_ROOT) if out_dir.is_absolute() else out_dir
    images_root = {k: str(out_rel / Path(v).name) for k, v in images.items()}
    report.build_report(report_info, mtable, images_root, data.splice_manifest, report_path)
    images_local = {k: Path(v).name for k, v in images.items()}
    report.build_report(report_info, mtable, images_local, data.splice_manifest, out_dir / "REPORT.md")

    return {"metrics": mtable, "out_dir": out_dir, "report": report_path,
            "regime_mix": regime_mix, "effective_start": eff_start}
