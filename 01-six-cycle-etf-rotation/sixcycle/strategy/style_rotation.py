"""S1 — Style Rotation.

Switch a Growth/Quality/Value style blend by stage, using the paper's explicit
percentage weights (brief 1.3). No inverse-vol here: the paper specifies fixed
style percentages, so we honour them directly.
"""
from __future__ import annotations

import pandas as pd

from .base import Context, Strategy


class StyleRotation(Strategy):
    name = "s1_style"

    def target_weights(self, decision_date: pd.Timestamp, ctx: Context) -> pd.Series:
        stage = ctx.stage_at(decision_date)
        if stage is None:
            return pd.Series(dtype=float)
        leg_weights = ctx.style_weights[stage]
        out = {}
        for leg, w in leg_weights.items():
            ticker = ctx.universe.leg_to_ticker.get(leg)
            if ticker is not None:
                out[ticker] = out.get(ticker, 0.0) + w
        s = pd.Series(out, dtype=float)
        return s / s.sum() if s.sum() else s
