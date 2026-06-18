"""Point-in-time discipline: future macro data must not change past stage labels."""
import numpy as np
import pandas as pd

from sixcycle.classifier import classify

SIG = {
    "money_series": "DGS3MO", "credit_series": "BUSLOANS",
    "credit_spread_series": "BAMLH0A0HYM2", "growth_series": "INDPRO",
    "growth_signal": "indpro", "cfnai_series": "CFNAI", "riskfree_series": "DGS3MO",
    "money_lookback_m": 3, "money_deadband_bps": 5, "credit_yoy_base_m": 12,
    "credit_pulse_m": 3, "growth_yoy_base_m": 12, "growth_accel_m": 3,
    "deadband_frac": 0.0, "macro_lag_days": 21, "clock_monotonic": False,
}


def _macro(end):
    months = pd.date_range("2010-01-01", end, freq="MS")
    m = len(months)
    phase = np.linspace(0, 6 * np.pi, m)
    rng = np.random.default_rng(1)
    return {
        "DGS3MO": pd.Series(np.clip(2.5 + 2 * np.sin(phase), 0.05, 6), index=months),
        "BUSLOANS": pd.Series(1500 * (1 + 0.05) ** (np.arange(m) / 12), index=months),
        "BAMLH0A0HYM2": pd.Series(np.clip(5 - 1.5 * np.sin(phase - 0.6), 2.5, 10), index=months),
        "INDPRO": pd.Series(100 * np.exp(np.cumsum(0.02 / 12 + 0.002 * np.sin(phase))), index=months),
        "CFNAI": pd.Series(0.4 * np.sin(phase), index=months),
    }


def test_future_data_does_not_change_past_labels():
    cutoff = pd.Timestamp("2022-01-01")
    target = pd.bdate_range("2015-01-01", "2022-12-31")

    base = classify(_macro("2022-12-31"), SIG, target)

    # corrupt everything strictly after the cutoff, re-run
    perturbed_macro = _macro("2022-12-31")
    for sid, s in perturbed_macro.items():
        s.loc[s.index > cutoff] = s.loc[s.index > cutoff] * 5.0 + 99.0
    perturbed = classify(perturbed_macro, SIG, target)

    # labels well before the cutoff (beyond the publication lag) must be identical
    safe = target[target < cutoff - pd.Timedelta(days=40)]
    a = base.stages.reindex(safe).dropna()
    b = perturbed.stages.reindex(safe).dropna()
    common = a.index.intersection(b.index)
    assert len(common) > 100
    assert (a.loc[common] == b.loc[common]).all(), "future data leaked into past labels"
