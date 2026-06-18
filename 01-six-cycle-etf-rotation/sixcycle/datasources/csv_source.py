"""Offline CSV data source (no network, no keys).

Reads from ``data/offline/``:
  * ``prices.csv``  — index = date, columns = tickers (adjusted close).
  * ``macro.csv``   — index = date, columns = FRED series ids (latest revision).

These bundled files let the whole pipeline + report run with zero credentials.
They are populated by ``sixcycle fetch-data --source ... --save-offline`` or by
``scripts/make_offline_data`` (both fetch real data only).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import REPO_ROOT
from .base import MacroSource, PriceSource

OFFLINE_DIR = REPO_ROOT / "data" / "offline"


class CsvPriceSource(PriceSource):
    name = "csv"

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (OFFLINE_DIR / "prices.csv")

    def history(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(
                f"offline prices not found at {self.path}. Run `sixcycle fetch-data "
                f"--save-offline` (with keys/network) or `scripts/make_offline_data.py` first."
            )
        df = pd.read_csv(self.path, index_col=0, parse_dates=True)
        keep = [t for t in tickers if t in df.columns]
        missing = set(tickers) - set(keep)
        if missing:
            print(f"[csv] warning: tickers absent from offline prices: {sorted(missing)}")
        return df.loc[start:end, keep].sort_index()


class CsvMacroSource(MacroSource):
    name = "csv"

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (OFFLINE_DIR / "macro.csv")

    def series(self, series_id: str, start: str, end: str) -> pd.Series:
        if not self.path.exists():
            raise FileNotFoundError(f"offline macro not found at {self.path}.")
        df = pd.read_csv(self.path, index_col=0, parse_dates=True)
        if series_id not in df.columns:
            raise KeyError(f"series {series_id!r} not in offline macro file")
        return df.loc[start:end, series_id].dropna().rename(series_id)
