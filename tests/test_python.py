"""Fast tests of the Python layer (no Geant4 needed)."""
from __future__ import annotations

import math
import re

import numpy as np
import pytest

from conftest import ROOT
from srdet import catalog, config as C, macro, spectra, studies


def test_quantities():
    assert C.quantity("200 um", "length") == pytest.approx(0.2)
    assert C.quantity("1.5 cm", "length") == pytest.approx(15)
    assert C.quantity("0.662 MeV", "energy") == pytest.approx(662)
    assert C.quantity(3, "length") == 3
    assert C.g4("2 um", "length") == "0.002 mm"
    with pytest.raises(ValueError):
        C.quantity("3 parsec", "length")


def test_overrides_merge():
    cfg = C.load("unit_optical.yaml")
    C.set_path(cfg, "physics.optical", {"scintillation": False})
    assert cfg["physics"]["optical"]["scintillation"] is False
    assert "boundary" in cfg["physics"]["optical"]  # partial update keeps other keys
    cfg = C.apply_sets(cfg, ["geometry.length=5 mm", "run.events=7"])
    assert cfg["geometry"]["length"] == "5 mm" and cfg["run"]["events"] == 7


@pytest.mark.parametrize("name", ["full", "legacy_like", "unit_optical", "unit_xray", "cluster7_xray", "slab_csi"])
def test_macro_order(name, tmp_path):
    text = macro.render(C.load(name), tmp_path)
    lines = text.splitlines()
    init = lines.index("/run/initialize")
    region = [i for i, l in enumerate(lines) if l.startswith("/run/setCutForRegion")]
    geom = [i for i, l in enumerate(lines) if l.startswith("/srdet/geom/")]
    assert max(geom) < init < region[0] < lines.index(lines[-1])
    assert lines[-1].startswith("/run/beamOn")
    assert not any('""' in l for l in lines)


def test_divergent_beam_points_to_detector(tmp_path):
    cfg = C.load("full")
    cfg["beam"]["type"] = "divergent"
    cmds = macro.beam_cmds(cfg)
    assert "/gps/ang/maxtheta 180 deg" in cmds  # GPS iso: theta = 180 deg is +z


def test_line_spectrum_histogram():
    cfg = C.load("full")
    cfg["beam"]["spectrum"] = {"source": "Am241"}
    pts = [l for l in macro.beam_cmds(cfg) if l.startswith("/gps/hist/point")]
    e = np.array([float(l.split()[1]) for l in pts])
    assert np.all(np.diff(e) > 0), "GPS histogram edges must increase"
    assert e.max() == pytest.approx(0.05956, abs=1e-4)  # MeV


def test_xray_tube_spectrum():
    e, w = spectra.xray_tube(80, 2.5)
    assert e.max() < 80 and w.sum() == pytest.approx(1)
    # filtration hardens the spectrum: mean energy grows with filter thickness
    e2, w2 = spectra.xray_tube(80, 10)
    assert (e2 * w2).sum() > (e * w).sum()


def test_xcom_k_edge():
    # CsI: iodine K edge at 33.17 keV, total attenuation jumps by ~3
    lo = spectra.mu_rho("CsI", np.array([33.0]))[0]
    hi = spectra.mu_rho("CsI", np.array([33.4]))[0]
    assert 2.5 < hi / lo < 3.5


def test_catalog_matches_cpp():
    src = (ROOT / "app/src/OpticalSurfaces.cc").read_text()
    cpp = set(re.findall(r'\{"(\w+)", \{"\1",', src))
    assert cpp == set(catalog.COATINGS), cpp ^ set(catalog.COATINGS)
    src = (ROOT / "app/src/Sensors.cc").read_text()
    cpp = set(re.findall(r'\{"(\w+)",\s*\{"\1"', src))
    assert cpp == set(catalog.SENSORS), cpp ^ set(catalog.SENSORS)
    src = (ROOT / "app/src/Materials.cc").read_text()
    for name in list(catalog.SCINTILLATORS) + catalog.GLASSES + catalog.OTHER_MATERIALS:
        assert f'{{"{name}",' in src, name


