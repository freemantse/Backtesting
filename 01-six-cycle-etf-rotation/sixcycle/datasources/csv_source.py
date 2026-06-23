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
CHINA_DIR = REPO_ROOT / "data" / "China"

# Series code (as referenced by configs/universe) -> CSV filename in data/China/.
# The CSVs keep the LSEG workbook basenames; two index legs carry the provider name
# (CNI/CSI) rather than the numeric code, so the mapping is explicit rather than glob-able.
# Produced by scripts/convert_lseg_xlsx.py. A plain ``<code>.csv`` is also accepted.
CHINA_SERIES_FILES = {
    "159915": "Growth_159915.csv",       # E Fund ChiNext ETF
    "518880": "Gold_518880.csv",         # Hua An YiFu Gold ETF
    "980092": "FreeCashFlow_CNI.csv",    # CNI Free Cash Flow index
    "H30269": "DividendLowVol_CSI.csv",  # CSI Dividend Low-Vol index
    "NBS_PMI": "PMI_NBS.csv",            # NBS Manufacturing PMI (first-release)
}


def _china_csv_path(directory: Path, code: str) -> Path:
    """Resolve a series code to its CSV path (mapped name, else ``<code>.csv``)."""
    return directory / CHINA_SERIES_FILES.get(code, f"{code}.csv")


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


class CsvDirPriceSource(PriceSource):
    """Per-series CSV prices — one ``<Name_Code>.csv`` (date,close) per leg in ``data/China/``.

    Reads the clean files produced by ``scripts/convert_lseg_xlsx.py`` from the
    delivered LSEG workbooks and assembles them into the wide (date x ticker)
    panel the engine expects. Series codes resolve to filenames via
    ``CHINA_SERIES_FILES``. A leg whose CSV is absent is skipped with a warning
    (never zero-filled — the AxiomQ gold bug); the splice activates once it lands.
    """

    name = "csvdir"

    def __init__(self, dir: Path | None = None) -> None:
        self.dir = dir or CHINA_DIR

    def history(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        cols: dict[str, pd.Series] = {}
        missing: list[str] = []
        for t in tickers:
            path = _china_csv_path(self.dir, t)
            if not path.exists():
                missing.append(t)
                continue
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            cols[t] = df["close"] if "close" in df.columns else df.iloc[:, 0]
        if missing:
            print(f"[csvdir] warning: no per-series CSV for tickers (leg skipped): {sorted(missing)}")
        if not cols:
            raise FileNotFoundError(
                f"no per-series price CSVs found in {self.dir} for {tickers}. "
                f"Run `python scripts/convert_lseg_xlsx.py` first."
            )
        df = pd.DataFrame(cols).sort_index()
        return df.loc[start:end]


class CsvDirMacroSource(MacroSource):
    """Per-series CSV macro from the LSEG workbooks (point-in-time first-release).

    Reads the series CSV from ``data/China/`` (filename resolved via
    ``CHINA_SERIES_FILES``). The NBS PMI file carries
    ``release_date,period,first_release`` — a true first-release series, so
    ``series()`` is indexed by the reference period while ``vintage()`` exposes the
    actual ``Original Release Date`` for point-in-time use (same [ref_date,
    vintage_date, value] shape as ``FredSource``). A plain ``date,value`` CSV is
    also accepted (returned as a latest-revision series, no vintages).
    """

    name = "csvdir"
    _FR_COLS = {"release_date", "period", "first_release"}

    def __init__(self, dir: Path | None = None) -> None:
        self.dir = dir or CHINA_DIR

    def _read(self, series_id: str) -> pd.DataFrame:
        path = _china_csv_path(self.dir, series_id)
        if not path.exists():
            raise KeyError(f"macro series {series_id!r} not found at {path}")
        return pd.read_csv(path)

    def series(self, series_id: str, start: str, end: str) -> pd.Series:
        df = self._read(series_id)
        if self._FR_COLS.issubset(df.columns):  # first-release frame
            idx = pd.to_datetime(df["period"])
            s = pd.Series(pd.to_numeric(df["first_release"], errors="coerce").values, index=idx)
        else:  # plain date,value
            idx = pd.to_datetime(df.iloc[:, 0])
            s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values, index=idx)
        return s.sort_index().loc[start:end].dropna().rename(series_id)

    def vintage(self, series_id: str, start: str, end: str) -> pd.DataFrame | None:
        df = self._read(series_id)
        if not self._FR_COLS.issubset(df.columns):
            return None  # no point-in-time info in a plain date,value file
        out = pd.DataFrame(
            {
                "ref_date": pd.to_datetime(df["period"]),
                "vintage_date": pd.to_datetime(df["release_date"]),
                "value": pd.to_numeric(df["first_release"], errors="coerce"),
            }
        ).dropna(subset=["value"])
        mask = (out["ref_date"] >= start) & (out["ref_date"] <= end)
        return out.loc[mask].sort_values("vintage_date").reset_index(drop=True)
