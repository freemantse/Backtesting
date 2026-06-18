"""Strategy context and abstract base.

A Strategy is a pure mapping ``target_weights(decision_date, ctx) -> Series``
(indexed by ticker, summing to ~1). The backtest engine handles the execution
lag, drift, turnover and costs — strategies never see P&L.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd

from ..riskparity import inverse_vol_weights
from ..universe import Universe


@dataclass
class Context:
    returns: pd.DataFrame          # daily simple returns, columns = tickers
    stages: pd.Series              # daily stage label (as-known), index = trading days
    universe: Universe
    stage_baskets: dict[int, list[str]]   # stage -> list of legs
    style_weights: dict[int, dict[str, float]]
    rp_lookback: int = 60
    vol_floor: float = 1e-4

    def stage_at(self, date: pd.Timestamp) -> int | None:
        v = self.stages.asof(date)
        if pd.isna(v):
            return None
        return int(v)

    def legs_to_tickers(self, legs: list[str]) -> list[str]:
        return [self.universe.leg_to_ticker[l] for l in legs if l in self.universe.leg_to_ticker]

    def inv_vol(self, tickers: list[str], as_of: pd.Timestamp) -> pd.Series:
        return inverse_vol_weights(
            self.returns, tickers, as_of, self.rp_lookback, self.vol_floor
        )


class Strategy(ABC):
    name: str = "abstract"

    @abstractmethod
    def target_weights(self, decision_date: pd.Timestamp, ctx: Context) -> pd.Series:
        """Target portfolio weights at ``decision_date`` (index = tickers)."""
        raise NotImplementedError
