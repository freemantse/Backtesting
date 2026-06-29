"""Fetch the two China macro signals not available via LSEG/Wind, and snapshot them
to per-series CSVs in ``data/China/`` (the ``--source csvdir`` run path reads these).

Pulled from the free **AkShare** library (reads mainland sites — needs network at fetch
time only; the committed CSVs make the backtest reproducible offline afterwards):

  * **Money = FDR007** — depository-institution 7-day pledged-repo fixing, the tightest
    free proxy for DR007 (which is entitlement-blocked on our Wind seat). Source:
    ``repo_rate_hist`` (columns FR001/FR007/FDR001/FDR007/...). The wide-range call breaks
    upstream, so we loop per calendar year. FDR007 starts ~2014-12; the early-2014 gap is
    back-filled with FR007 (the all-institution fixing) so the series spans the full window.
    -> ``Money_FDR007.csv`` (date,value)

  * **Credit = new RMB credit flow** — the master brief's documented substitute for the
    medium/long-term loan pulse (the exact MLT breakdown isn't freely available; TSF via
    ``macro_china_shrzgm`` is SSL-blocked from here). Source:
    ``macro_china_new_financial_credit`` -> the 当月 (monthly new-credit flow, 亿元) column.
    The classifier derives the pulse itself (TTM roll -> YoY -> 3-mo diff).
    -> ``Credit_NewLoans.csv`` (date,value)

A leg that fails to fetch is logged and skipped (never zero-filled). Re-run to refresh.

Usage:  python scripts/fetch_china_macro.py [--start 2014 --end 2025 --out data/China]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def fetch_money(start_year: int, end_year: int) -> pd.Series:
    """FDR007 (FR007-filled before FDR007 exists), looped per year, as a daily Series."""
    import akshare as ak

    frames = []
    for yr in range(start_year, end_year + 1):
        s, e = f"{yr}0101", f"{yr}1231"
        try:
            df = ak.repo_rate_hist(start_date=s, end_date=e)
            if df is not None and len(df):
                frames.append(df)
        except Exception as exc:  # noqa: BLE001
            print(f"[money] {yr}: skipped ({type(exc).__name__})")
    if not frames:
        raise RuntimeError("repo_rate_hist returned nothing for any year")
    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset="date")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    fdr = pd.to_numeric(df.get("FDR007"), errors="coerce")
    fr = pd.to_numeric(df.get("FR007"), errors="coerce")
    money = fdr.combine_first(fr)  # FDR007 preferred; FR007 fills the early-2014 gap
    return money.dropna().rename("FDR007")


def fetch_credit() -> pd.Series:
    """Monthly new-credit flow (新增信贷, 当月) as a month-end-indexed Series."""
    import akshare as ak

    df = ak.macro_china_new_financial_credit()
    # 月份 like "2014年01月份" -> month-end timestamp; 当月 = monthly new-credit flow (亿元)
    months = (
        df["月份"].astype(str)
        .str.replace("年", "-", regex=False)
        .str.replace("月份", "", regex=False)
        .str.replace("月", "", regex=False)
    )
    idx = pd.to_datetime(months, format="%Y-%m") + pd.offsets.MonthEnd(0)
    val = pd.to_numeric(df["当月"], errors="coerce")
    s = pd.Series(val.values, index=idx).dropna().sort_index()
    return s.rename("NewLoans")


def _cov(s: pd.Series) -> str:
    return f"{len(s):>5} obs  {s.index.min().date()} -> {s.index.max().date()}  [{s.min():.2f}, {s.max():.2f}]"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", type=int, default=2014)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--out", default=str(ROOT / "data" / "China"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    import akshare as ak
    print(f"[akshare] version {ak.__version__}")

    wrote = 0
    try:
        # Start one year early so the 3-month money lookback is warm at the 2014 backtest start.
        money = fetch_money(args.start - 1, args.end)
        money.to_csv(out / "Money_FDR007.csv", header=["value"], index_label="date")
        print(f"[ok]   Money_FDR007.csv     {_cov(money)}")
        wrote += 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Money/FDR007: {type(exc).__name__}: {exc}")

    try:
        # Keep FULL history (2008->): the credit pulse needs ~27 months of warmup
        # (TTM roll -> YoY -> 3-mo diff), so the signal must be valid before the 2014 start.
        credit = fetch_credit().loc[:f"{args.end}-12-31"]
        credit.to_csv(out / "Credit_NewLoans.csv", header=["value"], index_label="date")
        print(f"[ok]   Credit_NewLoans.csv  {_cov(credit)}")
        wrote += 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Credit/new-loans: {type(exc).__name__}: {exc}")

    print(f"\n[done] wrote {wrote}/2 macro CSV(s) to {out}")
    return 0 if wrote == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
