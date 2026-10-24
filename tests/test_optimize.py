"""Optimiser tests with a synthetic evaluator (no Geant4): known optimum, noise that shrinks with
statistics, constraints, derived parameters, invalid geometry, resume and reporting."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
import yaml

from srdet import config as C
from srdet.optimize import Optimizer, geometry_problem, parse_space, sample, spec_files, load_spec


def fake_physics(cfg: dict, name: str, parent) -> dict:
    """Light yield peaks at L = 2 mm, Ag is 3x better than Al; detection efficiency drops with
    wall thickness (fill factor); noise ~ 1/sqrt(events)."""
    g = cfg["geometry"]
    L = C.quantity(g["length"], "length")
    pitch = C.quantity(g["pitch"], "length")
    d = C.quantity(g["channel_diameter"], "length")
    coat = cfg["optics"]["coating"]
    n = cfg["run"]["events"]
    rng = np.random.default_rng(cfg["run"]["seed"])
    ly = (3.0 if coat == "Ag" else 1.0) * math.exp(-math.log(L / 2.0) ** 2)
    fill = (math.pi * d * d / 4) / (math.sqrt(3) / 2 * pitch * pitch)
    return {"det_yield_per_keV": ly * (1 + rng.normal(0, 1) / math.sqrt(n)),
            "detection_efficiency": fill, "psf_r50_um": 50 + 2000 * (pitch - d)}


SPEC = {
    "name": "T_fake",
    "base": "unit_xray.yaml",
    "space": {"L": {"path": "geometry.length", "low": "0.5 mm", "high": "10 mm", "log": True},
              "wall": {"low": "2 um", "high": "80 um"},
              "coat": {"path": "optics.coating", "values": ["Al", "Ag"]}},
    "derived": {"geometry.pitch": {"expr": "0.2 + 2*0.002 + wall", "unit": "mm"}},
    "objective": {"expr": "det_yield_per_keV * detection_efficiency"},
    "constraints": ["detection_efficiency >= 0.6"],
    "pareto": {"x": "psf_r50_um", "x_dir": "min", "y": "det_yield_per_keV", "y_dir": "max"},
    "search": {"sampler": "lhs", "initial": 24, "events": [100, 1000, 10000], "eta": 3,
               "refine": {"iterations": 5, "events": 10000, "step": 0.15, "min_gain": 0.01},
               "final": {"top": 2, "events": 20000, "repeats": 3}, "seed": 3},
}


def test_space_and_sampling():
    params = parse_space(SPEC["space"])
    assert params[0].unit_kind == "length" and params[0].low == pytest.approx(0.5)
    pts = sample(params, 30, "lhs", np.random.default_rng(0))
    L = np.array([p["L"] for p in pts])
    assert L.min() >= 0.5 and L.max() <= 10
    assert {p["coat"] for p in pts} == {"Al", "Ag"}
    # LHS inside every category: one point per stratum of the (log) range
    for coat in ("Al", "Ag"):
        u = np.sort([params[0].to_unit(p["L"]) for p in pts if p["coat"] == coat])
        assert np.all(np.floor(u * len(u)) == np.arange(len(u)))
    grid = sample(params, 0, "grid", np.random.default_rng(0))
    assert len(grid) == 3 * 3 * 2


def test_geometry_guard():
    cfg = C.load("unit_xray.yaml")
    cfg["geometry"]["pitch"] = "0.203 mm"  # 0.2 + 2*0.002 = 0.204 > pitch
    assert "wall" in geometry_problem(cfg)
    cfg["geometry"]["pitch"] = "0.21 mm"
    assert geometry_problem(cfg) == ""


def test_finds_known_optimum(tmp_path):
    opt = Optimizer(SPEC, evaluator=fake_physics, out_dir=tmp_path / "opt")
    out = opt.run()
    final = pd.read_csv(out / "final.csv")
    best = final.iloc[0]
    assert best["coat"] == "Ag"
    assert abs(math.log(best["L"] / 2.0)) < 0.35          # true optimum L = 2 mm
    assert best["wall"] < 0.02                             # thin walls maximise the fill factor
    assert best["detection_efficiency"] >= 0.6
    trials = pd.read_csv(out / "trials.csv")
    assert set(trials["stage"]) >= {"s0", "s1", "s2", "final0"}
    assert (trials.groupby("stage")["events"].nunique() == 1).all()
    for f in ["report.md", "best.yaml", "plots/convergence.png", "plots/sensitivity.png", "plots/pareto.png"]:
        assert (out / f).exists(), f
    best_cfg = yaml.safe_load((out / "best.yaml").read_text())
    assert best_cfg["extends"] == "unit_xray.yaml" and best_cfg["optics"]["coating"] == "Ag"
    assert C.load(out / "best.yaml")["geometry"]["pitch"].endswith("mm")


def test_constraints_mark_infeasible(tmp_path):
    spec = dict(SPEC, constraints=["detection_efficiency >= 0.99"],
                search=dict(SPEC["search"], initial=6, events=[100], refine=None, final=None))
    opt = Optimizer(spec, evaluator=fake_physics, out_dir=tmp_path / "opt")
    opt.run()
    trials = pd.read_csv(opt.dir / "trials.csv")
    assert not trials["feasible"].any()
    assert trials["violations"].str.contains("detection_efficiency").all()


def test_invalid_geometry_is_skipped_not_simulated(tmp_path):
    calls = []

    def ev(cfg, name, parent):
        calls.append(name)
        return fake_physics(cfg, name, parent)

    spec = dict(SPEC, space=dict(SPEC["space"], wall={"low": "-20 um", "high": "10 um"}),
                search=dict(SPEC["search"], initial=8, events=[100], refine=None, final=None))
    opt = Optimizer(spec, evaluator=ev, out_dir=tmp_path / "opt")
    opt.run()
    trials = pd.read_csv(opt.dir / "trials.csv")
    bad = trials["violations"].astype(str).str.startswith("invalid geometry")
    assert bad.any() and len(calls) == (~bad).sum()


def test_resume_reuses_trials(tmp_path):
    calls = []

    def ev(cfg, name, parent):
        calls.append(name)
        return fake_physics(cfg, name, parent)

    spec = dict(SPEC, search=dict(SPEC["search"], initial=6, events=[100, 300], refine=None, final=None))
    Optimizer(spec, evaluator=ev, out_dir=tmp_path / "opt").run()
    n_first = len(calls)
    Optimizer(spec, evaluator=ev, out_dir=tmp_path / "opt").run()
    assert len(calls) == n_first, "a resumed search must not re-simulate finished trials"


def test_shipped_specs_are_valid(tmp_path):
    assert spec_files(), "configs/optimize is empty"
    for name in spec_files():
        spec = load_spec(name)
        opt = Optimizer(spec, quick=True, evaluator=lambda *a: {}, out_dir=tmp_path / name)
        pts = sample(opt.params, 4, opt.search.get("sampler", "lhs"), np.random.default_rng(0))
        for pt in pts[:2]:
            cfg, reason = opt.config_for(pt)
            assert cfg is not None or reason, name


def test_refine_revisits_categories(tmp_path):
    """The cheap sensor is only feasible with a thin window: screening may miss it, the
    categorical moves of the refinement must find it (regression of O03)."""
    def ev(cfg, name, parent):
        sensor = cfg["geometry"]["sensor"]
        w = C.quantity(cfg["geometry"]["sensor_window_thickness"], "length")
        value = {"aSi_FPD": 8.0, "sCMOS_BSI": 0.5, "EMCCD": 0.25}[sensor]
        return {"det_yield_per_cost": value, "psf_r50_um": 100 + 1000 * w}

    spec = {"name": "T_sensor", "base": "unit_xray.yaml",
            "space": {"sensor": {"path": "geometry.sensor", "values": ["aSi_FPD", "sCMOS_BSI", "EMCCD"]},
                      "window": {"path": "geometry.sensor_window_thickness", "low": "0 mm", "high": "1 mm"}},
            "objective": {"expr": "det_yield_per_cost"}, "constraints": ["psf_r50_um <= 140"],
            "search": {"initial": 3, "events": [100], "refine": {"iterations": 6, "events": 100, "step": 0.3},
                       "final": {"top": 1, "events": 100, "repeats": 1}, "seed": 5}}
    out = Optimizer(spec, evaluator=ev, out_dir=tmp_path / "opt").run()
    best = pd.read_csv(out / "final.csv").iloc[0]
    assert best["sensor"] == "aSi_FPD" and best["window"] < 0.04
