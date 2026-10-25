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


def test_channel_model_limits():
    """Specular channel model: ideal mirror gives the escape cone x Fresnel, black walls only the
    direct cone, light falls with the distance to the sensor, metals rank Ag > Al > Au."""
    import numpy as np
    from srdet import estimates as E, theory as T
    lam = 550
    n_core = E.refractive_index(1.7536, 0.0109, lam)
    n_out = E.refractive_index(1.455, 0.0030, lam)
    cone = E.escape_cone_fraction(n_core, n_out)
    ideal = T.channel_lce(np.array([5.0]), 10, 0.2, "ideal", n_core, n_out, lam, entrance="ideal")[0]
    assert 0.8 * cone < ideal < cone
    near, far = T.channel_lce(np.array([9.9, 0.1]), 10, 0.2, "Al", n_core, n_out, lam)
    assert near > 5 * far
    z = np.linspace(0, 30, 50)
    lce = {c: T.channel_lce(z, 30, 0.2, c, n_core, n_out, lam).mean() for c in ("Ag", "Al", "Au")}
    assert lce["Ag"] > lce["Al"] > lce["Au"]
    # metal reflectance from CsI: Al ~ 0.87 at normal incidence (13 % loss per hit, as in U01)
    assert T.fresnel_r(n_core, T.metal_nk("Al", 550), np.array([0.0]))[0] == pytest.approx(0.87, abs=0.02)


def test_length_model_optimum_moves_with_energy():
    import numpy as np
    from srdet import theory as T
    L = np.geomspace(0.05, 100, 80)
    opt = {e: L[int(np.argmax(T.length_model(e, "Ag", L)["pe_per_incident_keV"]))] for e in (30, 60, 150, 662)}
    assert opt[30] < 2 and 0.5 < opt[60] < 2 and opt[150] > opt[60] and opt[662] > 10
    m = T.length_model(60, "Ag", np.array([1.0, 30.0]))
    assert m["absorbed"][1] - m["absorbed"][0] < 0.05      # 30 mm absorbs barely more than 1 mm at 60 keV
    assert m["pe_per_incident_keV"][1] < 0.3 * m["pe_per_incident_keV"][0]
