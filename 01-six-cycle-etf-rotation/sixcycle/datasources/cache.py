"""Tiny on-disk cache for fetched series (CSV; no parquet dependency)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import REPO_ROOT

CACHE_DIR = REPO_ROOT / "data" / "cache"


def _path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.csv"


def read(key: str) -> pd.DataFrame | None:
    p = _path(key)
    if not p.exists():
        return None
    return pd.read_csv(p, index_col=0, parse_dates=True)


def write(key: str, df: pd.DataFrame) -> None:
    df.to_csv(_path(key))
