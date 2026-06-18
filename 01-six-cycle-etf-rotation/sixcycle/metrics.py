"""Performance metrics: Sharpe, CAGR, vol, max drawdown, Calmar, turnover,
monthly win-rate vs benchmarks. Annualisation factor 252.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return np.nan
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return np.nan
    return (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0


def ann_vol(returns: pd.Series, ann: int = 252) -> float:
    return float(returns.std() * np.sqrt(ann))


def sharpe(returns: pd.Series, rf_daily: pd.Series | None = None, ann: int = 252) -> float:
    excess = returns if rf_daily is None else returns - rf_daily.reindex(returns.index).fillna(0.0)
    sd = excess.std()
    if sd == 0 or np.isnan(sd):
        return np.nan
    return float(excess.mean() / sd * np.sqrt(ann))


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def calmar(equity: pd.Series) -> float:
    mdd = abs(max_drawdown(equity))
    c = cagr(equity)
    return float(c / mdd) if mdd > 0 else np.nan


def annual_turnover(turnover: pd.Series) -> float:
    """Average per-year sum of one-way turnover fractions."""
    if turnover.empty:
        return np.nan
    by_year = turnover.groupby(turnover.index.year).sum()
    return float(by_year.mean())


def monthly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).resample("ME").prod() - 1.0


def monthly_win_rate(returns: pd.Series, bench_returns: pd.Series) -> float:
    a = monthly_returns(returns)
    b = monthly_returns(bench_returns).reindex(a.index)
    valid = a.notna() & b.notna()
    if valid.sum() == 0:
        return np.nan
    return float((a[valid] > b[valid]).mean())


def summarize(result, rf_daily=None, benchmarks: dict[str, pd.Series] | None = None, ann: int = 252) -> dict:
    """Compute the full metric set for one BacktestResult."""
    r, eq = result.returns, result.equity
    row = {
        "CAGR": cagr(eq),
        "AnnVol": ann_vol(r, ann),
        "Sharpe": sharpe(r, rf_daily, ann),
        "MaxDD": max_drawdown(eq),
        "Calmar": calmar(eq),
        "AnnTurnover": annual_turnover(result.turnover),
    }
    if benchmarks:
        for bname, bret in benchmarks.items():
            row[f"WinRate_vs_{bname}"] = monthly_win_rate(r, bret)
    return row


def metrics_table(results: dict, rf_daily=None, benchmarks=None, ann: int = 252) -> pd.DataFrame:
    rows = {name: summarize(res, rf_daily, benchmarks, ann) for name, res in results.items()}
    return pd.DataFrame(rows).T
