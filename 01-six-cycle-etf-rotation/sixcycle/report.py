"""Assemble the comprehensive REPORT.md from run facts + computed results.

The report combines static narrative (paper strategies, AxiomQ failure analysis,
our setup and asset choices) with the run's computed metrics, embedded graphs
and diagrams. Callable in-memory from `run`, or rebuilt from a run directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from .classifier import STAGE_NAMES

# Reference numbers from the source paper (in-sample) and AxiomQ (proxy reproduction).
PAPER_TABLE = pd.DataFrame(
    {
        "Period": ["since 2013", "since 2014", "since 2014", "since 2014"],
        "AnnReturn": ["27.3%", "11.5%", "23.0%", "9.4%"],
        "AnnVol": ["23.3%", "6.9%", "11.3%", "3.2%"],
        "MaxDD": ["38.1%", "11.2%", "12.0%", "3.4%"],
        "Sharpe": [1.17, 1.66, 2.04, 2.88],
    },
    index=["S1 Style Rotation", "S2 All-Weather", "S3 Rotation (main)", "S4 Target-Vol"],
)

AXIOMQ_TABLE = pd.DataFrame(
    {
        "AnnReturn": ["6.09%", "6.08%", "5.77%", "1.64%"],
        "Sharpe": [0.42, 0.51, 0.48, 0.52],
        "MaxDD": ["-42.74%", "-28.26%", "-29.53%", "-10.97%"],
    },
    index=["EW Benchmark", "S1 All-Weather", "S2 Rotation (net)", "S3 Target-Vol"],
)


# Human-facing display labels for the raw machine codes stored in run_config.
SOURCE_LABELS = {"tiingo": "Tiingo", "fred": "FRED", "stooq": "Stooq", "csv": "CSV (offline cache)"}
GROWTH_LABELS = {
    "indpro": "INDPRO (Industrial Production)",
    "cfnai": "CFNAI (Chicago Fed National Activity Index)",
}
REBAL_LABELS = {"M": "Monthly", "W": "Weekly"}


def _src(code: str) -> str:
    return SOURCE_LABELS.get(code, str(code).upper())


def _growth(code: str) -> str:
    return GROWTH_LABELS.get(code, str(code).upper())


def _rebal(code: str) -> str:
    return REBAL_LABELS.get(code, str(code))


def _provenance(info: dict) -> str:
    """Human-facing provenance line. Rebuild the live-fetch case with display
    names; echo the offline/PROVENANCE.txt string (already nicely cased)."""
    prov = info.get("data_provenance", "")
    if prov.startswith("live fetch"):
        return (f"live fetch — prices: {_src(info['price_source'])}, "
                f"macro: {_src(info['macro_source'])}")
    return prov


def _fmt_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    pct_cols = ["CAGR", "AnnVol", "MaxDD"]
    for c in out.columns:
        if c in pct_cols or c.startswith("WinRate"):
            out[c] = out[c].map(lambda v: f"{v*100:.1f}%" if pd.notna(v) else "—")
        elif c in ("Sharpe", "Calmar", "AnnTurnover"):
            out[c] = out[c].map(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
    return out


def _md_table(df: pd.DataFrame, index_name: str = "") -> str:
    """Render a DataFrame as a GitHub-flavoured markdown table (no tabulate dep)."""
    headers = [index_name] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]
    for idx, row in df.iterrows():
        cells = [str(idx)] + [str(v) for v in row.values]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def build_report(info: dict, metrics: pd.DataFrame, images: dict[str, str],
                 splice_manifest: list[dict], out_path: Path) -> Path:
    """Render REPORT.md. ``images`` maps logical name -> relative path."""
    fmt = _fmt_metrics(metrics)
    label_map = info.get("label_map", {})
    fmt.index = [label_map.get(i, i) for i in fmt.index]

    uni = info["universe"]
    md = []
    A = md.append

    # ---------------------------------------------------------------- title
    A("# Six-Cycle Multi-Asset ETF Rotation — US-Market Analog: Backtest Report\n")
    A(f"*Generated {info['generated']} · backtest window "
      f"{info['effective_start']} → {info['end']} · rebalance {_rebal(info['rebalance'])} · "
      f"prices: {_src(info['price_source'])} · macro: {_src(info['macro_source'])} · "
      f"growth signal: {_growth(info['growth_signal'])}*\n")
    A("> **What this is.** A faithful-in-*structure* reproduction of the Guosheng Securities "
      "“Six-Cycle Framework” multi-asset ETF rotation paper, rebuilt on **US ETFs** with a "
      "**point-in-time** macro classifier from free FRED data. It is a transferability test — *does "
      "the idea travel to US markets?* — not an attempt to reproduce the literal China numbers.\n")

    A(f"\n> **Data provenance:** {_provenance(info)}.\n")

    # ----------------------------------------------------------- exec summary
    A("\n## Executive summary\n")

    A("### In plain terms\n")
    A("The economy moves through a repeating cycle of phases — money loosens, then credit "
      "expands, then growth picks up, and later the reverse. The source paper's idea is "
      "simple: **work out which of six phases the economy is in right now, then hold the "
      "assets that have historically done best in that phase**, and re-check every month. "
      "This report re-tests that idea on real **US ETFs** (stocks by style, gold, "
      "commodities, long-term Treasuries), using a **leak-free** classifier that only ever "
      "looks at macro data that was actually known at the time.\n")

    A("\n**The four strategies tested** (all on the same six-phase engine):\n"
      "- **S1 Style Rotation** — rotate the *equity style* (Growth / Quality / Value) by phase.\n"
      "- **S2 All-Weather** — hold *every* phase's basket at once, no timing (a control).\n"
      "- **S3 Six-Cycle Rotation** — the *main* strategy: hold only the current phase's basket.\n"
      "- **S4 Rotation + Target-Vol** — S3 dialled to a low, steady volatility target.\n")

    A("\n### The result in context\n")
    A("The paper reports an in-sample Sharpe near **2.0** for its main rotation strategy. A prior "
      "reproduction (AxiomQ) collapsed that to **0.48** — but through three *mechanical* failures "
      "(wrong substitute assets, a missing gold leg, and a hand-typed hindsight regime timeline), "
      "not a refutation of the method. This build fixes all three and asks where the honest, "
      "out-of-sample-style number lands — expected **below** the paper's flattered ~2.0 but "
      "**above** AxiomQ's 0.48.\n")
    A("\n**Headline results (this run):**\n")
    A(_md_table(fmt, "Strategy") + "\n")

    A("\n### What's in this report\n")
    A("- **[Part I](#part-i--the-source-paper-six-cycle-framework)** — the source paper: the six-phase idea, its macro signals, and the four strategies.\n"
      "- **[Part II](#part-ii--the-prior-reproduction-axiomq-and-why-it-underperformed)** — the prior attempt (AxiomQ) and the three mistakes that sank it.\n"
      "- **[Part III](#part-iii--this-backtest-setup-purpose--choices)** — how this backtest is built: data, assets, *how a phase is decided from the macro data*, and mechanics.\n"
      "- **[Part IV](#part-iv--results)** — results: equity curves, drawdowns, regime timeline, and metrics.\n"
      "- **[Part V](#part-v--interpretation)** — interpretation: why the number lands where it does, plus honest caveats.\n"
      "- **[Part VI](#part-vi--reproducibility)** — how to reproduce the run.\n")

    # ------------------------------------------------------------- Part I
    A("\n---\n\n## Part I — The source paper (Six-Cycle Framework)\n")
    A("**Paper:** *Multi-Asset ETF Allocation under the Six-Cycle Framework* (六周期框架下的多资产ETF配置), "
      "Guosheng Securities Financial Engineering (Wang Yisheng, Liu Fubing), 2025-11-05.\n")
    A("\n**Core idea.** Locate where the economy sits on a six-stage macro cycle, then rotate a basket "
      "of style and multi-asset ETFs into whatever historically performs best in that stage. Within "
      "each stage, weight by risk parity; optionally scale leverage to a low volatility target.\n")

    A("\n### The macro classifier — three dimensions\n")
    A("| Dimension | Paper indicator | Signal logic |\n|---|---|---|\n"
      "| Money (货币) | DR007 short interbank rate | Falling rate = loose |\n"
      "| Credit (信用) | New medium/long-term loans, TTM YoY (“loan pulse”) | 3-month change; rising = expansion |\n"
      "| Growth (增长) | PMI (official + Caixin) | PMI momentum, up vs down |\n")

    A("\n### The six-stage clock\n")
    A("The stages cycle in a fixed order driven by the classic **monetary → credit → growth** "
      "lead-lag chain: money loosens first, then credit expands, then growth recovers; later money "
      "tightens, credit contracts, growth slows — and the clock loops.\n")
    A("\n```mermaid\nflowchart LR\n"
      "  S6[\"6 · Monetary Expansion\"] --> S1[\"1 · Credit Expansion\"]\n"
      "  S1 --> S2[\"2 · Economic Recovery\"]\n"
      "  S2 --> S3[\"3 · Monetary Retreat\"]\n"
      "  S3 --> S4[\"4 · Credit Retreat\"]\n"
      "  S4 --> S5[\"5 · Economic Slowdown\"]\n"
      "  S5 --> S6\n```\n")
    A("- **Style adaptation:** stages 1–2 favour **Growth**; 3–4 favour **Quality**; 5–6 favour **Value**.\n"
      "- **Asset classes:** offensive (stocks, commodities) lead stages 1–3; defensive (bonds) lead 4–6; "
      "transitional (gold) leads the growth-down stages 5, 6, 1.\n")

    A("\n### Stage → asset mapping (paper Figure 5)\n")
    A("| Stage | Paper holdings |\n|---|---|\n"
      "| 1 Credit Expansion | ChiNext (growth) + Gold |\n"
      "| 2 Economic Recovery | ChiNext + Non-ferrous futures (commodity) |\n"
      "| 3 Monetary Retreat | Cash-flow (quality) + Non-ferrous futures |\n"
      "| 4 Credit Retreat | Cash-flow + 30Y Treasury + Non-ferrous futures |\n"
      "| 5 Economic Slowdown | Dividend (value) + 30Y Treasury + Gold |\n"
      "| 6 Monetary Expansion | Dividend + 30Y Treasury + Gold |\n")

    A("\n### The four strategies & reported in-sample results\n")
    A(_md_table(PAPER_TABLE, "Strategy") + "\n")
    A("\n- **S1 Style Rotation** — switch the Growth/Quality/Value blend by stage.\n"
      "- **S2 All-Weather** — hold all six stage-baskets at once, risk-parity, *no timing*.\n"
      "- **S3 Six-Cycle Rotation** — the main strategy: hold only the current stage's basket.\n"
      "- **S4 Rotation + Target-Vol** — S3 scaled to ~3% annualised vol; highest Sharpe.\n")
    A("\n> **Caveat (theirs).** All paper figures are **in-sample**: the cycle definitions, mappings and "
      "weights were fit on the same history that was then tested. 2015 (+56.5%) flatters the rotation "
      "average heavily.\n")

    # ------------------------------------------------------------- Part II
    A("\n---\n\n## Part II — The prior reproduction (AxiomQ) and why it underperformed\n")
    A("AxiomQ attempted the China strategy but **lacked the required data**, so it ran a *proxy* "
      "reproduction over ~2,876 trading days (~11.4 yrs, 2014–2025): weekly rebalance, daily returns, "
      "annualisation 252, costs = 1bp commission + 2bp slippage.\n")
    A("\n**AxiomQ results:**\n")
    A(_md_table(AXIOMQ_TABLE, "Strategy") + "\n")
    A("\n### The three downgrades that crushed the Sharpe (≈2.0 → 0.48)\n")
    A("1. **Wrong ingredients (universe bias).** None of the 7 target ETFs were available. Substitutes "
      "were 4 broad indices + a dividend basket + a non-ferrous *stocks* basket. Worst of all, an "
      "**equity index (SSE50) stood in for the 30Y Treasury** — the wrong asset class entirely, which "
      "destroys the defensive ballast the rotation relies on in stages 4–6.\n"
      "2. **No gold.** No gold series existed locally, so the **gold leg was set to 0**. The defensive/"
      "transitional cushion (stages 1, 5, 6) simply vanished — likely the single biggest Sharpe killer.\n"
      "3. **Hand-typed regime timeline.** With no rate/loan/PMI inputs, the classifier was replaced by a "
      "**hard-coded 14-segment monthly timeline**. This is both illegitimate (hindsight, not "
      "reproducible) and crude (mis-timed transitions).\n")
    A("\n**Bottom line:** the gap was *mechanical*, not evidence against the framework. The state "
      "machine, risk parity and target-vol layers all ran fine; the result was dominated by missing "
      "assets and a fake classifier. **Those are exactly the three things this build fixes.**\n")

    # ------------------------------------------------------------- Part III
    A("\n---\n\n## Part III — This backtest: setup, purpose & choices\n")
    A("### Purpose\n")
    A("Test whether the Six-Cycle *idea* transfers to US markets, with an honest, point-in-time "
      "classifier and the real asset classes the paper intended (including gold and a true long bond). "
      "We expect a Sharpe **below** the paper's in-sample ~2.0 but **above** AxiomQ's 0.48 — that "
      "middle ground is the real result.\n")

    A("\n### The three fixes vs AxiomQ\n")
    A("| AxiomQ failure | This build |\n|---|---|\n"
      "| Wrong substitute assets / equity-as-bond | Real US ETFs for every leg, incl. a true long bond (**TLT**) |\n"
      "| Gold leg zeroed | **GLD** held in stages 1, 5, 6 as intended |\n"
      "| Hand-typed hindsight timeline | **Live, point-in-time** classifier from FRED with publication lags |\n")

    A("\n### Data stack\n")
    A(f"- **ETF prices → {_src(info['price_source'])}** (adjusted close; survivorship-aware free EOD). "
      "Stooq available as a free cross-check.\n"
      f"- **Macro → {_src(info['macro_source'])}**. Point-in-time via ALFRED vintages when a key is "
      "present; otherwise the latest-revision series with a fixed publication lag of "
      f"**{info['macro_lag_days']} days** applied so the classifier never peeks.\n"
      f"- **Growth signal → {_growth(info['growth_signal'])}** (PMI is proprietary and not freely bulk-"
      "downloadable; we use a free FRED proxy — this materially affects the growth leg and is a "
      "documented choice).\n")

    A("\n### Asset / equity choices (US analog)\n")
    A("| Leg | Paper instrument | US ETF used | Role |\n|---|---|---|---|\n"
      f"| Growth | ChiNext | **{uni.get('growth','?')}** | Offensive equity, stages 1–2 |\n"
      f"| Quality | Free-cash-flow | **{uni.get('quality','?')}** | Mid-cycle quality, stages 3–4 |\n"
      f"| Value | Dividend low-vol | **{uni.get('value','?')}** | Defensive equity, stages 5–6 |\n"
      f"| Gold | Gold ETF | **{uni.get('gold','?')}** | Transitional cushion, stages 1/5/6 |\n"
      f"| Commodity | Non-ferrous futures | **{uni.get('commodity','?')}** | Cyclical, stages 2–4 |\n"
      f"| 30Y Bond | 30Y Treasury | **{uni.get('bond','?')}** | Defensive ballast, stages 4–6 |\n"
      f"| Benchmark | CSI 800 | **{uni.get('benchmark','?')}** | Broad-market reference |\n")

    A("\n### How a phase is decided from the macro data\n")
    A("Every month-end, the raw macro series are turned into a single phase label through a "
      "fixed six-step pipeline. Nothing is hand-set — the label falls out of the data:\n")
    A("\n1. **Collect the raw monthly series from FRED** (resampled to month-end): the 3-month "
      "T-bill rate `DGS3MO`, commercial & industrial loans `BUSLOANS`, the high-yield credit "
      "spread `BAMLH0A0HYM2` (a tie-breaker), and industrial production `INDPRO` (or `CFNAI`).\n"
      "2. **Turn each into a momentum metric** — we care about *direction of change*, not level:\n"
      "   - **Money** = −(3-month change in the T-bill rate). A *falling* rate means policy is loosening.\n"
      "   - **Credit** = the “loan pulse” = the 3-month change in `BUSLOANS` year-over-year growth. "
      "*Accelerating* lending means credit is expanding.\n"
      "   - **Growth** = the 3-month change in `INDPRO` YoY growth (i.e. acceleration), or a 3-month "
      "average of `CFNAI`. *Speeding up* means growth is improving.\n"
      "3. **Reduce each metric to a +1 / −1 vote** with a **deadband + hysteresis**: clearly above "
      "zero → **+1**, clearly below → **−1**, but inside a small dead zone the metric is treated as "
      "noise and the *previous* vote is held (this stops the label flickering on tiny wiggles). For "
      "Credit, a too-small loan pulse is broken by the high-yield spread — a *falling* spread votes "
      "expansion (+1).\n"
      "4. **Map the three votes → one of six phases.** The triple `(Money, Credit, Growth)` has eight "
      "possible sign combinations; the 8→6 table below assigns each to a phase, following the classic "
      "**money → credit → growth lead-lag chain** (policy turns first, lending follows, real growth "
      "last). Six combinations are the canonical clock; the remaining two (where credit lags) fold into "
      "the nearest phase. *The paper omits this table, so it is our documented assumption.*\n"
      "5. **(Optional) clock smoothing:** when enabled, the phase may only advance to the same or the "
      "next clockwise phase, never jump — a further whipsaw guard.\n"
      f"6. **Make it leak-free (point-in-time):** each month-end label is only made available "
      f"**{info['macro_lag_days']} days later** (the publication lag) and then carried forward onto "
      "trading days — so the phase used on any given day relies only on data that was actually "
      "published by then.\n")
    A(f"\n*Worked example.* Suppose in a given month the T-bill rate is falling (**Money = +1**), "
      "loan growth is accelerating (**Credit = +1**), but industrial production is still contracting "
      "(**Growth = −1**). The triple `(+1, +1, −1)` maps to **Phase 1 — Credit Expansion**, so that "
      "month holds the Phase-1 basket. The live path of these votes and the resulting phases over the "
      "whole test window is plotted in [Part IV](#part-iv--results) (*Macro signal inputs* and "
      "*Regime timeline*).\n")

    A("\n### The classifier — signals & the 8→6 mapping (DOCUMENTED ASSUMPTION)\n")
    A("In precise terms, each dimension is reduced to +1/−1 with a small deadband + hysteresis to suppress whipsaw:\n"
      "- **Money** = sign of the *fall* in the 3-month T-bill (`DGS3MO`) over 3 months (falling = loose).\n"
      "- **Credit** = sign of the 3-month change in `BUSLOANS` YoY growth (loan pulse); ties broken by "
      "the direction of the HY OAS (`BAMLH0A0HYM2`, falling spread = expansion).\n"
      "- **Growth** = sign of the 3-month change in `INDPRO` YoY (acceleration), or the sign of a "
      "3-month CFNAI average.\n")
    A("\nThe paper does **not** publish the table that maps the eight (money, credit, growth) sign "
      "combinations to the six stages. We construct one from the monetary→credit→growth lead-lag chain "
      "and **flag it as our assumption, not paper-sourced**:\n")
    A("\n| Money | Credit | Growth | → Stage |\n|:---:|:---:|:---:|---|\n"
      "| + | − | − | 6 Monetary Expansion |\n"
      "| + | + | − | 1 Credit Expansion |\n"
      "| + | + | + | 2 Economic Recovery |\n"
      "| − | + | + | 3 Monetary Retreat |\n"
      "| − | − | + | 4 Credit Retreat |\n"
      "| − | − | − | 5 Economic Slowdown |\n"
      "| + | − | + | 2 Economic Recovery *(credit = laggard)* |\n"
      "| − | + | − | 5 Economic Slowdown *(credit = laggard)* |\n")

    A("\n### Stage → basket (US ETFs used here)\n")
    baskets = info["stage_baskets"]
    A("| Stage | Basket (legs → ETFs) |\n|---|---|\n")
    for st in range(1, 7):
        # baskets may be keyed by int (in-process) or by str (JSON round-trip
        # via run_config.json on the `report --run-dir` path) — accept both.
        legs = baskets.get(st) or baskets.get(str(st), [])
        etfs = ", ".join(f"{l}={uni.get(l,'?')}" for l in legs)
        A(f"| {st} {STAGE_NAMES[st]} | {etfs} |\n")

    A("\n### Backtest mechanics\n")
    A(f"- **Rebalance:** {_rebal(info['rebalance'])} (last trading day of each period), effective the **next** "
      "trading day (1-day execution lag → leakage-free).\n"
      f"- **Within-stage weighting:** inverse-volatility risk parity over a {info['rp_lookback']}-day "
      "lookback; legs with too little history are excluded and the rest renormalised (never zero-filled).\n"
      f"- **Target-vol (S4):** leverage = clip({info['target_vol']:.0%} / trailing annualised vol, 0, "
      f"{info['max_leverage']:g}); residual cash earns the 3-month T-bill rate.\n"
      f"- **Costs:** {info['commission_bps']:.0f}bp commission + {info['slippage_bps']:.0f}bp slippage, "
      "no stamp duty. **Annualisation:** 252.\n"
      f"- **Start date:** {info['effective_start']} — {info['splice_note']}\n")

    if splice_manifest:
        A("\n**Splice / history manifest:**\n")
        A("| Action | Detail |\n|---|---|\n")
        for m in splice_manifest:
            A(f"| {m.get('action','')} | {m.get('detail','')} |\n")

    # ------------------------------------------------------------- Part IV
    A("\n---\n\n## Part IV — Results\n")
    A("### Equity curves\n")
    A(f"![Equity curves]({images['equity']})\n")
    A("\n### Drawdowns\n")
    A(f"![Drawdown]({images['drawdown']})\n")
    A("\n### Regime timeline (what the live classifier saw)\n")
    A(f"![Regime timeline]({images['regime']})\n")
    A("\n### Macro signal inputs\n")
    A(f"![Signals]({images['signals']})\n")
    if "weights" in images:
        A("\n### Rotation weights over time (S3)\n")
        A(f"![Weights]({images['weights']})\n")

    A("\n### Metrics (this run)\n")
    A(_md_table(fmt, "Strategy") + "\n")
    A(f"\n*Regime mix over the test window:* {info.get('regime_mix','n/a')}.\n")

    # ------------------------------------------------------------- Part V
    A("\n---\n\n## Part V — Interpretation\n")
    A("**The honest middle ground.** Set the three columns side by side:\n\n"
      "| | Paper S3 (in-sample) | **This build** | AxiomQ S2 (proxy) |\n|---|---|---|---|\n"
      f"| Main rotation Sharpe | ~2.04 | **{info.get('s3_sharpe','—')}** | 0.48 |\n")
    A("\nWhy below the paper: (1) the paper's figures are **in-sample** and flattered by 2015; (2) the "
      "US growth signal is a **proxy** (INDPRO/CFNAI), not the PMI the paper uses; (3) our 8→6 mapping "
      "is an assumption, not a re-fit; (4) a different central bank and universe.\n")
    A("\nWhy above AxiomQ: the **real assets are present** — gold cushions the growth-down stages and a "
      "true long bond (TLT) provides the defensive ballast — and the **classifier is point-in-time**, "
      "not a hindsight timeline.\n")
    A("\n### Honest caveats\n")
    A("- **In-sample vs out-of-sample.** We do not re-fit the mapping; still, the stage definitions come "
      "from the paper's framework, so this is a *structural transfer test*, not a clean OOS experiment.\n"
      "- **Growth-proxy sensitivity.** Swapping INDPRO↔CFNAI shifts the growth leg and therefore the "
      "stage path and results.\n"
      "- **Splice / start-date distortion.** Quality (COWZ) is a recent ETF; extending before its "
      "inception requires a proxy splice (logged above) or clamping the start date.\n"
      "- **Free-data fidelity.** Tiingo/Stooq adjusted EOD is good but not institutional survivorship-"
      "grade; `BUSLOANS` is an imperfect analog of China's medium/long-term loan pulse.\n")

    # ------------------------------------------------------------- Part VI
    A("\n---\n\n## Part VI — Reproducibility\n")
    A("```bash\n"
      "pip install -r requirements.txt\n"
      "export TIINGO_API_KEY=...   # free at tiingo.com\n"
      "export FRED_API_KEY=...     # free at fred.stlouisfed.org\n"
      f"sixcycle fetch-data --start {info['effective_start']} --end {info['end']}\n"
      "sixcycle run --strategies s1,s2,s3,s4,ew,spy --out-dir outputs/run1\n"
      "sixcycle report --run-dir outputs/run1 --out REPORT.md\n"
      "# no keys? runs offline on bundled CSV data:\n"
      "sixcycle run --source csv --macro-source csv --out-dir outputs/demo\n"
      "```\n")
    A(f"\nFull resolved parameters for this run are in `{info.get('run_config_file','run_config.json')}`.\n")

    A("\n---\n\n*Generated by the `sixcycle` backtester. All figures are model output on the data "
      "described above; see the caveats in Part V before drawing conclusions.*\n")

    out_path.write_text("".join(md))
    return out_path


def rebuild_from_run_dir(run_dir: Path, out_path: Path) -> Path:
    """Rebuild REPORT.md from a completed run directory's artifacts."""
    run_dir = Path(run_dir)
    info = json.loads((run_dir / "run_config.json").read_text())
    metrics = pd.read_csv(run_dir / "metrics.csv", index_col=0)
    manifest = []
    mpath = run_dir / "splice_manifest.csv"
    if mpath.exists() and mpath.stat().st_size > 0:
        try:
            manifest = pd.read_csv(mpath).to_dict("records")
        except pd.errors.EmptyDataError:
            manifest = []  # clamp mode writes an empty manifest
    # Emit image links relative to the report's own location so they resolve
    # both when REPORT.md sits beside the run dir and when it lives at the
    # strategy root (e.g. outputs/run1/equity_curves.png) — e.g. on GitHub.
    out_dir = Path(out_path).resolve().parent
    images = {}
    for key, fname in [("equity", "equity_curves.png"), ("drawdown", "drawdown.png"),
                       ("regime", "regime_timeline.png"), ("signals", "signals.png"),
                       ("weights", "weights_s3_rotation.png")]:
        if (run_dir / fname).exists():
            images[key] = os.path.relpath((run_dir / fname).resolve(), out_dir)
    return build_report(info["report_info"], metrics, images, manifest, out_path)
