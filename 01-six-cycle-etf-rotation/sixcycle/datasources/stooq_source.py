"""Stooq prices (free, keyless) — used as a cross-check / fallback.

Stooq serves split+dividend-adjusted daily CSVs at a keyless endpoint:
``https://stooq.com/q/d/l/?s=spy.us&d1=YYYYMMDD&d2=YYYYMMDD&i=d``.
"""
from __future__ import annotations

import pandas as pd

from . import _http
from .base import PriceSource


class StooqSource(PriceSource):
    name = "stooq"

    def _one(self, ticker: str, start: str, end: str) -> pd.Series:
        d1 = start.replace("-", "")
        d2 = end.replace("-", "")
        sym = f"{ticker.lower()}.us"
        url = f"https://stooq.com/q/d/l/?s={sym}&d1={d1}&d2={d2}&i=d"
        buf = _http.get_csv_buffer(url)
        df = pd.read_csv(buf)
        if "Date" not in df.columns or "Close" not in df.columns:
            raise RuntimeError(f"unexpected Stooq payload for {ticker}: {df.columns.tolist()}")
        df["Date"] = pd.to_datetime(df["Date"])
        return df.set_index("Date")["Close"].rename(ticker)

    def history(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        cols = {}
        for t in tickers:
            try:
                cols[t] = self._one(t, start, end)
            except Exception as exc:  # noqa: BLE001
                print(f"[stooq] warning: failed to fetch {t}: {exc}")
        if not cols:
            raise RuntimeError("Stooq returned no data for any ticker.")
        return pd.DataFrame(cols).sort_index()
