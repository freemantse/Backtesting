"""FRED macro series, with point-in-time (ALFRED vintage) support.

Two modes:
  * With ``FRED_API_KEY`` + the ``fredapi`` package -> true ALFRED vintages
    (``vintage()`` returns the full [ref_date, vintage_date, value] archive),
    the core fix vs AxiomQ's hindsight timeline.
  * Keyless fallback -> the public ``fredgraph.csv`` endpoint returns the
    latest revision only. The classifier then applies a fixed publication lag
    (``signals.macro_lag_days``) to stay point-in-time-honest. Documented.
"""
from __future__ import annotations

import os

import pandas as pd

from . import _http
from .base import MacroSource


class FredSource(MacroSource):
    name = "fred"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        self._fred = None
        if self.api_key:
            try:
                from fredapi import Fred  # lazy

                self._fred = Fred(api_key=self.api_key)
            except Exception as exc:  # noqa: BLE001
                print(f"[fred] fredapi unavailable ({exc}); using keyless CSV endpoint.")

    # ---- latest-revision series -----------------------------------------
    def series(self, series_id: str, start: str, end: str) -> pd.Series:
        # 1. fredapi (best: official API + vintages) if installed
        if self._fred is not None:
            s = self._fred.get_series(series_id, observation_start=start, observation_end=end)
            return s.rename(series_id).dropna()
        # 2. official REST API with a key (no extra package; reachable host)
        if self.api_key:
            return self._series_rest(series_id, start, end)
        # 3. keyless public CSV fallback (may be blocked on some networks)
        url = (
            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
            f"&cosd={start}&coed={end}"
        )
        buf = _http.get_csv_buffer(url)
        df = pd.read_csv(buf)
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col)
        val = pd.to_numeric(df[series_id], errors="coerce")
        return val.rename(series_id).dropna()

    def _series_rest(self, series_id: str, start: str, end: str) -> pd.Series:
        """FRED official REST API (api.stlouisfed.org) using just the key."""
        import json

        url = (
            "https://api.stlouisfed.org/fred/series/observations?"
            f"series_id={series_id}&api_key={self.api_key}&file_type=json"
            f"&observation_start={start}&observation_end={end}"
        )
        payload = json.loads(_http.get_text(url))
        obs = payload.get("observations", [])
        idx = pd.to_datetime([o["date"] for o in obs])
        vals = pd.to_numeric([o["value"] for o in obs], errors="coerce")
        return pd.Series(vals, index=idx, name=series_id).dropna()

    # ---- point-in-time vintages (requires fredapi) ----------------------
    def vintage(self, series_id: str, start: str, end: str) -> pd.DataFrame | None:
        if self._fred is None:
            return None
        try:
            # all releases -> DataFrame with realtime_start vintage dates
            df = self._fred.get_series_all_releases(series_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[fred] vintage fetch failed for {series_id}: {exc}")
            return None
        df = df.rename(
            columns={"date": "ref_date", "realtime_start": "vintage_date", "value": "value"}
        )
        df["ref_date"] = pd.to_datetime(df["ref_date"])
        df["vintage_date"] = pd.to_datetime(df["vintage_date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["value"])
