"""Minimal .env loader (no python-dotenv dependency).

Reads ``.env.local`` then ``.env`` from the repo root and injects any
``KEY=VALUE`` pairs into ``os.environ`` *without* overriding variables already
set in the real environment (so an explicit ``export`` always wins).
"""
from __future__ import annotations

import os
from pathlib import Path

from .config import REPO_ROOT


def load_dotenv(filenames: tuple[str, ...] = (".env.local", ".env")) -> list[str]:
    """Load env files; return the list of keys that were set."""
    loaded: list[str] = []
    for name in filenames:
        p = REPO_ROOT / name
        if not p.exists():
            continue
        for raw in p.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and val and key not in os.environ:
                os.environ[key] = val
                loaded.append(key)
    return loaded