def test_all_studies_expand():
    for name in studies.study_files():
        s = studies.load_study(name)
        pts = studies.points(s)
        assert pts, name
        cfg = C.load(s["base"])
        for p in pts[:2]:
            c = C.deep_merge(cfg, {})
            for k, v in p.items():
                if k != "variant":
                    C.set_path(c, k, v)
            macro.render(c, ROOT / "runs" / "dummy")


def test_study_derived_metrics_and_explained_report(tmp_path):
    import pandas as pd
    from srdet.studies import derived_metrics, write_report
    study = {"name": "T_len", "title": "t", "scan": {"geometry.length": ["1 mm", "2 mm"]},
             "derived": {"pe_in": "det_yield_per_keV * detection_efficiency", "bad": "missing * 2"},
             "metrics": ["pe_in"], "explain": {"question": "Какая длина лучше?", "why": "потому что"}}
    row = {"det_yield_per_keV": 8.0, "detection_efficiency": 0.5, "ok": True}
    d = derived_metrics(study, row)
    assert d["pe_in"] == 4.0 and d["bad"] != d["bad"]  # NaN for a missing input
    df = pd.DataFrame([{"geometry.length": 1.0, "ok": True, "run_dir": "a", **d},
                       {"geometry.length": 2.0, "ok": True, "run_dir": "b", **d}])
    text = write_report(study, df, tmp_path).read_text()
    assert "Зачем это исследование" in text and "Какая длина лучше?" in text


def test_estimates_laws():
    import math
    from srdet import estimates as E
    # NIST XCOM CsI at 60 keV: mu/rho = 7.9 cm2/g (1 mm = 3.6 attenuation lengths); iodine K edge at 33.17 keV
    assert 7.5 < E.mu_rho("CsI_Tl", 60) < 8.3
    assert E.mu_rho("CsI_Tl", 33.3) > 2.5 * E.mu_rho("CsI_Tl", 33.0)  # K-edge jump ~3x
    assert E.mu_rho("EJ200", 60) is None  # no XCOM table -> no estimate, not a wrong one
    assert E.escape_cone_fraction(1.79, 1.465) == pytest.approx(1 - math.cos(math.asin(1.465 / 1.79)))
    assert E.escape_cone_fraction(1.5, 1.6) == 1.0
    assert E.decay_median_ns(100, 0, 1) == pytest.approx(100 * math.log(2))
    med = E.decay_median_ns(680, 3340, 0.64)
    assert 0.64 * math.exp(-med / 680) + 0.36 * math.exp(-med / 3340) == pytest.approx(0.5, abs=1e-6)
    assert E.hex_fill_factor(0.2, 0.208, "circle") == pytest.approx(0.8385, abs=1e-3)


def test_estimates_flag_a_wrong_result():
    from srdet import estimates as E
    cfg = C.load("unit_xray.yaml")
    mu = E.mu_linear("CsI_Tl", 60)
    t_w = math.exp(-E.mu_linear("G4_Be", 60) * 0.5)
    good = {"events": 2000, "detection_efficiency": t_w * (1 - math.exp(-mu * 30)), "detection_efficiency_err": 0.003,
            "scint_yield_per_keV": 53.0, "energy_balance_max_rel": 1e-6}
    checks = {c["id"]: c for c in E.run_checks(cfg, good)}
    assert checks["beer_lambert"]["status"] == "ok" and checks["light_yield"]["status"] == "ok"
    assert checks["energy"]["status"] == "ok"
    bad = dict(good, detection_efficiency=0.5, scint_yield_per_keV=80.0, energy_balance_max_rel=0.2)
    checks = {c["id"]: c for c in E.run_checks(cfg, bad)}
    assert checks["beer_lambert"]["status"] == "bad" and checks["light_yield"]["status"] == "bad"
    assert checks["energy"]["status"] == "bad"
    # a spectrum instead of one energy: no Beer-Lambert estimate rather than a wrong one
    cfg["beam"]["spectrum"] = {"source": "Am241"}
    assert "beer_lambert" not in {c["id"] for c in E.run_checks(cfg, good)}
