"""Theory next to Geant4: analytic curves for the histograms of a run and a simple model of a
detector channel, used by the web UI for visual verification.

Histogram overlays (`run_theory`):
* first_z      - depth of the first interaction: Beer-Lambert with NIST XCOM attenuation
                 (window, then scintillator core and - for wide beams - the glass walls);
* edep_core    - expected lines: photopeak, K-escape peaks (E0 - K alpha), Compton edge;
* t_det        - scintillation decay (one or two exponentials of the material);
* lambda_scint - emission spectrum (Gaussian in wavelength, as in Materials.cc);
* lambda_det   - emission spectrum x quantum efficiency of the sensor (geometry.json);
* fluo_energy  - K alpha / K beta lines of the elements present;
* lce_depth    - light collection versus emission depth derived from birthz_det / first_z.

Channel model (`channel_lce`, `length_model`): a specular channel of diameter D and length L
(sensor at the far end). A photon emitted at polar angle theta to the axis keeps |theta| on every
wall reflection; it can leave through the end face only inside the escape cone
theta < asin(n_out / n_core), with the Fresnel transmission of that face. On the way it hits the
wall about d tan(theta) / D_eff times (D_eff = pi D / 4, the mean chord of a circle), losing
1 - R(90 deg - theta) each time, with R from the complex refractive index of the metal (the same
n + ik tables as the simulation). Photons going backwards are turned round by the entrance
reflector. Absorption in the bulk uses the attenuation length of the core.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import yaml

from . import config as C
from . import estimates as E

HC_EV_NM = 1239.84193
# K-shell lines (keV): K edge, K alpha1, K beta1  (X-ray data booklet)
K_LINES = {"I": (33.17, 28.61, 32.29), "Cs": (35.98, 30.97, 34.99), "Na": (1.07, 1.04, 1.07),
           "Lu": (63.31, 54.07, 61.28), "Y": (17.04, 14.96, 16.74), "Bi": (90.53, 77.11, 87.34),
           "Ge": (11.10, 9.89, 10.98), "Gd": (50.24, 42.99, 48.70), "Ga": (10.37, 9.25, 10.26),
           "Pb": (88.00, 74.97, 84.94), "Ba": (37.44, 32.19, 36.38), "Si": (1.84, 1.74, 1.84)}
ELEMENTS = {"CsI_Tl": ["I", "Cs"], "CsI_pure": ["I", "Cs"], "NaI_Tl": ["I"], "LYSO": ["Lu", "Y"],
            "BGO": ["Bi", "Ge"], "GAGG": ["Gd", "Ga"], "LeadGlass_MCP": ["Pb", "Ba"], "LeadGlass_NIST": ["Pb"]}
# emission peak / FWHM in nm (Materials.cc)
EMISSION = {"CsI_Tl": (550, 130), "CsI_pure": (315, 40), "NaI_Tl": (415, 80), "LYSO": (420, 70),
            "BGO": (480, 110), "GAGG": (530, 110), "EJ200": (425, 50)}
ABS_LENGTH_MM = {"EJ200": 3800.0}  # others: 40 cm
# complex refractive index of the metal coatings, (lambda nm, n, k)  (OpticalSurfaces.cc)
METAL_NK = {
    "Al": [(300, 0.276, 3.61), (350, 0.37, 4.25), (400, 0.49, 4.86), (450, 0.62, 5.47), (500, 0.77, 6.08),
           (550, 0.96, 6.69), (600, 1.20, 7.26), (650, 1.47, 7.79), (700, 1.83, 8.31), (750, 2.40, 8.62)],
    "Ag": [(300, 1.35, 0.80), (350, 0.20, 1.30), (400, 0.05, 2.10), (450, 0.04, 2.65), (500, 0.05, 3.09),
           (550, 0.055, 3.59), (600, 0.06, 4.00), (650, 0.05, 4.45), (700, 0.04, 4.84)],
    "Au": [(300, 1.62, 1.90), (350, 1.63, 1.90), (400, 1.47, 1.95), (450, 1.38, 1.85), (500, 0.97, 1.87),
           (550, 0.43, 2.45), (600, 0.25, 3.00), (650, 0.17, 3.50), (700, 0.16, 3.95)],
}
# glass walls as mixtures of XCOM tables: ([(table, mass fraction)], density)
WALL_XCOM = {"LeadGlass_MCP": ([("PbO", 0.51), ("SiO2", 0.49)], 3.95), "FusedSilica": ([("SiO2", 1.0)], 2.20),
             "Borosilicate": ([("SiO2", 1.0)], 2.23)}


# ------------------------------------------------------------------ optics
def metal_nk(metal: str, lam_nm: float) -> complex | None:
    t = METAL_NK.get(metal)
    if not t:
        return None
    lam = [p[0] for p in t]
    return complex(np.interp(lam_nm, lam, [p[1] for p in t]), np.interp(lam_nm, lam, [p[2] for p in t]))


def fresnel_r(n1: float, n2: complex, phi: np.ndarray) -> np.ndarray:
    """Unpolarised reflectance from a dielectric n1 onto n2 (complex for a metal) at incidence phi."""
    s = n1 * np.sin(phi) / n2
    cos_t = np.sqrt(1 - s * s + 0j)
    cos_i = np.cos(phi)
    rs = (n1 * cos_i - n2 * cos_t) / (n1 * cos_i + n2 * cos_t)
    rp = (n2 * cos_i - n1 * cos_t) / (n2 * cos_i + n1 * cos_t)
    return np.clip(0.5 * (np.abs(rs) ** 2 + np.abs(rp) ** 2), 0, 1)


def coating_reflectance(coating: str, n_core: float, lam_nm: float, phi: np.ndarray, r_const: float = 0.9):
    """Reflectance of the channel wall seen from the core, or None if not specular."""
    if coating in METAL_NK:
        return fresnel_r(n_core, metal_nk(coating, lam_nm), phi)
    if coating == "ideal":
        return np.ones_like(phi)
    if coating == "black":
        return np.zeros_like(phi)
    if coating == "mirror":
        return np.full_like(phi, r_const)
    if coating == "Al_simple":
        return np.full_like(phi, 0.90)
    return None


def channel_lce(z: np.ndarray, length: float, d: float, coating: str, n_core: float, n_out: float,
                lam_nm: float, entrance: str = "Al", r_const: float = 0.9, abs_len: float = 400.0) -> np.ndarray:
    """Fraction of isotropic light emitted at depth z (0 = entrance, L = sensor) that leaves the
    end face of a specular channel. Vectorised over z (mm)."""
    th_c = math.asin(min(1.0, n_out / n_core))
    th = np.linspace(1e-4, th_c - 1e-6, 400)
    w = np.sin(th) * (th[1] - th[0]) / 2          # isotropic weight of each hemisphere
    r_wall = coating_reflectance(coating, n_core, lam_nm, np.pi / 2 - th, r_const)
    if r_wall is None:
        return np.full_like(np.asarray(z, float), np.nan)
    r_ent = coating_reflectance(entrance, n_core, lam_nm, th, r_const) if entrance not in ("none", "") else np.zeros_like(th)
    if r_ent is None:
        r_ent = np.full_like(th, 0.9)
    t_exit = 1 - fresnel_r(n_core, complex(n_out, 0), th)
    d_eff = math.pi * d / 4
    hits_per_mm = np.tan(th) / d_eff
    path_per_mm = 1 / np.cos(th)
    z = np.atleast_1d(np.asarray(z, float))[:, None]
    fwd = (length - z)
    bwd = (z + length)
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.log(np.clip(r_wall, 1e-300, 1))
    s_f = np.exp(fwd * hits_per_mm * lr - fwd * path_per_mm / abs_len)
    s_b = r_ent * np.exp(bwd * hits_per_mm * lr - bwd * path_per_mm / abs_len)
    return ((s_f + s_b) * t_exit * w).sum(axis=1)


def emission_weighted_qe(core: str, qe: tuple[list, list] | None) -> float:
    """Mean quantum efficiency over the emission spectrum (1 for an ideal sensor)."""
    if not qe or core not in EMISSION:
        return 1.0
    peak, fwhm = EMISSION[core]
    lam = np.linspace(peak - 3 * fwhm, peak + 3 * fwhm, 400)
    em = np.exp(-0.5 * ((lam - peak) / (fwhm / 2.3548)) ** 2)
    e_ev, eff = np.asarray(qe[0]), np.asarray(qe[1])
    q = np.interp(HC_EV_NM / lam, e_ev, eff, left=0, right=0)
    return float((em * q).sum() / em.sum())


# ------------------------------------------------------------------ X-ray attenuation
def mu_wall(material: str, e_kev: float) -> float | None:
    """Linear attenuation (1/mm) of a wall glass from mixed XCOM tables."""
    mix = WALL_XCOM.get(material)
    if not mix:
        return None
    tot = 0.0
    for table, frac in mix[0]:
        m = E.mu_rho_table(table, e_kev)
        if m is None:
            return None
        tot += frac * m
    return tot * mix[1] / 10.0


def length_model(e_kev: float, coating: str, lengths: np.ndarray, *, core="CsI_Tl", d=0.2,
                 coupling="OpticalGrease", entrance="Al", window="G4_Be", t_window=0.5, qe=1.0) -> dict:
    """Absorption, light collection and signal versus channel length for a pencil X-ray beam
    along the axis of one channel (the U04c setup), from NIST XCOM and the channel model."""
    mu = E.mu_linear(core, e_kev)
    mu_w = E.mu_linear(window, e_kev) if t_window > 0 else 0.0
    t_w = math.exp(-(mu_w or 0) * t_window)
    a, b = E.SCINT[core][3], E.SCINT[core][4]
    lam = EMISSION[core][0]
    n_core = E.refractive_index(a, b, lam)
    n_out = E.refractive_index(*E.COUPLING_N[coupling], lam)
    y = E.catalog.SCINTILLATORS[core][0] / 1000.0
    out = {"L": [], "absorbed": [], "lce_xray": [], "lce_uniform": [], "pe_per_incident_keV": [],
           "pe_per_absorbed_keV": []}
    for L in lengths:
        p_abs = t_w * (1 - math.exp(-mu * L))
        z = np.linspace(0, L, 200)
        lce_z = channel_lce(z, L, d, coating, n_core, n_out, lam, entrance, abs_len=ABS_LENGTH_MM.get(core, 400.0))
        dep = mu * np.exp(-mu * z)              # where the X-rays are absorbed
        lce_x = float((lce_z * dep).sum() / dep.sum())
        lce_u = float(lce_z.mean())
        out["L"].append(float(L))
        out["absorbed"].append(p_abs)
        out["lce_xray"].append(lce_x)
        out["lce_uniform"].append(lce_u)
        out["pe_per_absorbed_keV"].append(y * lce_x * qe)
        out["pe_per_incident_keV"].append(y * lce_x * qe * p_abs)
    out.update({"mu_per_mm": mu, "attenuation_length_mm": 1 / mu, "L99_mm": math.log(100) / mu,
                "window_transmission": t_w, "n_core": n_core, "n_out": n_out,
                "escape_cone": E.escape_cone_fraction(n_core, n_out), "yield_per_keV": y, "qe": qe})
    return out


# ------------------------------------------------------------------ histogram overlays of a run
def _hist(f, name):
    if name not in [k.split(";")[0] for k in f.keys()]:
        return None
    vals, edges = f[name].to_numpy()
    return np.asarray(vals, float), np.asarray(edges, float)


def _pack(name, title, vals, edges, xlabel, *, curves=(), lines=(), text="", agreement=None, ylabel="число"):
    return {"name": name, "title": title, "values": vals.tolist(), "edges": edges.tolist(), "xlabel": xlabel,
            "ylabel": ylabel, "curves": list(curves), "lines": list(lines), "text": text, "agreement": agreement}


def _fit_mu(centres, vals, z0, mu_ref):
    """Slope of log(counts) over the first ~3 attenuation lengths (weighted least squares)."""
    sel = (centres > z0) & (centres < z0 + 3 / mu_ref) & (vals > 5)
    if sel.sum() < 4:
        return None
    x, yv = centres[sel] - z0, np.log(vals[sel])
    wts = vals[sel]
    a = np.vstack([x, np.ones_like(x)]).T * np.sqrt(wts)[:, None]
    coef, *_ = np.linalg.lstsq(a, yv * np.sqrt(wts), rcond=None)
    return float(-coef[0])


def run_theory(d: Path) -> list[dict]:
    import uproot
    cfg = yaml.safe_load((d / "config.yaml").read_text()) if (d / "config.yaml").exists() else {}
    cfg = C.deep_merge(C.load(None), cfg or {})
    m = json.loads((d / "metrics.json").read_text()) if (d / "metrics.json").exists() else {}
    geom = json.loads((d / "geometry.json").read_text()) if (d / "geometry.json").exists() else {}
    if not (d / "srdet.root").exists():
        return []
    f = uproot.open(d / "srdet.root")
    g, b, o = cfg["geometry"], cfg["beam"], cfg["optics"]
    mode = g.get("mode")
    core = g.get("slab_material") if mode == "slab" else g.get("core_material")
    e0 = E._q(b.get("energy"), "energy")
    mono = b.get("particle") == "gamma" and not b.get("spectrum") and e0
    length = float(geom.get("length_mm") or E._q(g.get("length"), "length") or 0)
    z0 = -length / 2
    events = float(m.get("events") or 0)
    out = []

    # ---- depth of the first interaction vs Beer-Lambert
    h = _hist(f, "first_z")
    mu = E.mu_linear(core, e0) if mono else None
    if h is not None and mu and b.get("type") in ("pencil", "parallel", "gauss") and h[0].sum() > 0:
        vals, edges = h
        model = np.zeros_like(vals)
        comps = []
        t_w = 1.0
        if mode != "slab":
            win = g.get("window_material")
            tw = E._q(g.get("window_thickness"), "length", 0.0) or 0.0
            mu_w = E.mu_linear(win, e0) if tw > 0 else 0.0
            if mu_w:
                zf = z0 - tw
                a_, b_ = np.clip(edges[:-1], zf, z0), np.clip(edges[1:], zf, z0)
                model += events * (np.exp(-mu_w * (a_ - zf)) - np.exp(-mu_w * (b_ - zf)))
                t_w = math.exp(-mu_w * tw)
                comps.append(f"окно {win} {tw:g} мм (μ = {mu_w * 10:.3g} 1/см)")
        f_core, f_txt = 1.0, ""
        est = {c["id"]: c for c in E.run_checks(cfg, m, geom)}
        bl = est.get("beer_lambert")
        if bl and bl["high"] > 0 and bl["low"] < bl["high"]:
            f_core = bl["low"] / bl["high"]
        a_, b_ = np.clip(edges[:-1], z0, z0 + length), np.clip(edges[1:], z0, z0 + length)
        model += events * t_w * f_core * (np.exp(-mu * (a_ - z0)) - np.exp(-mu * (b_ - z0)))
        comps.append(f"сцинтиллятор {core} (μ = {mu * 10:.3g} 1/см, 1/μ = {1 / mu:.3g} мм)")
        if f_core < 0.999:
            mw = mu_wall(g.get("wall_material"), e0)
            if mw:
                model += events * t_w * (1 - f_core) * (np.exp(-mw * (a_ - z0)) - np.exp(-mw * (b_ - z0)))
                comps.append(f"стенки {g.get('wall_material')} {100 * (1 - f_core):.0f} % площади (μ = {mw * 10:.3g} 1/см)")
            f_txt = f" Доля пучка на сцинтилляторе {f_core:.2f}."
        centres = 0.5 * (edges[1:] + edges[:-1])
        mu_fit = _fit_mu(centres, vals, z0, mu) if f_core > 0.999 else None
        agree = {"label": "μ по наклону Geant4 / μ NIST", "sim": mu_fit * 10 if mu_fit else None, "ref": mu * 10,
                 "unit": "1/см"} if mu_fit else None
        out.append(_pack("first_z", "Где рентген впервые провзаимодействовал", vals, edges, "глубина z, мм",
                         curves=[{"name": "Бер–Ламберт (NIST XCOM)", "y": model.tolist(), "step": True}],
                         lines=[{"x": z0, "label": "вход в сцинтиллятор"},
                                {"x": z0 + min(length, 1 / mu), "label": "1/μ"},
                                {"x": z0 + min(length, math.log(100) / mu), "label": "99 % поглощено"}],
                         text=f"Ожидание: экспоненциальное ослабление exp(−μz), компоненты: {'; '.join(comps)}.{f_txt} "
                              f"99 % рентгена поглощается на первых {math.log(100) / mu:.3g} мм канала длиной {length:g} мм.",
                         agreement=agree))

    # ---- deposited energy: expected lines
    h = _hist(f, "edep_core")
    if h is not None and mono and h[0].sum() > 0:
        vals, edges = h
        lines = [{"x": e0, "label": f"фотопик {e0:g}"}]
        for el in ELEMENTS.get(core, []):
            edge, ka, kb = K_LINES[el]
            if e0 > edge:
                lines.append({"x": e0 - ka, "label": f"K-escape {el} ({e0 - ka:.3g})"})
        if e0 > 50:
            eps = e0 / 511.0
            lines.append({"x": e0 * 2 * eps / (1 + 2 * eps), "label": "край Комптона"})
        out.append(_pack("edep_core", "Энергия, выделенная в сцинтилляторе", vals, edges, "E, кэВ", lines=lines,
                         text="Линии — где должны быть пики: полное поглощение E₀, пики вылета K-флуоресценции "
                              "E₀ − Kα (если E₀ выше K-края) и край комптоновского распределения "
                              "E₀·2ε/(1+2ε), ε = E₀/511 кэВ." + (
                             f" В Geant4: доля фотопика {m['photopeak_fraction']:.3g}, вероятность K-escape "
                             f"{m.get('k_escape_fraction', 0):.3g}." if m.get("photopeak_fraction") is not None else "")))

    # ---- arrival time vs decay
    h = _hist(f, "t_det")
    sc = E.SCINT.get(core)
    if h is not None and sc and h[0].sum() > 50 and b.get("type") != "optical":
        vals, edges = h
        t1, t2, f1 = sc[:3]
        cdf = lambda t: 1 - (f1 * np.exp(-t / t1) + ((1 - f1) * np.exp(-t / t2) if t2 else 0))  # noqa: E731
        p = cdf(edges[1:]) - cdf(edges[:-1])
        model = p / p.sum() * vals.sum()
        out.append(_pack("t_det", "Время прихода зарегистрированных фотонов", vals, edges, "t, нс",
                         curves=[{"name": "высвечивание " + core, "y": model.tolist(), "step": True}],
                         lines=[{"x": E.decay_median_ns(t1, t2, f1), "label": "медиана распада"}],
                         text=f"Ожидание: распад сцинтиллятора τ = {t1:g} нс" + (f" ({f1 * 100:.0f} %) и {t2:g} нс" if t2 else "")
                              + "; транспорт света по каналу добавляет доли наносекунды.",
                         agreement={"label": "медиана, нс", "sim": m.get("t_det_median_ns"),
                                    "ref": E.decay_median_ns(t1, t2, f1), "unit": "нс"}, ylabel="фотоны"))

    # ---- wavelength: emission and emission x QE
    em = EMISSION.get(core)
    qe = geom.get("sensor_efficiency")
    for name, title, use_qe in (("lambda_scint", "Длина волны рождённых фотонов", False),
                                ("lambda_det", "Длина волны зарегистрированных фотонов", True)):
        h = _hist(f, name)
        if h is None or not em or h[0].sum() < 50:
            continue
        vals, edges = h
        c = 0.5 * (edges[1:] + edges[:-1])
        shape = np.exp(-0.5 * ((c - em[0]) / (em[1] / 2.3548)) ** 2)
        if use_qe and qe:
            shape = shape * np.interp(HC_EV_NM / c, qe["energy_eV"], qe["efficiency"], left=0, right=0)
        if shape.sum() <= 0:
            continue
        model = shape / shape.sum() * vals.sum()
        mean_sim = float((c * vals).sum() / vals.sum())
        mean_ref = float((c * shape).sum() / shape.sum())
        out.append(_pack(name, title, vals, edges, "λ, нм",
                         curves=[{"name": "спектр излучения" + (" × QE сенсора" if use_qe and qe else ""),
                                  "y": model.tolist(), "step": True}],
                         text=("Ожидание: гауссов спектр излучения " if not use_qe else
                               "Ожидание: спектр излучения, умноженный на квантовую эффективность сенсора "
                               f"({g.get('sensor')}); ") + f"пик {em[0]} нм, FWHM {em[1]} нм.",
                         agreement={"label": "средняя λ, нм", "sim": mean_sim, "ref": mean_ref, "unit": "нм"},
                         ylabel="фотоны"))

    # ---- fluorescence lines
    h = _hist(f, "fluo_energy")
    if h is not None and h[0].sum() > 20:
        vals, edges = h
        lines = []
        for el in ELEMENTS.get(core, []) + ELEMENTS.get(g.get("wall_material"), []):
            edge, ka, kb = K_LINES[el]
            if not mono or e0 > edge:
                lines += [{"x": ka, "label": f"{el} Kα"}, {"x": kb, "label": f"{el} Kβ"}]
        if lines:
            out.append(_pack("fluo_energy", "Энергии флуоресцентных квантов", vals, edges, "E, кэВ", lines=lines,
                             text="Линии — табличные энергии Kα и Kβ элементов сцинтиллятора и стекла "
                                  "(появляются, только если энергия пучка выше K-края).", ylabel="кванты"))

    # ---- light collection vs emission depth (why long channels lose light)
    hb, hz = _hist(f, "birthz_det"), _hist(f, "first_z")
    lce = m.get("lce")
    if hb is not None and lce and hb[0].sum() > 100:
        vb, edges = hb
        c = 0.5 * (edges[1:] + edges[:-1])
        if b.get("type") == "optical":
            ob = b.get("optical", {})
            born = ((c > z0) & (c < z0 + length)).astype(float) if ob.get("z_uniform", True) else None
        elif hz is not None and hz[0].sum() > 0 and len(hz[1]) == len(edges):
            born = hz[0].astype(float)
        else:
            born = None
        if born is not None and born.sum() > 0:
            # rebin to ~40 bins over the channel for readable statistics
            inside = (c > z0) & (c < z0 + length)
            idx = np.where(inside)[0]
            if len(idx) >= 4:
                k = max(1, len(idx) // 40)
                xs, ys = [], []
                for i in range(idx[0], idx[-1] + 1, k):
                    sb, sz = vb[i:i + k].sum(), born[i:i + k].sum()
                    if sz > 0 and (b.get("type") == "optical" or sz >= 20):
                        xs.append(float(c[i:i + k].mean()))
                        ys.append(float(lce * (sb / vb[inside].sum()) / (sz / born[inside].sum())))
                model_curve = []
                coat = o.get("coating")
                if mode != "slab" and core in E.SCINT and coat in METAL_NK | {"ideal": 0, "mirror": 0, "black": 0}:
                    cm = g.get("coupling_material", "OpticalGrease")
                    if cm in E.COUPLING_N and xs:
                        lam = EMISSION[core][0]
                        n_core = E.refractive_index(*E.SCINT[core][3:5], lam)
                        n_out = E.refractive_index(*E.COUPLING_N[cm], lam)
                        dch = float(geom.get("channel_diameter_mm") or 0.2)
                        qe_eff = emission_weighted_qe(core, (qe["energy_eV"], qe["efficiency"]) if qe else None)
                        lz = channel_lce(np.array(xs) - z0, length, dch, coat, n_core, n_out, lam,
                                         o.get("entrance_coating", "Al"), float(o.get("coating_reflectivity", 0.9)),
                                         ABS_LENGTH_MM.get(core, 400.0)) * qe_eff
                        model_curve = [{"name": "модель зеркального канала", "y": lz.tolist(), "x": xs}]
                if xs:
                    out.append({"name": "lce_depth", "title": "Светосбор в зависимости от места рождения света",
                                "points": {"x": xs, "y": ys}, "xlabel": "глубина z, мм (сенсор справа)",
                                "ylabel": "доля света, дошедшая до сенсора", "curves": model_curve,
                                "lines": [{"x": z0, "label": "вход"}, {"x": z0 + length, "label": "сенсор"}],
                                "text": "Точки — Geant4: какая доля света, рождённого на глубине z, зарегистрирована "
                                        "(отношение распределений birthz_det и места рождения). Линия — простая "
                                        "модель: свет внутри конуса выхода, потери на каждом отражении от стенки "
                                        "по комплексному n+ik металла. Свет, рождённый у входа, идёт до сенсора "
                                        "дальше всего и теряется сильнее. Модель приближённая: свет из дальнего "
                                        "конца длинного канала она занижает в 1.5–2.5 раза (см. «Верификация»).",
                                "agreement": None})
    return out
