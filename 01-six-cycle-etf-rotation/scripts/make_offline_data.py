"""Populate data/offline/{prices,macro}.csv so the pipeline runs without re-fetching.

Fetches REAL data only: Tiingo (adjusted, needs key) → Stooq (keyless) for prices,
and FRED (fredgraph / official API) for macro. If real data cannot be fetched the
script errors out — it never fabricates data. Writes PROVENANCE.txt noting the path.

Usage:  python scripts/make_offline_data.py [--start 2008-01-01] [--end 2025-12-31]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OFFLINE = ROOT / "data" / "offline"

TICKERS = ["QQQ", "COWZ", "SCHD", "GLD", "DBB", "TLT", "SPY", "QUAL"]
MACRO = ["DGS3MO", "BUSLOANS", "BAMLH0A0HYM2", "INDPRO", "CFNAI"]


def _try_real(start: str, end: str) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    from sixcycle.datasources.fred_source import FredSource
    from sixcycle.datasources.stooq_source import StooqSource
    from sixcycle.datasources.tiingo_source import TiingoSource
    from sixcycle.dotenv import load_dotenv

    load_dotenv()
    prices = macro = None
    # prefer Tiingo (adjusted, needs key); fall back to Stooq (keyless)
    try:
        prices = TiingoSource().history(TICKERS, start, end)
        if prices.dropna(how="all").empty:
            prices = None
    except Exception as exc:  # noqa: BLE001
        print(f"[real] Tiingo unavailable ({exc}); trying Stooq.")
    try:
        if prices is None:
            prices = StooqSource().history(TICKERS, start, end)
        if prices.dropna(how="all").empty:
            prices = None
    except Exception as exc:  # noqa: BLE001
        print(f"[real] Stooq prices failed: {exc}")
    try:
        fs = FredSource()
        cols = {}
        for sid in MACRO:
            try:
                cols[sid] = fs.series(sid, start, end)
            except Exception as exc:  # noqa: BLE001
                print(f"[real] FRED {sid} failed: {exc}")
        macro = pd.DataFrame(cols) if cols else None
    except Exception as exc:  # noqa: BLE001
        print(f"[real] FRED failed: {exc}")
    return prices, macro


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2008-01-01")
    ap.add_argument("--end", default="2025-12-31")
    args = ap.parse_args()

    OFFLINE.mkdir(parents=True, exist_ok=True)
    prices, macro = _try_real(args.start, args.end)
    if prices is None or macro is None or prices.empty or macro.empty:
        print(
            "[offline] ERROR: could not fetch real data. Set TIINGO_API_KEY + "
            "FRED_API_KEY in .env.local and ensure network access, then retry.",
            file=sys.stderr,
        )
        return 1
    provenance = "real (Tiingo/Stooq prices + FRED macro, latest revision)"

    prices.sort_index().to_csv(OFFLINE / "prices.csv")
    macro.sort_index().to_csv(OFFLINE / "macro.csv")
    (OFFLINE / "PROVENANCE.txt").write_text(provenance + "\n")
    print(f"[offline] wrote {OFFLINE/'prices.csv'}  {prices.shape}")
    print(f"[offline] wrote {OFFLINE/'macro.csv'}   {macro.shape}")
    print(f"[offline] provenance: {provenance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
