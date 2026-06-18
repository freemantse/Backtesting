"""S4 — Rotation + 3% Target-Vol overlay.

S4 scales S3's basket weights by a leverage scalar so trailing realised vol
targets ~3% annualised. Residual (1 - sum of weights) sits in cash at the
risk-free rate; the engine handles the cash leg. The leverage cap and a vol
floor prevent the classic low-vol leverage blow-up.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Context, Strategy


class _TargetVol(Strategy):
    name = "s4_targetvol"

    def __init__(
        self,
        base: Strategy,
        base_returns: pd.Series,
        target: float = 0.03,
        lookback: int = 60,
        max_leverage: float = 3.0,
        vol_floor_annual: float = 0.01,
        ann: int = 252,
    ) -> None:
        self.base = base
        self.base_returns = base_returns.dropna()
        self.target = target
        self.lookback = lookback
        self.max_leverage = max_leverage
        self.vol_floor_annual = vol_floor_annual
        self.ann = ann

    def leverage_at(self, decision_date: pd.Timestamp) -> float:
        hist = self.base_returns.loc[self.base_returns.index < decision_date].tail(self.lookback)
        if len(hist) < max(20, self.lookback // 2):
            return 1.0
        vol = float(hist.std()) * np.sqrt(self.ann)
        vol = max(vol, self.vol_floor_annual)
        return float(np.clip(self.target / vol, 0.0, self.max_leverage))

    def target_weights(self, decision_date: pd.Timestamp, ctx: Context) -> pd.Series:
        base_w = self.base.target_weights(decision_date, ctx)
        return base_w * self.leverage_at(decision_date)


def target_vol_overlay(base: Strategy, base_returns: pd.Series, tv_cfg: dict, ann: int) -> _TargetVol:
    return _TargetVol(
        base=base,
        base_returns=base_returns,
        target=tv_cfg.get("target", 0.03),
        lookback=tv_cfg.get("lookback", 60),
        max_leverage=tv_cfg.get("max_leverage", 3.0),
        vol_floor_annual=tv_cfg.get("vol_floor_annual", 0.01),
        ann=ann,
    )
