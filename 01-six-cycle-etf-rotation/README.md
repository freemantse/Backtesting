# Six-Cycle Multi-Asset ETF Rotation

**In plain terms:** the economy moves through repeating phases (easing money, expanding credit,
recovering growth, tightening, contracting, slowing). This strategy tries to hold the ETFs that
tend to do best in *whichever phase the economy is currently in*, and rotates as the phase changes.
We test four variants against simple benchmarks (an equal-weight basket and buy-and-hold S&P 500).

**📄 [Read the full US-market report → REPORT_US.md](REPORT_US.md)** — context, methodology, results, and caveats.
**📄 [China-market reproduction → REPORT_CHINA.md](REPORT_CHINA.md)** — the same framework run on its native market (real ChiNext / gold / SHFE non-ferrous / ChinaBond 30Y legs, NBS-PMI classifier). *Headline: six-cycle timing added little — the main rotation (Sharpe 0.54) slightly trailed an equal-weight of the same legs (0.69).*

### How a $1 investment would have grown

*US market:*
![US equity curves](outputs/run1/equity_curves.png)

*China market:*
![China equity curves](outputs/run_china/equity_curves.png)

### Headline results (latest runs)

**🇺🇸 US market** — 2016-06 → 2025-12, prices Tiingo, macro FRED ([REPORT_US.md](REPORT_US.md)):

| Strategy | CAGR | AnnVol | Sharpe | MaxDD | Calmar |
|---|---|---|---|---|---|
| S1 Style Rotation | 14.3% | 18.6% | 0.69 | -31.4% | 0.46 |
| S2 All-Weather | 9.8% | 9.6% | 0.78 | -21.4% | 0.46 |
| S3 Six-Cycle Rotation | 7.2% | 13.0% | 0.43 | -31.8% | 0.23 |
| S4 Target-Vol | 3.7% | 3.9% | 0.36 | -9.6% | 0.39 |
| *Benchmark: Equal-Weight* | 11.0% | 11.0% | 0.80 | -21.7% | 0.51 |
| *Benchmark: SPY (S&P 500)* | 15.1% | 18.1% | 0.74 | -33.7% | 0.45 |

**🇨🇳 China market** — 2014-01 → 2025-10, prices LSEG + Wind, macro AkShare + NBS PMI ([REPORT_CHINA.md](REPORT_CHINA.md)):

| Strategy | CAGR | AnnVol | Sharpe | MaxDD | Calmar |
|---|---|---|---|---|---|
| S1 Style Rotation | 12.2% | 24.5% | 0.50 | -51.3% | 0.24 |
| S2 All-Weather | 10.8% | 6.8% | 1.20 | -10.2% | 1.06 |
| S3 Six-Cycle Rotation | 9.1% | 13.4% | 0.54 | -22.8% | 0.40 |
| S4 Target-Vol | 4.0% | 4.6% | 0.37 | -9.9% | 0.41 |
| *Benchmark: Equal-Weight* | 10.6% | 12.5% | 0.69 | -27.3% | 0.39 |

*CAGR = annual return · Sharpe = return per unit of risk (higher is better) · MaxDD = worst
peak-to-trough drop (smaller is better). In **both** markets the main rotation (S3) trailed a simple
equal-weight of the same legs — the cycle-timing overlay added little. Full tables and interpretation
in [REPORT_US.md](REPORT_US.md) and [REPORT_CHINA.md](REPORT_CHINA.md).*

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

The same engine also runs the **China market** ([`configs/china.yaml`](configs/china.yaml)) off a committed CSV snapshot — see the [China path](#china-market-path) below.

See [`PLAN.md`](PLAN.md) for the design and [`REPORT_US.md`](REPORT_US.md) / [`REPORT_CHINA.md`](REPORT_CHINA.md) for the full write-ups + results.

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
Writes all artifacts to `outputs/run1/` and a comprehensive `REPORT_US.md` at the
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

### China-market path

The China reproduction runs entirely off a **committed CSV snapshot** in [`data/China/`](data/China/) — no API keys:

```bash
python -m sixcycle.cli run \
  --config configs/china.yaml \
  --source csvdir --macro-source csvdir \
  --strategies s1,s2,s3,s4 \
  --out-dir outputs/run_china \
  --report REPORT_CHINA.md
```

**Data sources** (window 2014-01 → 2025-10):

| Series | File in `data/China/` | Source |
|---|---|---|
| Growth (159915 ChiNext), Quality (980092), Value (H30269), Gold (518880) | `Growth_*`, `FreeCashFlow_*`, `DividendLowVol_*`, `Gold_*` | LSEG |
| Bond (CBA21801 ChinaBond 30Y), Commodity (IMCI SHFE non-ferrous) | `Bond_ChinaBond30Y.csv`, `Commodity_SHFENonferrous.csv` | Wind terminal export → `scripts/convert_lseg_xlsx.py` |
| Money (FDR007 repo), Credit (new RMB loans) | `Money_FDR007.csv`, `Credit_NewLoans.csv` | AkShare → `scripts/fetch_china_macro.py` |
| Growth signal (NBS official PMI) | `PMI_NBS.csv` | LSEG |

To refresh the macro snapshot (network required): `python scripts/fetch_china_macro.py`. To re-convert Wind price exports: `python scripts/convert_lseg_xlsx.py`. The China config uses the PMI growth signal (`--growth-signal pmi`), a flow-based credit pulse, an equal-weight benchmark (no single-ticker benchmark), and omits the US HY-spread tie-break.

---

## Key flags (`run`)

| Flag | Default | Meaning |
|---|---|---|
| `--strategies` | `s1,s2,s3,s4` | which strategies (benchmarks always run) |
| `--source` | `tiingo` | price source: `tiingo` / `stooq` / `csv` / `csvdir` (China) |
| `--macro-source` | `fred` | macro source: `fred` / `csv` / `csvdir` (China) |
| `--config` | `configs/default.yaml` | YAML config; use `configs/china.yaml` for the China path |
| `--rebalance` | `M` | `M` monthly (paper) or `W` weekly (AxiomQ) |
| `--growth-signal` | `indpro` | growth proxy: `indpro` / `cfnai` / `pmi` (China) |
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
  datasources/       # tiingo / stooq / fred / csv / csvdir + cache
  strategy/          # s1..s4 + benchmarks
configs/default.yaml # US parameters (single source of truth)
configs/china.yaml   # China parameters (PMI growth signal, flow credit, EW benchmark)
data/China/          # committed CSV snapshot for the China run
scripts/make_offline_data.py   # US offline snapshot
scripts/fetch_china_macro.py   # AkShare → Money_FDR007.csv / Credit_NewLoans.csv
scripts/convert_lseg_xlsx.py   # LSEG/Wind xlsx → date,close CSV
tests/
```

> **Disclaimer.** Research/education only. The US run is a *structural transfer test*
> of the paper's idea to US markets; the China run is a leak-free reproduction on its
> native market. Neither is investment advice. All results are model output on the
> data and documented assumptions described — read the caveats in each report.
