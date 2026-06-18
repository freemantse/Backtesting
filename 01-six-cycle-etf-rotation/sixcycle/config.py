"""Configuration model: typed dataclasses loaded from YAML, overridable by CLI.

`load_config()` reads ``configs/default.yaml`` (or a user path) into a
:class:`Config`. CLI flags are applied afterwards via :meth:`Config.override`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "default.yaml"


@dataclass(frozen=True)
class Config:
    """Fully-resolved run configuration (a thin wrapper over the YAML dict).

    The nested dicts (``universe``, ``signals``, ``backtest`` ...) are kept as
    plain dicts for flexibility; helper properties expose the common ones.
    """

    raw: dict[str, Any] = field(default_factory=dict)

    # ---- convenience accessors -------------------------------------------
    @property
    def dates(self) -> dict[str, str]:
        return self.raw["dates"]

    @property
    def universe(self) -> dict[str, str]:
        return self.raw["universe"]

    @property
    def inception(self) -> dict[str, str]:
        return self.raw.get("inception", {})

    @property
    def splice_proxy(self) -> dict[str, str]:
        return self.raw.get("splice_proxy", {})

    @property
    def stage_baskets(self) -> dict[int, list[str]]:
        return {int(k): v for k, v in self.raw["stage_baskets"].items()}

    @property
    def style_weights(self) -> dict[int, dict[str, float]]:
        return {int(k): v for k, v in self.raw["style_weights"].items()}

    @property
    def signals(self) -> dict[str, Any]:
        return self.raw["signals"]

    @property
    def backtest(self) -> dict[str, Any]:
        return self.raw["backtest"]

    @property
    def target_vol(self) -> dict[str, Any]:
        return self.raw["target_vol"]

    @property
    def costs(self) -> dict[str, Any]:
        return self.raw["costs"]

    def tickers(self) -> list[str]:
        """The distinct ETF tickers referenced by the active universe."""
        return sorted(set(self.universe.values()))

    def override(self, **flat_overrides: Any) -> "Config":
        """Return a new Config with dotted-path overrides applied.

        Keys use ``section.key`` notation, e.g. ``backtest.rebalance='W'`` or
        ``universe.growth='IWF'``. ``None`` values are ignored so CLI defaults
        do not clobber the YAML.
        """
        import copy

        new = copy.deepcopy(self.raw)
        for dotted, value in flat_overrides.items():
            if value is None:
                continue
            section, _, key = dotted.partition(".")
            if not key:  # top-level scalar
                new[section] = value
                continue
            new.setdefault(section, {})[key] = value
        return Config(raw=new)


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from YAML (defaults to ``configs/default.yaml``)."""
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(p, "r") as fh:
        raw = yaml.safe_load(fh)
    return Config(raw=raw)
