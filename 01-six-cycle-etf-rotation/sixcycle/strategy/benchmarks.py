"""Benchmarks: ETF equal-weight (rotation universe) and buy-and-hold (SPY)."""
from __future__ import annotations

import pandas as pd

from .base import Context, Strategy


class EqualWeight(Strategy):
    name = "ew"

    def target_weights(self, decision_date: pd.Timestamp, ctx: Context) -> pd.Series:
        tickers = ctx.universe.core_tickers()
        avail = [t for t in tickers if t in ctx.returns.columns]
        return pd.Series(1.0 / len(avail), index=avail)


class BuyHold(Strategy):
    """100% in one ticker (the benchmark, e.g. SPY)."""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        self.name = ticker.lower()

    def target_weights(self, decision_date: pd.Timestamp, ctx: Context) -> pd.Series:
        return pd.Series({self.ticker: 1.0})
