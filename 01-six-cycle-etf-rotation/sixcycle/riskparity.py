"""Inverse-volatility ("naive risk parity") weighting.

w_i proportional to 1/vol_i over a trailing lookback, normalised to sum 1.
Legs with insufficient history are dropped and the rest renormalised — never
zero-filled (that silent zeroing was AxiomQ's gold-leg bug).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def inverse_vol_weights(
    returns: pd.DataFrame,
    legs: list[str],
    as_of: pd.Timestamp,
    lookback: int = 60,
    vol_floor: float = 1e-4,
    min_obs: int | None = None,
) -> pd.Series:
    """Inverse-vol weights for ``legs`` using returns strictly before ``as_of``.

    Returns a Series indexed by the held tickers (summing to 1). Tickers with
    fewer than ``min_obs`` valid observations are excluded.
    """
    if min_obs is None:
        min_obs = max(20, lookback // 2)
    window = returns.loc[returns.index < as_of, legs].tail(lookback)
    vols = {}
    for leg in legs:
        col = window[leg].dropna()
        if len(col) >= min_obs:
            vols[leg] = max(float(col.std()), vol_floor)
    if not vols:
        # fallback: equal weight across requested legs
        return pd.Series(1.0 / len(legs), index=legs)
    inv = {k: 1.0 / v for k, v in vols.items()}
    total = sum(inv.values())
    return pd.Series({k: v / total for k, v in inv.items()})
