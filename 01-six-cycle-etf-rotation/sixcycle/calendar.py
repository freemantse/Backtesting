"""Trading-day calendar helpers: rebalance dates and execution lag.

We avoid an external exchange-calendar dependency and derive the trading-day
grid from the union of available price dates. Rebalance dates are the last
trading day of each month (``M``) or week (``W``).
"""
from __future__ import annotations

import pandas as pd


def trading_days(prices: pd.DataFrame) -> pd.DatetimeIndex:
    """Canonical trading-day index = the price index (already business days)."""
    return prices.index


def rebalance_dates(index: pd.DatetimeIndex, freq: str = "M") -> pd.DatetimeIndex:
    """Last trading day of each calendar month (M) or week (W) in ``index``."""
    freq = freq.upper()
    if freq not in ("M", "W"):
        raise ValueError(f"rebalance freq must be 'M' or 'W', got {freq!r}")
    s = pd.Series(index, index=index)
    # group by period, take the last trading day in each period
    period = "W" if freq == "W" else "M"
    grouped = s.groupby(index.to_period(period)).last()
    return pd.DatetimeIndex(grouped.values)


def shift_trading_days(index: pd.DatetimeIndex, date: pd.Timestamp, n: int) -> pd.Timestamp:
    """Return the trading day ``n`` positions after ``date`` in ``index``.

    Clamps to the last available trading day. Used for the execution lag so a
    decision made at month-end becomes effective on the next trading day.
    """
    pos = index.searchsorted(date)
    new_pos = min(pos + n, len(index) - 1)
    return index[new_pos]
