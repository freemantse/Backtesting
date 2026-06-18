# Backtesting

A collection of quantitative trading-strategy backtests. Each strategy lives in its own folder
with a plain-language report, the charts and metrics from the latest run, and the code used to
produce them. New strategies are added as new numbered folders.

---

## 👉 Start here 

**You don't need to install anything.** Pick a strategy from the table below and click its
**Report** link — it opens right here on GitHub, with the charts and results already rendered on the
page.

## Strategies

| # | Strategy | Idea in one line | Report | Status |
|---|----------|------------------|--------|--------|
| 1 | **Six-Cycle ETF Rotation** | Rotate U.S. ETFs based on which phase the economy is in | [Read the report](01-six-cycle-etf-rotation/REPORT.md) | ✅ Done |

> *(One row is added here per strategy. The Report link is always the fastest way to the right place.)*

## How to read a strategy report

Every report follows the same shape, so once you've read one you can read them all:

1. **Executive summary** (top) — the takeaway in a few sentences.
2. **Headline metrics table** — return (CAGR), risk (volatility, max drawdown), and
   risk-adjusted return (Sharpe). Higher CAGR/Sharpe is better; a smaller (less negative)
   max-drawdown is better.
3. **Equity-curve chart** — how an investment would have grown over time vs. simple benchmarks.
4. **Caveats** (near the end) — the honest limitations. Always worth reading before drawing
   conclusions. These are research/education tests, **not** investment advice.

## Want to run it yourself?

Reading the report is enough — but if you'd like to reproduce the results on your own computer,
here's the beginner-friendly path. (Mac/Windows/Linux all work.)

1. **Install Python 3.9 or newer** from [python.org](https://www.python.org/downloads/).
   To check it worked, open a terminal and run `python --version` — if it prints a number, you're set.
2. **Download the code.** Either click the green **Code → Download ZIP** button at the top of this
   page and unzip it, or, if you have git: `git clone <this-repo-url>`.
3. **Open a terminal in the strategy folder:**
   ```bash
   cd 01-six-cycle-etf-rotation
   ```
4. **Install the requirements** (one-time):
   ```bash
   pip install -r requirements.txt
   ```
5. **Run the demo** — this uses bundled offline data, so **no accounts or API keys are needed:**
   ```bash
   python -m sixcycle.cli run --source csv --macro-source csv --out-dir outputs/demo
   ```
6. **See the results** — open the newly created `outputs/demo/REPORT.md` and the charts
   (`.png` files) in that folder.

> **On a Mac?** If `python` / `pip` aren't found, use `python3` / `pip3` instead.
> Each strategy folder also has its own README with more detail and advanced options.

---

*Research and education only. Nothing here is investment advice.*
