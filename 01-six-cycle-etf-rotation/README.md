# Six-Cycle Multi-Asset ETF Rotation

**In plain terms:** the economy moves through repeating phases (easing money, expanding credit,
recovering growth, tightening, contracting, slowing). This strategy tries to hold the ETFs that
tend to do best in *whichever phase the economy is currently in*, and rotates as the phase changes.
We test four variants against simple benchmarks (an equal-weight basket and buy-and-hold S&P 500).

**📄 [Read the full report → REPORT.md](REPORT.md)** — context, methodology, results, and caveats.

### How a $1 investment would have grown

![Equity curves](outputs/run1/equity_curves.png)

### Headline results (latest run)

| Strategy | CAGR | AnnVol | Sharpe | MaxDD | Calmar |
|---|---|---|---|---|---|
| S1 Style Rotation | 14.3% | 18.6% | 0.69 | -31.4% | 0.46 |
| S2 All-Weather | 9.8% | 9.6% | 0.78 | -21.4% | 0.46 |
| S3 Six-Cycle Rotation | 7.2% | 13.0% | 0.43 | -31.8% | 0.23 |
| S4 Target-Vol | 3.7% | 3.9% | 0.36 | -9.6% | 0.39 |
| *Benchmark: Equal-Weight* | 11.0% | 11.0% | 0.80 | -21.7% | 0.51 |
| *Benchmark: SPY (S&P 500)* | 15.1% | 18.1% | 0.74 | -33.7% | 0.45 |

*CAGR = annual return · Sharpe = return per unit of risk (higher is better) · MaxDD = worst
peak-to-trough drop (smaller is better). Full table and interpretation in the [report](REPORT.md).*

### Want to run it yourself? (optional — no API keys needed)

1. Install [Python 3.9+](https://www.python.org/downloads/) (`python --version` to check).
2. Download this repo (green **Code → Download ZIP**, or `git clone`), then in a terminal:
   ```bash
   cd 01-six-cycle-etf-rotation
   pip install -r requirements.txt
   python -m sixcycle.cli run --source csv --macro-source csv --out-dir outputs/demo
   ```
3. Open `outputs/demo/REPORT.md` and the `.png` charts in that folder to see your results.

> On a Mac, use `python3` / `pip3` if `python` / `pip` aren't found. Full technical reference below.

---

## Technical reference

A command-line Python backtester that reproduces the four strategies of the
Guosheng Securities **“Six-Cycle Framework”** multi-asset ETF rotation paper as a
**US-market analog**, fixing the three failures of the prior AxiomQ attempt
(wrong assets, no gold, hand-typed regime timeline).

- **Prices:** Tiingo (free key) — adjusted EOD. Stooq cross-check + offline CSV.
- **Macro:** FRED (free key) — point-in-time via ALFRED vintages when available.
- **Growth signal:** free FRED proxy (INDPRO YoY acceleration, or CFNAI).
- **Strategies:** S1 Style Rotation · S2 All-Weather · S3 Six-Cycle Rotation · S4 Target-Vol · benchmarks (EW, SPY).

See [`PLAN.md`](PLAN.md) for the design and [`REPORT.md`](REPORT.md) for the full write-up + results.

---

## Install

```bash
pip install -r requirements.txt          # core + optional connectors
# or: pip install -e .                    # installs the `sixcycle` command
```

Python 3.9+. Core deps: pandas, numpy, matplotlib, scipy, PyYAML. The data
connectors (`tiingo`, `fredapi`, `pandas-datareader`) are optional — the offline
CSV path runs without them.

## API keys (for live data)

Put your free keys in **`.env.local`** (auto-loaded by every command; never committed):

```ini
# .env.local
TIINGO_API_KEY=your_tiingo_token
FRED_API_KEY=your_fred_key
```

(Or `export TIINGO_API_KEY=...` / `export FRED_API_KEY=...` — a real env var wins over the file.)
A `.env.example` template is provided. Behind a corporate proxy? `.env.local` also accepts
`SIXCYCLE_CA_BUNDLE=/path/to/ca.pem`, `HTTPS_PROXY=...`, or (last resort) `SIXCYCLE_INSECURE_SSL=1`.

No keys? Skip straight to the **offline** example below.

---

## Usage

The CLI has three subcommands. Run `python -m sixcycle.cli <cmd> -h` for full flags.

### 1. Fetch + cache data
```bash
python -m sixcycle.cli fetch-data --start 2016-06-01 --end 2025-12-31
# save a no-key offline snapshot (prices+macro) for later runs:
python -m sixcycle.cli fetch-data --source stooq --macro-source fred --save-offline
```

### 2. Run the backtest
```bash
python -m sixcycle.cli run --strategies s1,s2,s3,s4 --out-dir outputs/run1
```
Writes all artifacts to `outputs/run1/` and a comprehensive `REPORT.md` at the
project root.

### 3. (Re)build the report from a run
```bash
python -m sixcycle.cli report --run-dir outputs/run1 --out REPORT.md
```

### Offline (cache real data, then run keyless)
```bash
python scripts/make_offline_data.py          # fetch real data once → data/offline/
python -m sixcycle.cli run --source csv --macro-source csv --out-dir outputs/demo
```

If `sixcycle` is installed (`pip install -e .`) you can drop the `python -m sixcycle.cli`
prefix and just type `sixcycle ...`.

---

## Key flags (`run`)

| Flag | Default | Meaning |
|---|---|---|
| `--strategies` | `s1,s2,s3,s4` | which strategies (benchmarks always run) |
| `--source` | `tiingo` | price source: `tiingo` / `stooq` / `csv` |
| `--macro-source` | `fred` | macro source: `fred` / `csv` |
| `--rebalance` | `M` | `M` monthly (paper) or `W` weekly (AxiomQ) |
| `--growth-signal` | `indpro` | growth proxy: `indpro` / `cfnai` |
| `--growth-etf/--value-etf/--commodity-etf` | per config | override a leg's ETF |
| `--target-vol` / `--max-leverage` | `0.03` / `3.0` | S4 target-vol params |
| `--clock-monotonic` | off | restrict stage moves to adjacent clock stages |
| `--on-missing-history` | `clamp` | `clamp` start to latest inception, or `proxy`-splice |
| `--commission-bps` / `--slippage-bps` | `1` / `2` | trading costs |

## Outputs (per run dir)

`equity_curves.png`, `drawdown.png`, `regime_timeline.png(.csv)`, `signals.png`,
`weights_*.csv`, `stage_weights.csv`, `turnover.csv`, `metrics.csv`/`.md`,
`splice_manifest.csv`, `run_config.json`, and a local `REPORT.md`.

## Tests
```bash
pytest -q          # classifier mapping, risk parity, backtest costs, point-in-time no-leakage
```

## Project layout
```
sixcycle/            # package
  config.py universe.py calendar.py classifier.py riskparity.py backtest.py
  metrics.py plotting.py report.py runner.py cli.py
  datasources/       # tiingo / stooq / fred / csv + cache
  strategy/          # s1..s4 + benchmarks
configs/default.yaml # all parameters (single source of truth)
scripts/make_offline_data.py
tests/
```

> **Disclaimer.** Research/education only. This is a *structural transfer test* of
> the paper's idea to US markets, not investment advice. All results are model
> output on free data with documented assumptions — read Part V of the report.
