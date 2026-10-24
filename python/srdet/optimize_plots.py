"""Figures of an optimisation run: convergence, per-parameter sensitivity, Pareto front."""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from .plotting import COLORS, _save, plt


def _stage_color(stage: str) -> str:
    s = str(stage)
    if s.startswith("final"):
        return "#d62728"
    if s.startswith("r"):
        return "#2ca02c"
    try:
        return COLORS[int(s[1:]) % len(COLORS)]
    except ValueError:
        return "0.5"


def convergence(df: pd.DataFrame, path: Path, maximize: bool, spec: dict) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    obj = pd.to_numeric(df["objective"], errors="coerce")
    feas = df["feasible"].astype(bool)
    def group(stage: str) -> str:
        s = str(stage)
        return "refine" if s.startswith("r") else "validation" if s.startswith("final") else s

    for g, grp in df.groupby(df["stage"].map(group), sort=False):
        f = grp["feasible"].astype(bool)
        y = pd.to_numeric(grp["objective"], errors="coerce")
        ev = sorted(set(int(e) for e in grp["events"]))
        label = {"refine": "refinement", "validation": "validation (repeats)"}.get(g, f"screening {g}")
        ax.scatter(grp["trial"][f], y[f], s=22, color=_stage_color(grp["stage"].iloc[0]),
                   label=f"{label}, {'/'.join(map(str, ev))} events")
        ax.scatter(grp["trial"][~f], y[~f], s=22, marker="x", color=_stage_color(grp["stage"].iloc[0]), alpha=0.5)
    best = (obj.where(feas).cummax() if maximize else obj.where(feas).cummin()).ffill()
    ax.plot(df["trial"], best, color="k", lw=1.2, label="best feasible so far")
    ax.set(xlabel="Trial", ylabel=f"Objective: {spec['objective']['expr']}",
           title=f"Convergence — {spec.get('title', spec['name'])}")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8)
    ax.text(0.01, 0.01, "× = infeasible (constraint violated)", transform=ax.transAxes, fontsize=7, color="0.4")
    return _save(fig, path)


def sensitivity(df: pd.DataFrame, params, out: Path, spec: dict) -> list[Path]:
    """Objective versus every free parameter (screening + refinement trials)."""
    d = df[df["feasible"].astype(bool) & ~df["stage"].astype(str).str.startswith("final")]
    if not len(d):
        return []
    n = len(params)
    ncol = min(3, n)
    nrow = math.ceil(n / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(5.2 * ncol, 3.9 * nrow), squeeze=False)
    y = pd.to_numeric(d["objective"], errors="coerce")
    for i, p in enumerate(params):
        ax = axes[i // ncol][i % ncol]
        if p.kind == "choice":
            groups = [y[d[p.alias].astype(str) == str(v)].dropna() for v in p.values]
            ax.boxplot([g if len(g) else [np.nan] for g in groups], tick_labels=[str(v) for v in p.values])
            for j, g in enumerate(groups):
                ax.scatter(np.full(len(g), j + 1) + np.random.default_rng(j).uniform(-0.12, 0.12, len(g)), g,
                           s=10, alpha=0.6, color=COLORS[j % len(COLORS)])
            ax.tick_params(axis="x", rotation=30)
        else:
            x = pd.to_numeric(d[p.alias], errors="coerce")
            sc = ax.scatter(x, y, c=d["events"], cmap="viridis", s=18, norm=mcolors.LogNorm())
            if p.log:
                ax.set_xscale("log")
                ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
                ax.xaxis.set_minor_formatter(mticker.NullFormatter())
            unit = {"length": " [mm]", "energy": " [keV]", "angle": " [deg]"}.get(p.unit_kind or "", "")
            ax.set_xlabel(f"{p.alias}{unit}" + (f"  ({p.path})" if p.path else "  (virtual)"))
        ax.set_ylabel("objective")
        if p.kind == "choice":
            ax.set_xlabel(f"{p.alias}  ({p.path})")
    for k in range(n, nrow * ncol):
        axes[k // ncol][k % ncol].set_visible(False)
    if any(p.kind != "choice" for p in params):
        fig.colorbar(sc, ax=axes.ravel().tolist(), label="events per trial", shrink=0.6)
    fig.suptitle(f"Sensitivity of the objective — {spec.get('title', spec['name'])}")
    return [_save(fig, out / "sensitivity.png")]


def pareto(df: pd.DataFrame, par: dict, path: Path, spec: dict, params) -> tuple[Path, pd.DataFrame]:
    """Non-dominated feasible candidates in (x, y); each candidate counted at its highest statistics."""
    x, y = par["x"], par["y"]
    sx = 1 if par.get("x_dir", "min") == "min" else -1
    sy = 1 if par.get("y_dir", "max") == "min" else -1
    aliases = [p.alias for p in params]
    d = df[df["feasible"].astype(bool)].copy()
    if x not in d or y not in d or not len(d):
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, f"no feasible trials with {x} and {y}", ha="center", transform=ax.transAxes)
        return _save(fig, path), pd.DataFrame()
    d["_key"] = d[aliases].astype(str).agg("|".join, axis=1)
    d = d.sort_values("events").groupby("_key").tail(1)
    d[x] = pd.to_numeric(d[x], errors="coerce")
    d[y] = pd.to_numeric(d[y], errors="coerce")
    d = d.dropna(subset=[x, y])
    pts = d[[x, y]].to_numpy() * np.array([sx, sy])
    dominated = np.array([np.any(np.all(pts <= p, axis=1) & np.any(pts < p, axis=1)) for p in pts])
    front = d[~dominated].sort_values(x)
    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.scatter(d[x], d[y], s=18, color="0.6", label="feasible candidates")
    ax.plot(front[x], front[y], "o-", color="#d62728", label="Pareto front")
    for _, r in front.iterrows():
        lab = ", ".join(f"{a}={r[a]:.3g}" if isinstance(r[a], float) else f"{a}={r[a]}" for a in aliases)
        ax.annotate(lab, (r[x], r[y]), fontsize=6.5, xytext=(4, 4), textcoords="offset points")
    ax.set(xlabel=f"{x} ({'lower' if sx > 0 else 'higher'} is better)",
           ylabel=f"{y} ({'lower' if sy > 0 else 'higher'} is better)",
           title=f"Pareto front — {spec.get('title', spec['name'])}")
    ax.legend()
    cols = aliases + [x, y, "objective", "events"]
    return _save(fig, path), front[[c for c in cols if c in front]]
