"""Physics sanity tests: short Geant4 runs compared with reference laws and tabulated data.

They are meant to catch clearly wrong physics (units, geometry, missing processes, wrong
material tables), not to validate Geant4 at the per-cent level. Tolerances combine the
statistical error (4 sigma) with a systematic allowance stated in each test.
"""
from __future__ import annotations

import csv
import json
import math

import numpy as np
import pytest

from conftest import ROOT, needs_sim, scale

pytestmark = needs_sim

FIRST = {"phot": 1, "compt": 2, "Rayl": 3, "conv": 4}
# G4OpBoundaryProcessStatus values (Geant4 11)
TRANSMISSION, FRESNEL_REFRACTION, FRESNEL_REFLECTION, TIR = 1, 2, 3, 4


def xcom(name: str):
    rows = list(csv.reader(l for l in (ROOT / f"tests/data/xcom_{name}.csv").read_text().splitlines()
                           if not l.startswith("#")))[1:]
    return np.array(rows, dtype=float)


def xcom_at(name: str, e_kev: float, column: int) -> float:
    """Log-log interpolation; just above an edge when the energy is duplicated."""
    a = xcom(name)
    e = a[:, 0] * 1e3
    v = a[:, column]
    i = np.searchsorted(e, e_kev, side="right")
    i = min(max(i, 1), len(e) - 1)
    f = math.log(e_kev / e[i - 1]) / math.log(e[i] / e[i - 1])
    return math.exp(math.log(v[i - 1]) + f * (math.log(v[i]) - math.log(v[i - 1])))


CSI_DENSITY = 4.51  # g/cm3 (CsI_Tl in Materials.cc)


def slab(simulate, energy_kev, thickness_mm, n, name, material="CsI_Tl", extra=None):
    sets = {"geometry.slab_thickness": f"{thickness_mm} mm", "geometry.slab_material": material,
            "beam.energy": f"{energy_kev} keV", "run.events": n}
    sets.update(extra or {})
    return simulate("slab_csi.yaml", sets, name)


@pytest.mark.parametrize("e_kev,t_mm", [(20, 0.05), (40, 0.2), (60, 0.5), (100, 1.0), (662, 10.0)])
def test_beer_lambert(simulate, e_kev, t_mm):
    """Fraction of primaries crossing the slab without any interaction = exp(-mu t).
    XCOM total attenuation (with coherent). Livermore vs XCOM: allow 4 % on mu."""
    n = scale(20000)
    run, m, _ = slab(simulate, e_kev, t_mm, n, f"bl_{e_kev}")
    p = (run.events["first_proc"] == 0).mean()
    mu_sim = -math.log(p) / (t_mm / 10)
    mu_ref = xcom_at("CsI", e_kev, 6) * CSI_DENSITY
    sigma_mu = math.sqrt((1 - p) / (p * n)) / (t_mm / 10)
    assert abs(mu_sim - mu_ref) < 4 * sigma_mu + 0.04 * mu_ref, (mu_sim, mu_ref, sigma_mu)


def test_k_edge_jump(simulate):
    """Iodine K edge (33.17 keV): attenuation ratio across the edge as in XCOM (+-8 %)."""
    n = scale(30000)
    mus = []
    for e in (33.0, 33.4):
        run, _, _ = slab(simulate, e, 0.05, n, f"kedge_{e}")
        p = (run.events["first_proc"] == 0).mean()
        mus.append(-math.log(p))
    ratio_sim = mus[1] / mus[0]
    ratio_ref = xcom_at("CsI", 33.4, 6) / xcom_at("CsI", 33.0, 6)
    assert abs(ratio_sim / ratio_ref - 1) < 0.08, (ratio_sim, ratio_ref)


