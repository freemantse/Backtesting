"""Inverse-vol risk parity: normalisation, lower vol => higher weight, exclusion."""
import numpy as np
import pandas as pd

from sixcycle.riskparity import inverse_vol_weights


def _returns():
    idx = pd.bdate_range("2020-01-01", periods=120)
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "LOWVOL": rng.normal(0, 0.005, len(idx)),
            "HIVOL": rng.normal(0, 0.02, len(idx)),
        },
        index=idx,
    )


def test_weights_sum_to_one_and_favor_low_vol():
    r = _returns()
    w = inverse_vol_weights(r, ["LOWVOL", "HIVOL"], r.index[-1], lookback=60)
    assert abs(w.sum() - 1.0) < 1e-9
    assert w["LOWVOL"] > w["HIVOL"]


def test_excludes_insufficient_history():
    r = _returns()
    r["NEW"] = np.nan
    r.loc[r.index[-5:], "NEW"] = 0.01   # only 5 obs
    w = inverse_vol_weights(r, ["LOWVOL", "HIVOL", "NEW"], r.index[-1], lookback=60)
    assert "NEW" not in w.index
    assert abs(w.sum() - 1.0) < 1e-9
