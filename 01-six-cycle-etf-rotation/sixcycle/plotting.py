"""Matplotlib plots for the report (headless 'Agg' backend)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .classifier import STAGE_NAMES  # noqa: E402
from .metrics import drawdown_series  # noqa: E402

_STAGE_COLORS = {
    1: "#2ca02c", 2: "#98df8a", 3: "#1f77b4",
    4: "#aec7e8", 5: "#d62728", 6: "#ff9896",
}


def plot_equity(results: dict, out: Path, logy: bool = True) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6))
    for name, res in results.items():
        ax.plot(res.equity.index, res.equity.values, label=name, linewidth=1.4)
    ax.set_title("Equity Curves — Six-Cycle US Analog")
    ax.set_ylabel("Growth of $1")
    if logy:
        ax.set_yscale("log")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_drawdown(results: dict, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(11, 5))
    for name, res in results.items():
        dd = drawdown_series(res.equity)
        ax.plot(dd.index, dd.values * 100, label=name, linewidth=1.1)
    ax.set_title("Drawdown (%)")
    ax.set_ylabel("Drawdown %")
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_regime(stages: pd.Series, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(11, 4))
    s = stages.dropna()
    ax.step(s.index, s.values, where="post", color="black", linewidth=0.9)
    # shade by stage
    vals = s.values
    idx = s.index
    start = 0
    for i in range(1, len(vals) + 1):
        if i == len(vals) or vals[i] != vals[start]:
            stg = int(vals[start])
            ax.axvspan(idx[start], idx[min(i, len(idx) - 1)],
                       color=_STAGE_COLORS.get(stg, "gray"), alpha=0.25)
            start = i
    ax.set_yticks(list(STAGE_NAMES.keys()))
    ax.set_yticklabels([f"{k}:{v}" for k, v in STAGE_NAMES.items()], fontsize=8)
    ax.set_title("Six-Cycle Regime Timeline (point-in-time classifier)")
    ax.set_ylim(0.5, 6.5)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_signals(transformed: pd.DataFrame, signals: pd.DataFrame, out: Path) -> Path:
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    cols = list(transformed.columns)
    titles = ["Money (short-rate change; <0 = easing)",
              "Credit (loan pulse; >0 = expansion)",
              "Growth (momentum; >0 = accelerating)"]
    for ax, col, title in zip(axes, cols, titles):
        ax.plot(transformed.index, transformed[col].values, color="#1f77b4", linewidth=1.0)
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set_title(f"{title}", fontsize=10)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Macro signal inputs (monthly, point-in-time)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_weights(result, out: Path) -> Path:
    """Stacked-area of a strategy's asset weights over time."""
    w = result.weights.copy()
    w = w.loc[:, (w.abs().sum() > 1e-6)]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.stackplot(w.index, [w[c].clip(lower=0).values for c in w.columns], labels=list(w.columns))
    ax.set_title(f"Asset weights over time — {result.name}")
    ax.set_ylabel("Weight")
    ax.legend(loc="upper left", fontsize=8, ncol=4)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out