@pytest.mark.parametrize("e_kev", [30, 100, 300, 3000])
def test_partial_cross_sections(simulate, e_kev):
    """Share of photoelectric / Compton / Rayleigh / pair among first interactions in a thin
    slab = sigma_i / sigma_total (XCOM). Allow 0.02 absolute + 4 sigma."""
    n = scale(20000)
    t = {30: 0.05, 100: 1.0, 300: 5.0, 3000: 10.0}[e_kev]
    run, _, _ = slab(simulate, e_kev, t, n, f"xs_{e_kev}")
    ev = run.events[run.events["first_proc"] > 0]
    tot = xcom_at("CsI", e_kev, 6)
    refs = {"phot": xcom_at("CsI", e_kev, 3) / tot, "compt": xcom_at("CsI", e_kev, 2) / tot,
            "Rayl": xcom_at("CsI", e_kev, 1) / tot}
    if e_kev > 1022:
        refs["conv"] = (xcom_at("CsI", e_kev, 4) + xcom_at("CsI", e_kev, 5)) / tot
    for proc, ref in refs.items():
        frac = (ev["first_proc"] == FIRST[proc]).mean()
        err = math.sqrt(max(frac * (1 - frac), 1e-4) / len(ev))
        assert abs(frac - ref) < 0.02 + 4 * err, (proc, frac, ref)


@pytest.mark.parametrize("e_kev", [662, 5000])
def test_energy_conservation(simulate, e_kev):
    """E0 = E_deposited + E_escaping for every event (1e-3 relative); at 5 MeV escaping
    positrons must be booked with their 2 m_e c^2 annihilation energy."""
    run, m, _ = slab(simulate, e_kev, 10, scale(3000), f"cons_{e_kev}")
    bal = (run.events["e0_keV"] - run.events["edep_total_keV"] - run.events["e_escape_keV"]) / run.events["e0_keV"]
    assert np.abs(bal).max() < 1e-3


def test_fluorescence_lines(simulate):
    """60 keV in CsI: fluorescence spectrum peaks at the I and Cs K-alpha energies."""
    run, _, _ = slab(simulate, 60, 1.0, scale(20000), "bl_60_fluo")
    v, e = run.hists["fluo_energy"].to_numpy()
    c = 0.5 * (e[1:] + e[:-1])
    for line in (28.61, 30.97):
        win = (c > line - 0.3) & (c < line + 0.3)
        side = ((c > line - 1.5) & (c < line - 0.6)) | ((c > line + 0.6) & (c < line + 1.0))
        assert v[win].sum() > 5 * max(v[side].mean() * win.sum(), 1), f"no K-alpha peak at {line} keV"


def test_scintillation_yield_and_poisson(simulate):
    """N_scint / E_dep = yield (Birks off, RESOLUTIONSCALE = 1): mean within 1 %, and
    (N - Y E) / sqrt(Y E) has unit width (Poisson) within 10 %."""
    run, m, _ = simulate("slab_csi.yaml", {
        "geometry.slab_thickness": "5 mm", "beam.energy": "100 keV", "run.events": scale(2000),
        "physics.optical": {"scintillation": True, "cerenkov": False, "boundary": False, "absorption": False},
        "materials.yield_scale": 0.05, "materials.overrides": ["birks CsI_Tl 0"]}, "ly")
    ev = run.events[run.events["edep_slab_keV"] > 1]
    y = 54000 * 0.05 / 1000  # per keV
    mean = ev["n_scint"].sum() / (ev["edep_slab_keV"].sum() * y)
    assert abs(mean - 1) < 0.01
    z = (ev["n_scint"] - y * ev["edep_slab_keV"]) / np.sqrt(y * ev["edep_slab_keV"])
    assert abs(z.std() - 1) < 0.10


def _optical_slab(simulate, name, direction, energy_ev=2.25, extra=None):
    sets = {"geometry.slab_thickness": "10 mm", "geometry.slab_material": "CsI_Tl",
            "physics.optical": {"scintillation": False, "cerenkov": False},
            "beam.type": "optical", "run.events": scale(20000),
            "beam.optical": {"n": 1, "energy": f"{energy_ev} eV", "absolute": True,
                             "pos": ["0 mm", "0 mm", "0 mm"], "dir": direction}}
    sets.update(extra or {})
    return simulate("slab_csi.yaml", sets, name)


def _n_csi(energy_ev: float) -> float:
    lam_um = 1.23984193 / energy_ev
    return 1.7536 + 0.0109 / lam_um ** 2  # Cauchy form used in Materials.cc


