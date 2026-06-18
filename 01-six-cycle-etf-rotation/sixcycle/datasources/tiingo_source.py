"""Tiingo adjusted end-of-day prices (primary price source).

Free API key required (env ``TIINGO_API_KEY``). Uses the REST CSV endpoint via
stdlib HTTP so the optional ``tiingo`` package is not strictly required, but
falls back to it if present. Returns dividend+split-adjusted close (``adjClose``).
"""
from __future__ import annotations

import os

import pandas as pd

from . import _http
from .base import PriceSource


class TiingoSource(PriceSource):
    name = "tiingo"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("TIINGO_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "TIINGO_API_KEY not set. Get a free key at https://www.tiingo.com "
                "and `export TIINGO_API_KEY=...`, or use --source stooq / --source csv."
            )

    def _one(self, ticker: str, start: str, end: str) -> pd.Series:
        url = (
            f"https://api.tiingo.com/tiingo/daily/{ticker}/prices"
            f"?startDate={start}&endDate={end}&format=csv&token={self.api_key}"
        )
        buf = _http.get_csv_buffer(url)
        df = pd.read_csv(buf, parse_dates=["date"]).set_index("date")
        col = "adjClose" if "adjClose" in df.columns else "close"
        return df[col].rename(ticker)

    def history(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        cols = {}
        for t in tickers:
            try:
                cols[t] = self._one(t, start, end)
            except Exception as exc:  # noqa: BLE001
                print(f"[tiingo] warning: failed to fetch {t}: {exc}")
        if not cols:
            raise RuntimeError("Tiingo returned no data for any ticker.")
        return pd.DataFrame(cols).sort_index()
