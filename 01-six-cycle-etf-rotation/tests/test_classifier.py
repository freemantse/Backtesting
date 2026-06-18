"""Classifier: the 8 sign combinations map to the documented stages."""
import itertools

import pandas as pd

from sixcycle.classifier import STAGE_MAP, STAGE_NAMES, _map_stage


def test_all_eight_combos_have_a_stage():
    combos = list(itertools.product([+1, -1], repeat=3))
    assert len(STAGE_MAP) == 8
    for c in combos:
        assert c in STAGE_MAP, f"missing combo {c}"
        assert STAGE_MAP[c] in STAGE_NAMES


def test_canonical_clock_mapping():
    # the six "clean" combinations follow the monetary->credit->growth clock
    assert STAGE_MAP[(+1, -1, -1)] == 6   # easing into weakness
    assert STAGE_MAP[(+1, +1, -1)] == 1   # credit turns up
    assert STAGE_MAP[(+1, +1, +1)] == 2   # full recovery
    assert STAGE_MAP[(-1, +1, +1)] == 3   # money tightens, still growing
    assert STAGE_MAP[(-1, -1, +1)] == 4   # credit rolls over
    assert STAGE_MAP[(-1, -1, -1)] == 5   # confirmed slowdown


def test_map_stage_handles_nan():
    assert pd.isna(_map_stage(float("nan"), 1, 1))
