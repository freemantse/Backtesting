"""Backtest engine: turnover/cost arithmetic and equity construction on toy data."""
import numpy as np
import pandas as pd

from sixcycle.backtest import run_backtest
from sixcycle.strategy.base import Context, Strategy
from sixcycle.universe import Universe


class _Fixed(Strategy):
    """Hold a fixed target weight (so we can check turnover/cost exactly)."""
    name = "fixed"

    def __init__(self, w):
        self.w = w

    def target_weights(self, decision_date, ctx):
        return self.w


def _ctx(returns):
    uni = Universe(leg_to_ticker={"growth": "A", "value": "B"}, inception={}, splice_proxy={})
    return Context(returns=returns, stages=pd.Series(dtype=float), universe=uni,
                   stage_baskets={}, style_weights={})


def test_zero_cost_buyhold_matches_asset():
    idx = pd.bdate_range("2021-01-01", periods=80)
    r = pd.DataFrame({"A": np.full(len(idx), 0.001), "B": np.zeros(len(idx))}, index=idx)
    ctx = _ctx(r)
    res = run_backtest(_Fixed(pd.Series({"A": 1.0})), ctx, str(idx[0].date()), str(idx[-1].date()),
                       rebalance="M", exec_lag_days=1, costs={})
    # after the first effective rebalance, equity compounds at 0.1%/day in A
    assert res.equity.iloc[-1] > 1.0
    assert (res.turnover > 0).sum() >= 1


def test_turnover_and_cost_charged_once_on_switch():
    idx = pd.bdate_range("2021-01-01", periods=60)
    r = pd.DataFrame({"A": np.zeros(len(idx)), "B": np.zeros(len(idx))}, index=idx)
    ctx = _ctx(r)
    # 100% A -> with flat returns, rebalances to A repeatedly => first turnover ~1, then 0
    res = run_backtest(_Fixed(pd.Series({"A": 1.0})), ctx, str(idx[0].date()), str(idx[-1].date()),
                       rebalance="M", exec_lag_days=1, costs={"commission_bps": 1, "slippage_bps": 2})
    first_to = res.turnover[res.turnover > 0].iloc[0]
    assert abs(first_to - 1.0) < 1e-6           # 0 -> 100% A is one-way turnover 1.0
    # cost = turnover * 3bp on that day
    cost_day = res.costs[res.costs > 0].iloc[0]
    assert abs(cost_day - 1.0 * 3e-4) < 1e-9
