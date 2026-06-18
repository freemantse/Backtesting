"""S2 — All-Weather.

Hold all six stage-baskets simultaneously with no timing. Two-level risk parity:
inverse-vol *within* each basket, then inverse-vol *across* baskets (using each
basket's trailing portfolio volatility). A leg's final weight is the sum over
every basket that contains it of (across-basket weight x within-basket weight).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Context, Strategy


class AllWeather(Strategy):
    name = "s2_allweather"

    def target_weights(self, decision_date: pd.Timestamp, ctx: Context) -> pd.Series:
        within: dict[int, pd.Series] = {}
        basket_ret: dict[int, pd.Series] = {}
        window = ctx.returns.loc[ctx.returns.index < decision_date].tail(ctx.rp_lookback)

        for stage, legs in ctx.stage_baskets.items():
            tickers = ctx.legs_to_tickers(legs)
            w = ctx.inv_vol(tickers, decision_date)
            within[stage] = w
            # basket return series over the trailing window (fixed current weights)
            sub = window[w.index].dropna(how="all")
            basket_ret[stage] = (sub * w).sum(axis=1)

        # across-basket inverse-vol
        across_vol = {st: max(float(r.std()), ctx.vol_floor) for st, r in basket_ret.items()}
        inv = {st: 1.0 / v for st, v in across_vol.items()}
        tot = sum(inv.values())
        across = {st: v / tot for st, v in inv.items()}

        # combine
        final: dict[str, float] = {}
        for stage, w in within.items():
            aw = across[stage]
            for ticker, ww in w.items():
                final[ticker] = final.get(ticker, 0.0) + aw * ww
        s = pd.Series(final, dtype=float)
        return s / s.sum() if s.sum() else s
