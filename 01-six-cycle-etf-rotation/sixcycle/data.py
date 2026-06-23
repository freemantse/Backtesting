"""High-level data loading: source factory, price assembly, splicing, macro.

Bridges the raw data sources to the backtest by:
  * choosing a price/macro source from a name ("tiingo"/"stooq"/"csv"/"fred"),
  * handling ETFs that launched after the requested start (clamp or proxy-splice),
  * returning a clean price panel + macro series dict + a splice manifest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt

import pandas as pd

from .config import Config
from .datasources.base import MacroSource, PriceSource
from .universe import Universe


def make_price_source(name: str) -> PriceSource:
    name = name.lower()
    if name == "tiingo":
        from .datasources.tiingo_source import TiingoSource

        return TiingoSource()
    if name == "stooq":
        from .datasources.stooq_source import StooqSource

        return StooqSource()
    if name == "csv":
        from .datasources.csv_source import CsvPriceSource

        return CsvPriceSource()
    if name == "csvdir":
        from .datasources.csv_source import CsvDirPriceSource

        return CsvDirPriceSource()
    raise ValueError(f"unknown price source {name!r}")


def make_macro_source(name: str) -> MacroSource:
    name = name.lower()
    if name == "fred":
        from .datasources.fred_source import FredSource

        return FredSource()
    if name == "csv":
        from .datasources.csv_source import CsvMacroSource

        return CsvMacroSource()
    if name == "csvdir":
        from .datasources.csv_source import CsvDirMacroSource

        return CsvDirMacroSource()
    raise ValueError(f"unknown macro source {name!r}")


@dataclass
class LoadedData:
    prices: pd.DataFrame                 # adjusted close, columns = tickers
    macro: dict[str, pd.Series]          # series_id -> reference-date series
    splice_manifest: list[dict] = field(default_factory=list)
    effective_start: str = ""


def _return_splice(proxy: pd.Series, etf: pd.Series, ter_daily: float = 0.0) -> pd.Series:
    """Chain proxy returns (before ETF inception) with ETF returns into one
    spliced adjusted-price series. Spliced on *returns* to avoid a level jump.
    """
    etf = etf.dropna()
    proxy = proxy.dropna()
    if etf.empty:
        return proxy
    inception = etf.index[0]
    proxy_pre = proxy.loc[:inception]
    if proxy_pre.empty:
        return etf
    proxy_ret = proxy_pre.pct_change().dropna() - ter_daily
    etf_ret = etf.pct_change().dropna()
    # build a spliced price starting at 1.0 on the first proxy date
    combined_ret = pd.concat([proxy_ret, etf_ret[etf_ret.index > inception]])
    combined_ret = combined_ret.sort_index()
    price = (1.0 + combined_ret).cumprod()
    # rescale so the level matches the real ETF at inception (cosmetic)
    if inception in price.index:
        scale = etf.loc[inception] / price.loc[inception] if price.loc[inception] else 1.0
        price = price * scale
    return price


def load(
    cfg: Config,
    universe: Universe,
    price_source: str,
    macro_source: str,
    on_missing_history: str = "clamp",
) -> LoadedData:
    """Load prices + macro for the configured universe and date window."""
    start = cfg.dates["start"]
    end = cfg.dates["end"]
    req_start = dt.date.fromisoformat(start)

    tickers = universe.tickers(include_benchmark=True)
    manifest: list[dict] = []
    effective_start = start

    # --- decide clamp vs proxy based on inception dates ------------------
    core = universe.core_tickers()
    latest_inc = universe.latest_inception(core)
    if on_missing_history == "clamp" and latest_inc and latest_inc > req_start:
        effective_start = max(latest_inc, req_start).isoformat()
        manifest.append(
            {
                "action": "clamp",
                "detail": f"start clamped to {effective_start} (latest core ETF inception)",
            }
        )

    psrc = make_price_source(price_source)
    fetch_start = "1990-01-01" if on_missing_history == "proxy" else effective_start
    prices = psrc.history(tickers, fetch_start, end)

    # --- proxy-splice tickers that launched after the requested start ----
    if on_missing_history == "proxy":
        for t in list(prices.columns):
            inc = universe.inception.get(t)
            proxy = universe.proxy_for(t)
            if inc and inc > req_start and proxy:
                try:
                    proxy_px = psrc.history([proxy], fetch_start, end)[proxy]
                    spliced = _return_splice(proxy_px, prices[t])
                    prices[t] = spliced
                    manifest.append(
                        {
                            "action": "proxy-splice",
                            "ticker": t,
                            "proxy": proxy,
                            "detail": f"{t} extended before {inc} using {proxy} returns",
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    manifest.append(
                        {"action": "proxy-failed", "ticker": t, "detail": str(exc)}
                    )
        lower = start
    else:
        lower = effective_start
    # keep ~1y of history before the trading window so the inverse-vol lookback
    # and the first rebalance have data (the engine still trades only from `start`).
    buffer_start = (dt.date.fromisoformat(lower) - dt.timedelta(days=400)).isoformat()
    prices = prices.loc[buffer_start:end]

    prices = prices.dropna(how="all").sort_index()

    # --- macro series ----------------------------------------------------
    msrc = make_macro_source(macro_source)
    sig = cfg.signals
    wanted = {
        sig["money_series"],
        sig["credit_series"],
        sig["credit_spread_series"],
        sig["growth_series"],
        sig.get("cfnai_series", "CFNAI"),
        sig["riskfree_series"],
    }
    macro: dict[str, pd.Series] = {}
    macro_start = "2000-01-01"  # need history for YoY/lookbacks before backtest start
    for sid in sorted(wanted):
        try:
            macro[sid] = msrc.series(sid, macro_start, end)
        except Exception as exc:  # noqa: BLE001
            print(f"[macro] warning: failed to load {sid}: {exc}")

    return LoadedData(
        prices=prices, macro=macro, splice_manifest=manifest, effective_start=effective_start
    )
