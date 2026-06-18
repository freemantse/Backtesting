"""Universe resolution: leg <-> ETF mapping, inception dates, splice config.

Keeps the mapping between the paper's abstract "legs" (growth/quality/value/
gold/commodity/bond) and concrete US ETF tickers, plus the inception dates the
backtest uses to detect missing history and decide splicing.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt

from .config import Config


@dataclass(frozen=True)
class Universe:
    leg_to_ticker: dict[str, str]
    inception: dict[str, dt.date]
    splice_proxy: dict[str, str]  # ticker -> proxy ticker for pre-inception history

    @classmethod
    def from_config(cls, cfg: Config) -> "Universe":
        leg_to_ticker = dict(cfg.universe)
        inception = {
            k: dt.date.fromisoformat(v) for k, v in cfg.inception.items()
        }
        return cls(
            leg_to_ticker=leg_to_ticker,
            inception=inception,
            splice_proxy=dict(cfg.splice_proxy),
        )

    @property
    def ticker_to_leg(self) -> dict[str, str]:
        return {v: k for k, v in self.leg_to_ticker.items()}

    def tickers(self, include_benchmark: bool = True) -> list[str]:
        legs = self.leg_to_ticker.copy()
        if not include_benchmark:
            legs.pop("benchmark", None)
        return sorted(set(legs.values()))

    def core_tickers(self) -> list[str]:
        """The six rotation legs (excludes the benchmark)."""
        return [
            self.leg_to_ticker[leg]
            for leg in ("growth", "quality", "value", "gold", "commodity", "bond")
            if leg in self.leg_to_ticker
        ]

    def proxy_for(self, ticker: str) -> str | None:
        return self.splice_proxy.get(ticker)

    def latest_inception(self, tickers: list[str]) -> dt.date | None:
        """Latest inception among the given tickers (the binding start date)."""
        dates = [self.inception[t] for t in tickers if t in self.inception]
        return max(dates) if dates else None
