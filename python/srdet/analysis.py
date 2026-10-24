"""Read a run folder and compute physics metrics.

All photon numbers are reported "physical", i.e. divided by materials.yield_scale
(a scaled yield only changes the statistics, not the means). Errors are standard errors.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import catalog

FIRST_PROC = {0: "none", 1: "phot", 2: "compt", 3: "Rayl", 4: "conv", 5: "other"}
FATES = ["n_det", "n_abs_bulk", "n_abs_surface", "n_norindex", "n_escaped", "n_lost_other"]
FATE_LABELS = {"n_det": "detected", "n_abs_bulk": "absorbed in bulk", "n_abs_surface": "absorbed on surface",
               "n_norindex": "lost into non-optical material", "n_escaped": "escaped world", "n_lost_other": "other"}
OP_CLASSES = ["op_fresnel_refl", "op_tir", "op_lambert", "op_spike_lobe", "op_lut_refl", "op_refraction",
              "op_surf_abs", "op_detection", "op_norindex"]
OP_LABELS = {"op_fresnel_refl": "Fresnel reflection", "op_tir": "total internal refl.",
             "op_lambert": "Lambertian refl.", "op_spike_lobe": "specular spike/lobe",
             "op_lut_refl": "LUT/coated refl.", "op_refraction": "refraction/transmission",
             "op_surf_abs": "surface absorption", "op_detection": "detection", "op_norindex": "no RINDEX kill"}
PROCS = ["n_phot", "n_compt", "n_rayl", "n_conv", "n_eioni", "n_ebrem", "n_annihil", "n_msc"]
K_ALPHA = {"I": 28.612, "Cs": 30.973, "Pb": 74.969, "Bi": 77.108, "Gd": 42.996, "Lu": 54.070}


@dataclass
class Run:
    path: Path
    cfg: dict
    geom: dict
    mats: dict
    summary: dict
    meta: dict
    events: pd.DataFrame
    photons: pd.DataFrame | None = None
    hists: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.meta.get("name") or self.path.name

    @property
    def yield_scale(self) -> float:
        return float(self.cfg.get("materials", {}).get("yield_scale", 1.0)) or 1.0

    @property
    def optical_gun(self) -> bool:
        return self.cfg.get("beam", {}).get("type") == "optical"


def _json(p: Path) -> dict:
    return json.loads(p.read_text()) if p.exists() else {}


def load_run(path: str | Path, with_photons: bool = True) -> Run:
    import uproot

    path = Path(path)
    cfg = yaml.safe_load((path / "config.yaml").read_text()) if (path / "config.yaml").exists() else {}
    f = uproot.open(path / "srdet.root")
    events = f["events"].arrays(library="pd")
    photons = None
    if with_photons and "photons" in f and f["photons"].num_entries > 0:
        photons = f["photons"].arrays(library="pd")
    hists = {}
    for key, cls in f.classnames().items():
        if cls.startswith("TH1") or cls.startswith("TH2"):
            hists[key.split(";")[0]] = f[key]
    return Run(path, cfg, _json(path / "geometry.json"), _json(path / "materials.json"),
               _json(path / "run_summary.json"), _json(path / "meta.json"), events, photons, hists)


def _frac(k: float, n: float) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    p = k / n
    return p, math.sqrt(max(p * (1 - p), 1.0 / n) / n)


def _mean(x: pd.Series) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return float("nan"), float("nan")
    return float(x.mean()), float(x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else 0.0


def photopeak_mask(ev: pd.DataFrame, e0: float) -> np.ndarray:
    """Events depositing (almost) the full energy in the detector."""
    return np.abs(ev["edep_total_keV"].to_numpy() - e0) < max(0.5, 0.01 * e0)


def gauss_peak(x: np.ndarray) -> tuple[float, float]:
    """Mean and sigma of the main peak: iterative 2-sigma truncated estimate (robust to tails)."""
    x = np.asarray(x, dtype=float)
    if len(x) < 5:
        return float("nan"), float("nan")
    mu, s = np.median(x), x.std()
    for _ in range(10):
        sel = x[np.abs(x - mu) < 2 * max(s, 1e-9)]
        if len(sel) < 5:
            break
        mu, s = sel.mean(), sel.std() / 0.8796  # correct the truncation of a 2-sigma window
    return float(mu), float(s)


def metrics(run: Run) -> dict:
    ev = run.events
    n = len(ev)
    ys = run.yield_scale
    m: dict = {"name": run.name, "events": n, "yield_scale": ys}
    if n == 0:
        return m
    e0 = float(ev["e0_keV"].mean())
    m["e0_keV"] = e0
    mono = bool(ev["e0_keV"].std() < 1e-6 * max(e0, 1e-9))
    produced = ev["n_scint"] + ev["n_cher"]

    if run.optical_gun:
        n_gun = int(run.cfg["beam"]["optical"]["n"])
        total = n * n_gun
        m["lce"], m["lce_err"] = _frac(ev["n_det"].sum(), total)
        m["lce_exit"], m["lce_exit_err"] = _frac(ev["n_exit"].sum(), total)
        m["photons_per_event"] = n_gun
        for f in FATES:
            m[f"fate_{f}"] = ev[f].sum() / total
    else:
        m["interacting_fraction"], m["interacting_fraction_err"] = _frac((ev["first_proc"] != 0).sum(), n)
        dep = ev["edep_core_keV"] > 0.5
        m["detection_efficiency"], m["detection_efficiency_err"] = _frac(dep.sum(), n)
        if mono and e0 > 0:
            pk = photopeak_mask(ev, e0)
            m["photopeak_fraction"], m["photopeak_fraction_err"] = _frac(pk.sum(), n)
            ph = ev["first_proc"] == 1
            m["k_escape_fraction"], m["k_escape_fraction_err"] = _frac((ev["n_fluo_escape"][ph] > 0).sum(), ph.sum())
        m["mean_edep_core_keV"], m["mean_edep_core_keV_err"] = _mean(ev["edep_core_keV"])
        m["mean_edep_wall_keV"] = float(ev["edep_wall_keV"].mean())
        m["mean_edep_coating_keV"] = float(ev["edep_coating_keV"].mean())
        m["mean_edep_sensor_keV"] = float(ev["edep_sensor_keV"].mean())
        m["core_energy_fraction"] = float(ev["edep_core_keV"].sum() / max(ev["edep_total_keV"].sum(), 1e-12))
        m["mean_n_scint"] = float(ev["n_scint"].mean() / ys)
        m["mean_n_cher"] = float(ev["n_cher"].mean() / ys)
        m["mean_n_det"], err = _mean(ev["n_det"] / ys)
        m["mean_n_det_err"] = err
        edep_sum = ev["edep_core_keV"].sum()
        if edep_sum > 0:
            m["scint_yield_per_keV"] = float(ev["n_scint"].sum() / edep_sum / ys)
            m["det_yield_per_keV"] = float(ev["n_det"].sum() / edep_sum / ys)
        if produced.sum() > 0:
            m["lce"], m["lce_err"] = _frac(ev["n_det"].sum(), produced.sum())
            m["lce_exit"], m["lce_exit_err"] = _frac(ev["n_exit"].sum(), produced.sum())
            for f in FATES:
                m[f"fate_{f}"] = float(ev[f].sum() / produced.sum())
        if mono and e0 > 0:
            pk = photopeak_mask(ev, e0)
            if pk.sum() >= 20 and ev["n_det"][pk].mean() > 0:
                mu, s = gauss_peak(ev["n_det"][pk].to_numpy())
                m["resolution_fwhm_scaled"] = 2.3548 * s / mu if mu > 0 else float("nan")
                # Poisson limit for the physical (unscaled) light yield
                m["resolution_fwhm_poisson_limit"] = 2.3548 / math.sqrt(mu / ys) if mu > 0 else float("nan")
        hit = (ev["edep_core_keV"] > 0) & (ev["first_cell"] >= 0)
        if hit.sum() > 0:
            m["em_crosstalk"] = float(1 - (ev["edep_first_cell_keV"][hit] / ev["edep_core_keV"][hit]).mean())
            m["mean_cells_hit"] = float(ev["n_cells_hit"][ev["edep_core_keV"] > 0].mean())
        fp = ev["first_proc"].value_counts()
        for code, label in FIRST_PROC.items():
            m[f"first_{label}"] = float(fp.get(code, 0) / n)
        for p in PROCS:
            m[f"mean_{p}"] = float(ev[p].mean())
        m["mean_n_fluo"] = float(ev["n_fluo"].mean())
        m["fluo_escape_per_event"] = float(ev["n_fluo_escape"].mean())
        if not run.cfg.get("physics", {}).get("radioactive") and e0 > 0:
            bal = (ev["e0_keV"] - ev["edep_total_keV"] - ev["e_escape_keV"]) / ev["e0_keV"]
            m["energy_balance_max_rel"] = float(np.abs(bal).max())
            m["energy_balance_mean_rel"] = float(bal.mean())

    det = ev["n_det"].sum()
    if det > 0:
        m["optical_crosstalk"] = float(ev["det_other_cell"].sum() / det)
    c = ev["coat_refl"].sum() + ev["coat_abs"].sum() + ev["coat_trans"].sum()
    if c > 0:
        m["coat_refl_prob"] = float(ev["coat_refl"].sum() / c)
        m["coat_abs_prob"] = float(ev["coat_abs"].sum() / c)
        m["coat_trans_prob"] = float(ev["coat_trans"].sum() / c)
    for k in OP_CLASSES:
        m[f"mean_{k}"] = float(ev[k].mean() / ys) if not run.optical_gun else float(ev[k].mean())
    h = run.hists.get("nrefl_det")
    if h is not None:
        v, e = h.to_numpy()
        if v.sum() > 0:
            m["mean_refl_det"] = float((v * 0.5 * (e[1:] + e[:-1])).sum() / v.sum())
    h = run.hists.get("t_det")
    if h is not None:
        v, e = h.to_numpy()
        if v.sum() > 0:
            c = np.cumsum(v) / v.sum()
            m["t_det_median_ns"] = float(np.interp(0.5, c, e[1:]))

    # point-spread of the detected light around the cell of the first interaction
    # (needs run.photon_fraction > 0); for the optical gun the photons start in the central cell
    if run.photons is not None and len(run.photons) and run.geom.get("cells"):
        cells = np.array(run.geom["cells"], dtype=float)
        ph = run.photons
        if run.optical_gun:
            c = int(run.geom.get("central_cell", 0))
            cx, cy = np.full(len(ph), cells[c, 2]), np.full(len(ph), cells[c, 3])
            ok = np.ones(len(ph), bool)
        else:
            fc = ph["evt"].map(ev.set_index("evt")["first_cell"]).fillna(-1).astype(int).to_numpy()
            ok = fc >= 0
            cx, cy = cells[np.clip(fc, 0, None), 2], cells[np.clip(fc, 0, None), 3]
        if ok.sum() > 10:
            r = np.hypot(ph["x_mm"].to_numpy() - cx, ph["y_mm"].to_numpy() - cy)[ok]
            m["psf_r50_um"] = float(np.median(r) * 1000)
            m["psf_r90_um"] = float(np.quantile(r, 0.9) * 1000)
            m["psf_in_cell_fraction"] = float((r < 0.5 * float(run.geom.get("pitch_mm", 0.2))).mean())

    # photodetector price / performance (see docs/physics.md)
    sensor = run.geom.get("sensor") or run.cfg.get("geometry", {}).get("sensor")
    if sensor in catalog.SENSORS and "det_yield_per_keV" in m:
        _, ff, pix, noise, cost = catalog.SENSORS[sensor]
        pitch = float(run.geom.get("pitch_mm", 0.2))
        npix = max(1.0, (pitch / pix) ** 2)
        s = m["det_yield_per_keV"] * 60.0
        m["snr_60keV_per_channel"] = s / math.sqrt(s + npix * noise ** 2) if s > 0 else 0.0
        m["relative_cost"] = cost
        m["det_yield_per_cost"] = m["det_yield_per_keV"] / cost if cost > 0 else float("inf")
    m["wall_time_s"] = run.meta.get("wall_time_s", run.summary.get("wall_time_s"))
    m["geometry_fill_factor"] = run.geom.get("core_fill_factor")
    m["n_cells"] = run.geom.get("n_cells")
    return m


def sanity(run: Run, m: dict) -> list[str]:
    """Checks that flag clearly unphysical output (used to mark a run as failed)."""
    problems = []
    if "energy_balance_max_rel" in m and m["energy_balance_max_rel"] > 1e-3:
        problems.append(f"energy not conserved: max |E0 - Edep - Eescape|/E0 = {m['energy_balance_max_rel']:.2e}")
    if m.get("lce", 0) > 1 + 1e-9:
        problems.append(f"light collection efficiency > 1 ({m['lce']})")
    if (run.events["edep_total_keV"] > run.events["e0_keV"] * (1 + 1e-6) + 1e-3).any() and \
            not run.cfg.get("physics", {}).get("radioactive"):
        problems.append("event with deposited energy > primary energy")
    sy = m.get("scint_yield_per_keV")
    core = run.cfg.get("geometry", {}).get("core_material")
    if sy and core in catalog.SCINTILLATORS and run.cfg.get("physics", {}).get("optical", {}).get("scintillation"):
        expected = catalog.SCINTILLATORS[core][0] / 1000
        if not (0.5 * expected < sy < 1.05 * expected):  # Birks quenching only lowers the yield
            problems.append(f"scintillation yield {sy:.1f}/keV far from catalogue {expected:.1f}/keV")
    return problems


def analyze_run(path: str | Path, plots: bool = True) -> dict:
    run = load_run(path)
    m = metrics(run)
    m["sanity_problems"] = sanity(run, m)
    (run.path / "metrics.json").write_text(json.dumps(m, indent=2, default=float))
    if plots:
        from .plotting import run_plots
        run_plots(run, m)
    if m["sanity_problems"]:
        raise RuntimeError("; ".join(m["sanity_problems"]))
    return m
