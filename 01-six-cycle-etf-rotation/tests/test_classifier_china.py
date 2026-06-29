"""China classifier additions: PMI growth mode, credit flow TTM-roll, optional HY spread."""
import numpy as np
import pandas as pd

from sixcycle.classifier import _credit_signal, _growth_signal


def _monthly(values, start="2010-01-31"):
    idx = pd.date_range(start, periods=len(values), freq="ME")
    return pd.Series(values, index=idx)


def test_pmi_mode_expansion_vs_contraction():
    """PMI > 50 -> growth up (+1); < 50 -> down (-1)."""
    pmi = _monthly([52.0, 51.0, 49.0, 48.5, 53.0])
    sig = {"growth_signal": "pmi", "growth_series": "PMI", "pmi_neutral": 50.0, "pmi_deadband": 0.0}
    state, metric = _growth_signal({"PMI": pmi}, sig)
    assert state.iloc[0] == 1.0 and state.iloc[1] == 1.0
    assert state.iloc[2] == -1.0 and state.iloc[3] == -1.0
    assert state.iloc[4] == 1.0
    assert metric.name == "growth_pmi_vs50"


def test_credit_flow_ttm_roll_runs_and_signs():
    """A monthly FLOW with seasonal spikes/negatives still yields a finite pulse via TTM roll."""
    rng = np.linspace(8000, 12000, 60) + np.tile([5000, -1000, 0, 200, 100, -50], 10)
    loans = _monthly(rng)
    sig = {"credit_series": "NewLoans", "credit_is_flow": True,
           "credit_yoy_base_m": 12, "credit_pulse_m": 3, "deadband_frac": 0.0}
    state, pulse = _credit_signal({"NewLoans": loans}, sig)
    # once warm (>27 months), the state is decided (+/-1), never NaN
    assert set(state.dropna().unique()).issubset({-1.0, 1.0})
    assert state.dropna().shape[0] > 0


def test_credit_optional_spread_no_crash_without_series():
    """China omits credit_spread_series -> ties carry prior state, no KeyError."""
    loans = _monthly(list(range(100, 160)))  # steadily rising -> positive pulse
    sig = {"credit_series": "NewLoans", "credit_is_flow": False,
           "credit_yoy_base_m": 12, "credit_pulse_m": 3, "deadband_frac": 0.0}
    state, _ = _credit_signal({"NewLoans": loans}, sig)  # no spread key at all
    assert state.dropna().shape[0] > 0
