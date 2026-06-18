"""Deterministic backtest engine.

Simulates a strategy day-by-day in dollar space (so drift, cash, leverage and
costs all fall out naturally):

  1. mark positions and cash to market with that day's returns,
  2. on an *effective* rebalance day, trade to the strategy's target weights,
     charging one-way turnover * cost_rate,
  3. record equity, weights, turnover and cost.

Decisions are made at month/week-end using only data through the decision date;
they become effective ``exec_lag_days`` trading days later (leakage-free).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import calendar as cal
from .strategy.base import Context, Strategy


@dataclass
class BacktestResult:
    name: str
    returns: pd.Series        # daily portfolio returns (net of cost)
    equity: pd.Series         # cumulative equity, base 1.0
    weights: pd.DataFrame     # daily asset weights (cash = 1 - row sum)
    turnover: pd.Series       # one-way turnover fraction per day (0 off-rebalance)
    costs: pd.Series          # cost fraction charged per day
    rebalance_weights: pd.DataFrame   # target weights snapshot per rebalance


def _cost_rate(costs: dict) -> float:
    return (costs.get("commission_bps", 0) + costs.get("slippage_bps", 0)
            + costs.get("stamp_bps", 0)) * 1e-4


def run_backtest(
    strategy: Strategy,
    ctx: Context,
    start: str,
    end: str,
    rebalance: str = "M",
    exec_lag_days: int = 1,
    costs: dict | None = None,
    rf_daily: pd.Series | None = None,
) -> BacktestResult:
    costs = costs or {}
    cost_rate = _cost_rate(costs)
    returns = ctx.returns.loc[start:end].copy()
    idx = returns.index
    if rf_daily is None:
        rf_daily = pd.Series(0.0, index=idx)
    rf_daily = rf_daily.reindex(idx).fillna(0.0)

    # decision dates -> effective dates -> target weights
    decision_dates = cal.rebalance_dates(idx, rebalance)
    eff_targets: dict[pd.Timestamp, pd.Series] = {}
    snapshots: dict[pd.Timestamp, pd.Series] = {}
    for d in decision_dates:
        w = strategy.target_weights(d, ctx)
        if w is None or w.empty:
            continue
        e = cal.shift_trading_days(idx, d, exec_lag_days)
        eff_targets[e] = w
        snapshots[d] = w

    if not eff_targets:
        raise RuntimeError(f"strategy {strategy.name} produced no target weights")

    first_eff = min(eff_targets)
    tickers = list(returns.columns)

    positions = pd.Series(0.0, index=tickers)   # dollar holdings
    cash = 1.0
    started = False

    eq_dates, eq_vals, ret_vals = [], [], []
    w_rows, to_vals, cost_vals = [], [], []
    prev_equity = 1.0

    for t in idx:
        if not started:
            if t < first_eff:
                continue
            started = True  # begin at first effective rebalance with 100% cash
        # 1. mark to market
        r = returns.loc[t].fillna(0.0)
        positions = positions * (1.0 + r)
        cash = cash * (1.0 + float(rf_daily.loc[t]))
        equity = float(positions.sum() + cash)

        turnover = 0.0
        cost_frac = 0.0
        # 2. rebalance if effective today
        if t in eff_targets and equity > 0:
            w_pre = positions / equity
            w_tgt = eff_targets[t].reindex(tickers).fillna(0.0)
            # one-way turnover including the cash leg (so cash<->asset moves and
            # leverage changes are counted): 0.5 * L1 over assets + cash.
            cash_pre = 1.0 - float(w_pre.sum())
            cash_tgt = 1.0 - float(w_tgt.sum())
            turnover = 0.5 * (float((w_tgt - w_pre).abs().sum()) + abs(cash_tgt - cash_pre))
            cost_frac = turnover * cost_rate
            cost_dollar = cost_frac * equity
            positions = w_tgt * equity
            cash = equity - float(positions.sum()) - cost_dollar
            equity = equity - cost_dollar

        # 3. record
        ret_vals.append(equity / prev_equity - 1.0 if prev_equity else 0.0)
        prev_equity = equity
        eq_dates.append(t)
        eq_vals.append(equity)
        w_rows.append((positions / equity) if equity else positions * 0.0)
        to_vals.append(turnover)
        cost_vals.append(cost_frac)

    equity_s = pd.Series(eq_vals, index=eq_dates, name=strategy.name)
    returns_s = pd.Series(ret_vals, index=eq_dates, name=strategy.name)
    weights_df = pd.DataFrame(w_rows, index=eq_dates).fillna(0.0)
    turnover_s = pd.Series(to_vals, index=eq_dates, name="turnover")
    costs_s = pd.Series(cost_vals, index=eq_dates, name="cost")
    snap_df = pd.DataFrame(snapshots).T.fillna(0.0)

    return BacktestResult(
        name=strategy.name,
        returns=returns_s,
        equity=equity_s,
        weights=weights_df,
        turnover=turnover_s,
        costs=costs_s,
        rebalance_weights=snap_df,
    )


def riskfree_daily(macro: dict[str, pd.Series], series_id: str, index: pd.DatetimeIndex, ann: int = 252) -> pd.Series:
    """Convert an annualised %-rate FRED series into a daily compounding rate
    aligned to the trading-day ``index`` (point-in-time forward-fill)."""
    if series_id not in macro:
        return pd.Series(0.0, index=index)
    rate = macro[series_id].copy()
    daily = (1.0 + rate / 100.0) ** (1.0 / ann) - 1.0
    return daily.reindex(index.union(daily.index)).ffill().reindex(index).fillna(0.0)
