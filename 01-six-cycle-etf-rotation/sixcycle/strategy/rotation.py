"""S3 — Six-Cycle Rotation (the paper's main strategy).

Hold only the current stage's basket, inverse-vol weighted within the basket.
"""
from __future__ import annotations

import pandas as pd

from .base import Context, Strategy


class Rotation(Strategy):
    name = "s3_rotation"

    def target_weights(self, decision_date: pd.Timestamp, ctx: Context) -> pd.Series:
        stage = ctx.stage_at(decision_date)
        if stage is None:
            return pd.Series(dtype=float)
        legs = ctx.stage_baskets[stage]
        tickers = ctx.legs_to_tickers(legs)
        return ctx.inv_vol(tickers, decision_date)