def test_fresnel_normal_incidence(simulate):
    """CsI -> air at normal incidence: R = ((n1 - n2) / (n1 + n2))^2 ~ 0.080."""
    run, _, _ = _optical_slab(simulate, "fresnel0", [0, 0, 1])
    s = run.events["first_boundary_status"]
    s = s[s >= 0]
    r_sim = (s == FRESNEL_REFLECTION).mean()
    n1, n2 = _n_csi(2.25), 1.0003
    r_ref = ((n1 - n2) / (n1 + n2)) ** 2
    assert abs(r_sim - r_ref) < 4 * math.sqrt(r_ref * (1 - r_ref) / len(s)) + 0.003, (r_sim, r_ref)


def test_total_internal_reflection(simulate):
    """45 deg > critical angle asin(1/1.79) = 34 deg: every photon is totally reflected;
    20 deg: unpolarised Fresnel reflectance (mean of s and p)."""
    d45 = [math.sin(math.radians(45)), 0, math.cos(math.radians(45))]
    run, _, _ = _optical_slab(simulate, "tir45", d45)
    s = run.events["first_boundary_status"]
    s = s[s >= 0]
    assert (s == TIR).mean() > 0.999

    th = math.radians(20)
    run, _, _ = _optical_slab(simulate, "fresnel20", [math.sin(th), 0, math.cos(th)])
    s = run.events["first_boundary_status"]
    s = s[s >= 0]
    n1, n2 = _n_csi(2.25), 1.0003
    tt = math.asin(n1 / n2 * math.sin(th))
    rs = ((n1 * math.cos(th) - n2 * math.cos(tt)) / (n1 * math.cos(th) + n2 * math.cos(tt))) ** 2
    rp = ((n1 * math.cos(tt) - n2 * math.cos(th)) / (n1 * math.cos(tt) + n2 * math.cos(th))) ** 2
    r_ref = 0.5 * (rs + rp)
    r_sim = (s == FRESNEL_REFLECTION).mean()
    assert abs(r_sim - r_ref) < 4 * math.sqrt(r_ref * (1 - r_ref) / len(s)) + 0.004, (r_sim, r_ref)


def test_absorption_length(simulate):
    """Bulk absorption before the first boundary: 1 - exp(-d / lambda), d = 5 mm, lambda = 10 mm."""
    run, _, _ = _optical_slab(simulate, "abslen", [0, 0, 1],
                              extra={"materials.overrides": ["setAbsLength CsI_Tl 10 mm"],
                                     "physics.optical": {"scintillation": False, "cerenkov": False,
                                                         "rayleigh": False}})
    s = run.events["first_boundary_status"]
    p_sim = (s == -1).mean()
    p_ref = 1 - math.exp(-0.5)
    assert abs(p_sim - p_ref) < 4 * math.sqrt(p_ref * (1 - p_ref) / len(s)) + 0.005, (p_sim, p_ref)


def test_cherenkov_threshold_and_frank_tamm(simulate):
    """No Cherenkov light below threshold (T < 0.10 MeV for n = 1.80); Frank-Tamm photon number
    for a 1 GeV muon crossing 1 mm of CsI within 3 %."""
    base = {"geometry.slab_thickness": "1 mm", "beam.particle": "e-",
            "physics.optical": {"scintillation": False, "cerenkov": True, "boundary": False,
                                "cerenkov_max_photons": 20, "cerenkov_max_beta_change": 1}}
    run, _, _ = simulate("slab_csi.yaml", {**base, "beam.energy": "90 keV", "run.events": scale(2000)}, "cher_low")
    assert run.events["n_cher"].sum() == 0
    run, _, _ = simulate("slab_csi.yaml", {**base, "beam.energy": "2 MeV", "run.events": scale(500)}, "cher_high")
    assert run.events["n_cher"].mean() > 1

    run, _, _ = simulate("slab_csi.yaml", {**base, "beam.particle": "mu-", "beam.energy": "1 GeV",
                                           "run.events": scale(2000)}, "cher_mu")
    mats = json.loads((run.path / "materials.json").read_text())
    rin = mats["CsI_Tl"]["vectors"]["RINDEX"]
    e = np.array(rin["energy_eV"])
    n = np.array(rin["value"])
    mmu = 105.658
    gamma = (1000 + mmu) / mmu
    beta2 = 1 - 1 / gamma ** 2
    integrand = np.clip(1 - 1 / (beta2 * n ** 2), 0, None)
    trapz = getattr(np, "trapezoid", None) or np.trapz
    expected = 369.81 * 0.1 * trapz(integrand, e)  # photons per eV per cm * 0.1 cm
    got = run.events["n_cher_primary"].mean()
    assert abs(got / expected - 1) < 0.03 + 4 / math.sqrt(expected * len(run.events)), (got, expected)


