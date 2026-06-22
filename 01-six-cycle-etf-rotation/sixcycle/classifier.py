"""The macro classifier: three binary signals -> the six-stage clock.

Money / Credit / Growth are each reduced to +1/-1 (with a deadband + hysteresis
to suppress whipsaw), then mapped onto the six-stage clock. Everything is
computed point-in-time: signals are derived on a monthly grid from reference-
date macro data, then made available only after a publication lag, so the label
on day T uses only information knowable by T.

The 8 -> 6 mapping table is a DOCUMENTED ASSUMPTION (the paper omits it),
grounded in the monetary -> credit -> growth lead-lag chain. See REPORT_US.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

# (money, credit, growth) -> stage.  +1 = loose/expansion/up ; -1 = tight/contraction/down.
STAGE_MAP: dict[tuple[int, int, int], int] = {
    (+1, -1, -1): 6,  # Monetary Expansion  — money just eased; credit & growth still down
    (+1, +1, -1): 1,  # Credit Expansion    — easy money, credit turns up, growth not yet
    (+1, +1, +1): 2,  # Economic Recovery   — all three up
    (-1, +1, +1): 3,  # Monetary Retreat    — money tightens (leads), credit & growth still up
    (-1, -1, +1): 4,  # Credit Retreat      — money tight, credit rolls over, growth peaking
    (-1, -1, -1): 5,  # Economic Slowdown   — all three down
    (+1, -1, +1): 2,  # extra: growth-up + easy money ≈ recovery (credit = laggard)
    (-1, +1, -1): 5,  # extra: tight money + growth-down ≈ slowdown (credit = laggard)
}

STAGE_NAMES = {
    1: "Credit Expansion",
    2: "Economic Recovery",
    3: "Monetary Retreat",
    4: "Credit Retreat",
    5: "Economic Slowdown",
    6: "Monetary Expansion",
}

# clock order for the optional monotonic (adjacency) smoothing
CLOCK_ORDER = [1, 2, 3, 4, 5, 6]


@dataclass
class ClassifierResult:
    stages: pd.Series           # daily stage label on the target index (int)
    stages_monthly: pd.Series   # monthly stage label (pre-lag)
    signals_monthly: pd.DataFrame   # columns money/credit/growth in {-1,+1}
    transformed: pd.DataFrame   # underlying monthly metrics (for plotting)


def _month_end(s: pd.Series) -> pd.Series:
    return s.resample("ME").last()


def _state_with_hysteresis(metric: pd.Series, deadband: float) -> pd.Series:
    """Sign of ``metric`` with a deadband; values inside the band carry the
    previous decided state forward (hysteresis), reducing whipsaw."""
    state = pd.Series(index=metric.index, dtype=float)
    prev = np.nan
    for date, v in metric.items():
        if pd.isna(v):
            s = prev
        elif v > deadband:
            s = 1.0
        elif v < -deadband:
            s = -1.0
        else:
            s = prev
        state[date] = s
        if not pd.isna(s):
            prev = s
    return state


def _money_signal(macro: dict[str, pd.Series], sig: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
    rate = _month_end(macro[sig["money_series"]])
    change = rate - rate.shift(sig["money_lookback_m"])
    metric = -change  # falling rate = loose = +1
    deadband = sig["money_deadband_bps"] / 100.0  # series is in percent
    state = _state_with_hysteresis(metric, deadband)
    return state, change.rename("money_rate_change")


def _credit_signal(macro: dict[str, pd.Series], sig: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
    loans = _month_end(macro[sig["credit_series"]])
    yoy = loans / loans.shift(sig["credit_yoy_base_m"]) - 1.0
    pulse = yoy - yoy.shift(sig["credit_pulse_m"])
    oas = _month_end(macro[sig["credit_spread_series"]])
    oas_change = oas - oas.shift(sig["credit_pulse_m"])
    db = sig.get("deadband_frac", 0.0)
    state = pd.Series(index=pulse.index, dtype=float)
    prev = np.nan
    for date in pulse.index:
        p = pulse.get(date, np.nan)
        if not pd.isna(p) and p > db:
            s = 1.0
        elif not pd.isna(p) and p < -db:
            s = -1.0
        else:  # tie-break on HY spread: falling spread => credit expansion
            oc = oas_change.get(date, np.nan)
            if pd.isna(oc):
                s = prev
            else:
                s = 1.0 if oc < 0 else (-1.0 if oc > 0 else prev)
        state[date] = s
        if not pd.isna(s):
            prev = s
    return state, pulse.rename("credit_pulse")


def _growth_signal(macro: dict[str, pd.Series], sig: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
    which = sig.get("growth_signal", "indpro").lower()
    if which == "cfnai":
        cfnai = _month_end(macro[sig["cfnai_series"]])
        metric = cfnai.rolling(3).mean()
        state = _state_with_hysteresis(metric, sig.get("deadband_frac", 0.0))
        return state, metric.rename("growth_cfnai_ma3")
    indpro = _month_end(macro[sig["growth_series"]])
    yoy = indpro / indpro.shift(sig["growth_yoy_base_m"]) - 1.0
    accel = yoy - yoy.shift(sig["growth_accel_m"])
    state = _state_with_hysteresis(accel, sig.get("deadband_frac", 0.0))
    return state, accel.rename("growth_indpro_accel")


def _map_stage(m: float, c: float, g: float) -> float:
    if pd.isna(m) or pd.isna(c) or pd.isna(g):
        return np.nan
    return float(STAGE_MAP[(int(m), int(c), int(g))])


def _apply_monotonic(stages: pd.Series) -> pd.Series:
    """Restrict transitions to the same or the next clock stage (min-dwell 1).

    Smooths whipsaw by enforcing the clock's cyclic adjacency. A move is allowed
    only to the current stage or its clockwise neighbour; otherwise hold.
    """
    out = stages.copy()
    prev = np.nan
    for date, raw in stages.items():
        if pd.isna(raw):
            out[date] = prev
            continue
        if pd.isna(prev):
            cur = raw
        else:
            nxt = CLOCK_ORDER[(int(prev) % 6)]  # clockwise neighbour
            cur = raw if raw in (prev, nxt) else prev
        out[date] = cur
        prev = cur
    return out


def classify(
    macro: dict[str, pd.Series],
    sig: dict[str, Any],
    target_index: pd.DatetimeIndex,
) -> ClassifierResult:
    """Produce daily stage labels (point-in-time) over ``target_index``."""
    money, money_x = _money_signal(macro, sig)
    credit, credit_x = _credit_signal(macro, sig)
    growth, growth_x = _growth_signal(macro, sig)

    grid = money.index.union(credit.index).union(growth.index)
    sig_df = pd.DataFrame(
        {
            "money": money.reindex(grid),
            "credit": credit.reindex(grid),
            "growth": growth.reindex(grid),
        }
    )
    stages_monthly = sig_df.apply(
        lambda r: _map_stage(r["money"], r["credit"], r["growth"]), axis=1
    )
    if sig.get("clock_monotonic", False):
        stages_monthly = _apply_monotonic(stages_monthly)

    # point-in-time availability: a month-end label is knowable only after the lag
    lag = pd.Timedelta(days=int(sig.get("macro_lag_days", 21)))
    avail = stages_monthly.dropna().copy()
    avail.index = avail.index + lag

    # forward-fill onto the trading-day target index (as-known on each day)
    daily = avail.reindex(target_index.union(avail.index)).ffill().reindex(target_index)
    daily = daily.ffill()

    transformed = pd.DataFrame(
        {money_x.name: money_x, credit_x.name: credit_x, growth_x.name: growth_x}
    )

    return ClassifierResult(
        stages=daily.astype("float").rename("stage"),
        stages_monthly=stages_monthly.rename("stage"),
        signals_monthly=sig_df,
        transformed=transformed,
    )
