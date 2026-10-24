"""Beam energy spectra: radionuclide lines, an approximate X-ray tube model and user files.

Spectra are returned as (energies_keV, weights). Line spectra are converted to a GPS
user histogram with narrow bins (see macro.py).
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .paths import repo_root

# Main photon lines (keV, emission probability per decay), rounded values from the
# NNDC / LNHB decay data tables. Low-energy L X-rays are omitted.
NUCLIDES: dict[str, list[tuple[float, float]]] = {
    "Fe55": [(5.888, 0.0845), (5.899, 0.166), (6.490, 0.0340)],
    "Cd109": [(21.990, 0.293), (22.163, 0.553), (24.94, 0.176), (88.0336, 0.0366)],
    "Am241": [(26.3446, 0.0227), (59.5409, 0.359)],
    "Co57": [(14.4129, 0.0916), (122.0607, 0.856), (136.4736, 0.1068)],
    "Ba133": [(30.625, 0.34), (30.973, 0.627), (35.0, 0.23), (80.9979, 0.329), (276.3989, 0.0716),
              (302.8508, 0.1834), (356.0129, 0.6205), (383.8485, 0.0894)],
    "Cs137": [(31.817, 0.0199), (32.194, 0.0364), (36.4, 0.0105), (661.657, 0.851)],
    "Na22": [(511.0, 1.80), (1274.537, 0.9994)],
    "Co60": [(1173.228, 0.9985), (1332.492, 0.9998)],
}

# Tungsten K lines (keV, relative intensity) and K edge
W_K_LINES = [(57.981, 0.58), (59.318, 1.0), (67.244, 0.22), (69.10, 0.08)]
W_K_EDGE = 69.525


def _xcom(name: str) -> tuple[np.ndarray, np.ndarray]:
    path = repo_root() / "tests" / "data" / f"xcom_{name}.csv"
    rows = [r for r in csv.reader(l for l in path.read_text().splitlines() if not l.startswith("#"))][1:]
    a = np.array(rows, dtype=float)
    return a[:, 0] * 1e3, a[:, 6]  # keV, total attenuation with coherent (cm2/g)


def mu_rho(name: str, e_kev: np.ndarray) -> np.ndarray:
    """Log-log interpolation of the XCOM total attenuation (cm2/g). Absorption edges are listed
    twice (below / above); searchsorted(side='right') picks the correct side of the edge."""
    e, mu = _xcom(name)
    x = np.atleast_1d(np.asarray(e_kev, dtype=float))
    i = np.clip(np.searchsorted(e, x, side="right"), 1, len(e) - 1)
    f = np.log(x / e[i - 1]) / np.log(e[i] / e[i - 1])
    return np.exp(np.log(mu[i - 1]) + f * (np.log(mu[i]) - np.log(mu[i - 1])))


def xray_tube(kvp: float, filter_mm_al: float = 2.5, step_kev: float = 0.5, char_fraction: float = 0.10):
    """Approximate W-anode spectrum: Kramers continuum dN/dE ~ (E0 - E)/E, W K lines above the
    K edge (char_fraction of the photons), filtered by `filter_mm_al` of aluminium.
    Good enough for relative studies; use a measured / SpekPy spectrum (file) for absolute work."""
    e = np.arange(step_kev, kvp, step_kev) + step_kev / 2
    w = np.clip((kvp - e) / e, 0, None)
    w /= w.sum()
    if kvp > W_K_EDGE:
        frac = char_fraction * min(1.0, (kvp - W_K_EDGE) / 30.0)
        lines = np.array(W_K_LINES)
        for el, rel in lines:
            i = int(np.argmin(np.abs(e - el)))
            w[i] += frac * rel / lines[:, 1].sum()
    w *= np.exp(-mu_rho("Al", e) * 2.699 * filter_mm_al / 10.0)
    keep = w > w.max() * 1e-6
    return e[keep], w[keep] / w[keep].sum()


def from_file(path: str | Path):
    """Two columns: energy [keV], weight. '#' comments allowed."""
    data = np.loadtxt(path, comments="#", delimiter=None if str(path).endswith(".txt") else ",")
    return data[:, 0], data[:, 1]


def resolve(spec: dict | None):
    """Return ('lines', E, w) or ('hist', E, w) or None for a mono-energetic beam."""
    if not spec:
        return None
    if "lines" in spec:
        a = np.array(spec["lines"], dtype=float)
        return "lines", a[:, 0], a[:, 1]
    if "source" in spec:
        a = np.array(NUCLIDES[spec["source"]])
        return "lines", a[:, 0], a[:, 1]
    if "xray_tube" in spec:
        t = spec["xray_tube"]
        from .config import quantity
        e, w = xray_tube(float(t.get("kvp", 80)), quantity(t.get("filter", "2.5 mm"), "length"),
                         float(t.get("step_keV", 0.5)))
        return "hist", e, w
    if "file" in spec:
        e, w = from_file(spec["file"])
        return "hist", e, w
    raise ValueError(f"unknown spectrum spec {spec}")