@pytest.mark.parametrize("coating,r", [("mirror", 0.9), ("ideal", 1.0), ("black", 0.0)])
def test_coating_absorption_probability(simulate, coating, r):
    """Specular mirror of reflectivity R: absorbed fraction per coating hit = 1 - R."""
    run, m, _ = simulate("unit_optical.yaml", {"optics.coating": coating, "optics.coating_reflectivity": r,
                                               "run.events": scale(100), "geometry.length": "5 mm"},
                         f"coat_{coating}")
    n = run.events["coat_refl"].sum() + run.events["coat_abs"].sum()
    p = run.events["coat_abs"].sum() / n
    assert abs(p - (1 - r)) < 4 * math.sqrt(max(r * (1 - r), 1e-6) / n) + 1e-3, (p, 1 - r)


def test_light_conservation(simulate):
    """Every optical photon ends in exactly one fate."""
    run, m, _ = simulate("unit_optical.yaml", {"run.events": scale(100), "geometry.length": "5 mm"}, "fates")
    fates = run.events[["n_det", "n_abs_bulk", "n_abs_surface", "n_norindex", "n_escaped", "n_lost_other"]].sum(axis=1)
    assert (fates == run.cfg["beam"]["optical"]["n"]).all()
    assert m["lce"] <= 1


@pytest.mark.parametrize("mode", ["unit", "cluster7", "full"])
def test_geometry_has_no_overlaps(simulate, mode):
    sets = {"geometry.mode": mode, "geometry.check_overlaps": True, "run.events": 1,
            "physics.optical": {"scintillation": False}, "geometry.detector_radius": "1 mm"}
    for coating in ("Al", "none"):
        sets["optics.coating"] = coating
        run, _, log = simulate("unit_xray.yaml", sets, f"ov_{mode}_{coating}")
        assert "Overlap is detected" not in log
        assert "Checking overlaps for volume Cell" in log


def test_lattice_geometry(simulate):
    """Cells: centre distance >= pitch, all inside the matrix radius, count close to area ratio."""
    run, _, _ = simulate("full.yaml", {"run.events": 1, "physics.optical": {"scintillation": False},
                                       "beam.type": "pencil"}, "lattice")
    g = run.geom
    cells = np.array(g["cells"])[:, 2:4]
    p = g["pitch_mm"]
    rc = p / math.sqrt(3)
    r = np.hypot(cells[:, 0], cells[:, 1])
    assert (r + rc <= g["matrix_radius_mm"] + 1e-9).all()
    from scipy.spatial import cKDTree
    d, _ = cKDTree(cells).query(cells, k=2)
    assert d[:, 1].min() == pytest.approx(p, rel=1e-6)
    expected = math.pi * (g["matrix_radius_mm"] - rc) ** 2 / (math.sqrt(3) / 2 * p ** 2)
    assert abs(len(cells) / expected - 1) < 0.03
    assert g["n_cells"] == len(cells)


def test_track_export(simulate):
    """run.tracks=N writes N JSON lines with the trajectories (3D viewer of the web UI)."""
    run, _, _ = simulate("unit_xray.yaml", {"run.events": 5, "run.tracks": 3, "materials.yield_scale": 0.01},
                         "tracks")
    lines = (run.path / "tracks.jsonl").read_text().splitlines()
    assert len(lines) == 3
    ev = json.loads(lines[0])
    prim = next(t for t in ev["tracks"] if t["parent"] == 0)
    assert prim["pdg"] == 22 and len(prim["pts"]) >= 2
    z0 = prim["pts"][0][2]
    assert z0 < 0  # the beam starts in front of the detector and flies along +z
