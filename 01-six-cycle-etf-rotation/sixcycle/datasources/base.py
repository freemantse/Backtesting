"""Abstract contracts for price and macro data sources.

Return contracts (kept tidy so everything downstream is provider-agnostic):
  * PriceSource.history(tickers, start, end) -> DataFrame indexed by date,
    columns = tickers, values = adjusted close (dividend + split adjusted).
  * MacroSource.series(series_id, start, end) -> Series indexed by date.
  * MacroSource.vintage(series_id) -> optional DataFrame [ref_date, vintage_date,
    value] for true point-in-time; returns None if the source has no vintages.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class PriceSource(ABC):
    name: str = "abstract"

    @abstractmethod
    def history(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        """Adjusted-close history; columns = tickers, index = trading days."""
        raise NotImplementedError


class MacroSource(ABC):
    name: str = "abstract"

    @abstractmethod
    def series(self, series_id: str, start: str, end: str) -> pd.Series:
        """Latest-vintage series indexed by reference date."""
        raise NotImplementedError

    def vintage(self, series_id: str, start: str, end: str) -> pd.DataFrame | None:
        """Point-in-time vintages [ref_date, vintage_date, value], or None."""
        return None
