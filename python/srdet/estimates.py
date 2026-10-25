"""Analytic cross-checks of a simulated run ("sanity estimates"): what simple physics laws and
reference data predict for the same configuration, next to what Geant4 produced.

* NIST XCOM cross sections (tests/data/xcom_*.csv, see tools/fetch_xcom.py) with Beer-Lambert:
  interaction / detection probability, share of photoelectric and Compton first interactions;
* catalogue light yield (scintillation photons per keV, lowered only by Birks quenching);
* the escape cone of a specular channel: only light within asin(n_out / n_core) of the axis can
  leave through the end face, so it bounds the light collection from above;
* decay times of the scintillator: median arrival time of the light;
* hexagonal lattice geometry (fill factor, number of cells), isotropic-source acceptance,
  photo-statistics (Poisson) and energy conservation.

Every check returns the expected value or range, the measured metric, the deviation and a status
(ok / warn / bad / n/a). The estimates are deliberately simple: a `warn` means "look closer",
a `bad` that the run or the model needs attention. The same numbers are drawn as an approximation
over the simulated points in the web UI.
"""
from __future__ import annotations

import csv
import functools
import json
import math
from pathlib import Path

import numpy as np
import yaml

from . import catalog
from . import config as C
from .paths import repo_root

# material -> (XCOM table, density g/cm3); densities as in app/src/Materials.cc / Geant4 NIST
XCOM_FOR = {"CsI_Tl": ("CsI", 4.51), "CsI_pure": ("CsI", 4.51), "NaI_Tl": ("NaI", 3.67), "LYSO": ("LYSO", 7.1),
            "BGO": ("BGO", 7.13), "GAGG": ("GAGG", 6.63), "G4_Be": ("Be", 1.848), "G4_Al": ("Al", 2.699),
            "G4_Si": ("Si", 2.33), "G4_Pb": ("Pb", 11.35)}
# scintillator: (tau1 ns, tau2 ns, share of tau1, Cauchy A, Cauchy B [um^2], Birks kB mm/MeV)  (Materials.cc)
SCINT = {"CsI_Tl": (680, 3340, 0.64, 1.7536, 0.0109, 7.1e-3), "CsI_pure": (16, 0, 1.0, 1.7536, 0.0109, 0.0),
         "NaI_Tl": (250, 0, 1.0, 1.81, 0.0069, 0.0), "LYSO": (40, 0, 1.0, 1.79, 0.0057, 0.0),
         "BGO": (300, 0, 1.0, 2.09, 0.0138, 0.0), "GAGG": (90, 0, 1.0, 1.87, 0.0108, 0.0),
         "EJ200": (2.1, 0, 1.0, 1.565, 0.0027, 0.126)}
COUPLING_N = {"OpticalGrease": (1.455, 0.0030), "Epoxy": (1.545, 0.0055), "Air": (1.0003, 0.0), "Vacuum": (1.0, 0.0)}
SPECULAR = {"Al", "Ag", "Au", "Al_simple", "mirror", "ideal", "black"}  # reflection keeps the angle to the axis
COLS = {"coherent": 1, "incoherent": 2, "photoelectric": 3, "pair_nuclear": 4, "pair_electron": 5, "total": 6}
TOL = 0.05  # default relative tolerance of an estimate


# ------------------------------------------------------------------ NIST XCOM
@functools.lru_cache(maxsize=None)
def _xcom(name: str) -> np.ndarray | None:
    p = repo_root() / "tests" / "data" / f"xcom_{name}.csv"
    if not p.exists():
        return None
    rows = list(csv.reader(l for l in p.read_text().splitlines() if not l.startswith("#")))[1:]
    return np.array(rows, dtype=float)


def mu_rho(material: str, e_kev: float, column: str = "total") -> float | None:
    """Mass attenuation coefficient (cm2/g) of a catalogue material; log-log interpolation of
    XCOM, just above an absorption edge when the energy is exactly on it. None without data."""
    ref = XCOM_FOR.get(material)
    return mu_rho_table(ref[0], e_kev, column) if ref else None


def mu_rho_table(table: str, e_kev: float, column: str = "total") -> float | None:
    """The same for an XCOM table by name (e.g. "PbO")."""
    a = _xcom(table)
    if a is None:
        return None
    e, v = a[:, 0] * 1e3, a[:, COLS[column]]
    if not e[0] <= e_kev <= e[-1]:
        return None
    i = int(np.searchsorted(e, e_kev, side="right"))
    i = min(max(i, 1), len(e) - 1)
    if v[i - 1] <= 0 or v[i] <= 0:  # pair production below threshold
        return float(np.interp(e_kev, e[i - 1:i + 1], v[i - 1:i + 1]))
    f = math.log(e_kev / e[i - 1]) / math.log(e[i] / e[i - 1])
    return math.exp(math.log(v[i - 1]) + f * (math.log(v[i]) - math.log(v[i - 1])))


def mu_linear(material: str, e_kev: float, column: str = "total") -> float | None:
    """Linear attenuation coefficient in 1/mm."""
    m = mu_rho(material, e_kev, column)
    return None if m is None else m * XCOM_FOR[material][1] / 10.0


# ------------------------------------------------------------------ small laws
def refractive_index(a: float, b: float, lam_nm: float) -> float:
    return a + b / (lam_nm / 1000.0) ** 2


def escape_cone_fraction(n_core: float, n_out: float) -> float:
    """Isotropic light within the cone around +-z that can leave through an end face
    (both hemispheres: the backward half is turned round by the entrance reflector)."""
    if n_out >= n_core:
        return 1.0
    return 1.0 - math.cos(math.asin(n_out / n_core))


def decay_median_ns(tau1: float, tau2: float, frac1: float) -> float:
    """Median emission time of a one- or two-component exponential decay."""
    if not tau2 or frac1 >= 1:
        return tau1 * math.log(2)
    lo, hi = 0.0, 20 * max(tau1, tau2)
    for _ in range(80):
        t = 0.5 * (lo + hi)
        if frac1 * math.exp(-t / tau1) + (1 - frac1) * math.exp(-t / tau2) > 0.5:
            lo = t
        else:
            hi = t
    return 0.5 * (lo + hi)


def hex_fill_factor(d: float, pitch: float, shape: str) -> float:
    cell = math.sqrt(3) / 2 * pitch * pitch
    core = math.sqrt(3) / 2 * d * d if shape == "hex" else math.pi * d * d / 4
    return core / cell


# ------------------------------------------------------------------ checks
def _status(measured, lo, hi, err: float, tol: float, abs_tol: float = 0.0) -> tuple[str, float | None]:
    """ok inside [lo, hi] widened by tolerance + 3 sigma; warn within twice that; else bad.
    Returns (status, relative deviation from the nearest edge, signed)."""
    if measured is None or not math.isfinite(measured):
        return "n/a", None
    if lo <= measured <= hi:
        return "ok", 0.0
    edge = lo if measured < lo else hi
    dev = (measured - edge) / abs(edge) if edge else measured - edge
    slack = tol * abs(edge) + abs_tol + 3 * (err or 0.0)
    if abs(measured - edge) <= slack:
        return "ok", dev
    return ("warn" if abs(measured - edge) <= 2 * slack else "bad"), dev


def _check(cid, title, metric, measured, lo, hi=None, *, law, source, unit="", err=0.0, tol=TOL, abs_tol=0.0,
           note="", approx=True) -> dict:
    hi = lo if hi is None else hi
    status, dev = _status(_num(measured), lo, hi, err, tol, abs_tol)
    return {"id": cid, "title": title, "metric": metric, "measured": _num(measured), "err": err or None,
            "low": lo, "high": hi, "value": 0.5 * (lo + hi), "unit": unit, "law": law, "source": source,
            "deviation": dev, "status": status, "tolerance": tol, "note": note, "approx": approx}


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _q(value, kind, default=None):
    try:
        return C.quantity(value, kind)
    except (TypeError, ValueError):
        return default


def _fmt(x: float) -> str:
    return f"{x:.3g}"


def run_checks(cfg: dict, m: dict, geom: dict | None = None) -> list[dict]:
    """All estimates that apply to this configuration; `m` are the analysis metrics."""
    geom = geom or {}
    g, o, b, ph = cfg.get("geometry", {}), cfg.get("optics", {}), cfg.get("beam", {}), cfg.get("physics", {})
    mode = g.get("mode", "full")
    out: list[dict] = []
    events = _num(m.get("events")) or 0

    # ---- geometry of the lattice
    pitch, d = _q(g.get("pitch"), "length"), _q(g.get("channel_diameter"), "length")
    shape = g.get("channel_shape", "circle")
    fill = None
    if mode != "slab" and pitch and d:
        fill = hex_fill_factor(d, pitch, shape)
        out.append(_check("fill_factor", "Доля площади сцинтиллятора", "geometry_fill_factor",
                          m.get("geometry_fill_factor", geom.get("core_fill_factor")), fill,
                          law=("πD²/4" if shape != "hex" else "√3/2·D²") + " ÷ (√3/2·p²), "
                              f"D = {_fmt(d * 1000)} мкм, p = {_fmt(pitch * 1000)} мкм",
                          source="геометрия шестигранной решётки", tol=0.01, approx=False))
        r_det = _q(g.get("detector_radius"), "length")
        if mode == "full" and r_det and _num(m.get("n_cells", geom.get("n_cells"))):
            n_est = math.pi * (r_det - pitch / math.sqrt(3)) ** 2 / (math.sqrt(3) / 2 * pitch * pitch)
            out.append(_check("n_cells", "Число сот", "n_cells", m.get("n_cells", geom.get("n_cells")), n_est,
                              law=f"π(R − p/√3)² ÷ (√3/2·p²), R = {_fmt(r_det)} мм",
                              source="площадь круга ÷ площадь соты", tol=0.03))

    # ---- X-rays: Beer-Lambert with NIST XCOM
    particle, spectrum = b.get("particle", "gamma"), b.get("spectrum")
    e0 = _q(b.get("energy"), "energy")
    btype = b.get("type", "pencil")
    core = g.get("slab_material") if mode == "slab" else g.get("core_material")
    length = _q(g.get("slab_thickness") if mode == "slab" else g.get("length"), "length")
    mu = mu_linear(core, e0) if (particle == "gamma" and not spectrum and e0 and core) else None
    if mu is not None and length and btype in ("pencil", "parallel", "gauss", "isotropic"):
        p_core = 1 - math.exp(-mu * length)
        law_core = f"1 − exp(−μL), μ({core}, {_fmt(e0)} кэВ) = {_fmt(mu * 10)} 1/см, L = {_fmt(length)} мм → {_fmt(p_core)}"
        if mode == "slab":
            if btype != "isotropic":
                n_int = events
                p = _num(m.get("interacting_fraction"))
                err = math.sqrt(p * (1 - p) / n_int) if p is not None and n_int else 0
                out.append(_check("beer_lambert", "Вероятность взаимодействия (Бер–Ламберт)", "interacting_fraction",
                                  p, p_core, law=law_core, source="NIST XCOM, полное ослабление", err=err, tol=0.03))
        else:
            win = g.get("window_material")
            t_win = _q(g.get("window_thickness"), "length", 0.0) or 0.0
            mu_w = mu_linear(win, e0) if t_win > 0 else 0.0
            t_w = math.exp(-(mu_w or 0.0) * t_win)
            win_note = "" if mu_w is not None else f" (окно {win}: нет данных XCOM, пропускание принято за 1)"
            # share of the beam that enters a scintillator core
            f, f_txt = 1.0, "узкий пучок в центр канала"
            r_beam = _q(b.get("radius"), "length")
            sigma = _q(b.get("sigma"), "length")
            if btype == "parallel" and r_beam and d:
                if r_beam <= d / 2:
                    f, f_txt = 1.0, "пучок уже канала"
                elif pitch and r_beam <= pitch / math.sqrt(3):
                    f, f_txt = (d / 2 / r_beam) ** 2, "доля пятна пучка на сцинтилляторе центральной соты"
                else:
                    f, f_txt = fill or 1.0, "доля площади сцинтиллятора"
            elif btype == "gauss" and sigma and d and pitch:
                f, f_txt = ((1 - math.exp(-(d / 2) ** 2 / (2 * sigma ** 2)), "гауссово пятно внутри канала")
                            if sigma < pitch else (fill or 1.0, "доля площади сцинтиллятора"))
            if btype == "isotropic":
                dist = _q(b.get("distance"), "length")
                rad = _num(geom.get("matrix_radius_mm")) or _q(g.get("detector_radius"), "length")
                if dist and rad:
                    acc = 0.5 * (1 - dist / math.hypot(dist, rad))
                    lo = acc * t_w * (fill or 1.0) * p_core
                    out.append(_check("acceptance", "Попадание изотропного источника", "interacting_fraction",
                                      m.get("interacting_fraction"), lo, acc,
                                      law=f"Ω/4π = (1 − d/√(d²+R²))/2 = {_fmt(acc)}, d = {_fmt(dist)} мм, R = {_fmt(rad)} мм; "
                                          f"снизу ×T_окна·f·(1 − exp(−μL))",
                                      source="телесный угол + NIST XCOM", tol=0.15,
                                      err=math.sqrt(acc / max(events, 1))))
            else:
                hi = t_w * p_core
                lo = hi * f
                law = (f"T_окна·f·(1 − exp(−μL)): T = exp(−μ_окна·t) = {_fmt(t_w)}{win_note}; "
                       f"f = {_fmt(f)} ({f_txt}); {law_core}")
                note = ("" if f >= 0.999 else "Нижняя граница — только прямое попадание в сцинтиллятор; верхняя — "
                        "если бы рентген, попавший в стенку, тоже доходил до сцинтиллятора (рассеяние, флуоресценция).")
                p = _num(m.get("detection_efficiency"))
                err = _num(m.get("detection_efficiency_err")) or 0
                out.append(_check("beer_lambert", "Эффективность регистрации (Бер–Ламберт)", "detection_efficiency",
                                  p, lo, hi, law=law, source="NIST XCOM, полное ослабление", err=err,
                                  tol=0.04, abs_tol=0.01, note=note))
        # first-interaction mix: photoelectric / Compton as sigma_i / sigma_total
        if btype in ("pencil",) or mode == "slab":
            none = _num(m.get("first_none"))
            n_int = events * (1 - none) if none is not None else 0
            if n_int > 20:
                win = g.get("window_material") if mode != "slab" else None
                t_win = (_q(g.get("window_thickness"), "length", 0.0) or 0.0) if win else 0.0
                mu_w = mu_linear(win, e0) if win and t_win > 0 else None
                p_w = 1 - math.exp(-mu_w * t_win) if mu_w else 0.0
                w_core = (1 - p_w) * p_core
                for proc, col, label in (("phot", "photoelectric", "фотоэффекта"), ("compt", "incoherent", "комптона")):
                    s_core = mu_rho(core, e0, col) / mu_rho(core, e0)
                    s_win = (mu_rho(win, e0, col) / mu_rho(win, e0)) if mu_w else 0.0
                    share = (p_w * s_win + w_core * s_core) / (p_w + w_core) if (p_w + w_core) > 0 else s_core
                    meas = _num(m.get(f"first_{proc}"))
                    meas = meas / (1 - none) if meas is not None and none < 1 else None
                    err = math.sqrt(max(share * (1 - share), 1e-4) / n_int)
                    out.append(_check(f"xs_{proc}", f"Доля {label} среди первых взаимодействий", f"share_{proc}",
                                      meas, share, law=f"σ_{col} / σ_полн ({core}, {_fmt(e0)} кэВ) = {_fmt(s_core)}"
                                      + (f"; с учётом окна ({_fmt(p_w * 100)} % взаимодействий) → {_fmt(share)}" if p_w > 1e-3 else ""),
                                      source="NIST XCOM, парциальные сечения", err=err, tol=0.0, abs_tol=0.02))

    # ---- scintillation light
    optical = ph.get("optical", {}) or {}
    is_gun = btype == "optical"
    scint = SCINT.get(core)
    if scint and optical.get("scintillation", True) and not is_gun and core in catalog.SCINTILLATORS:
        y = catalog.SCINTILLATORS[core][0] / 1000.0
        kb = scint[5]
        for o_ in cfg.get("materials", {}).get("overrides", []) or []:
            parts = str(o_).split()
            if len(parts) == 3 and parts[0] == "birks" and parts[1] == core:
                kb = float(parts[2])
        lo = y * (0.5 if kb > 0.05 else 0.9 if kb > 0 else 0.98)
        out.append(_check("light_yield", "Сцинтилляционных фотонов на кэВ", "scint_yield_per_keV",
                          m.get("scint_yield_per_keV"), lo, y,
                          law=f"Y = {y * 1000:,.0f} фот/МэВ ({core}, каталог) = {_fmt(y)} на кэВ; гашение Биркса "
                              f"(kB = {kb:g} мм/МэВ) только уменьшает выход".replace(",", " "),
                          source="каталог сцинтилляторов (Saint-Gobain и др.)", tol=0.03))
        med = decay_median_ns(*scint[:3])
        # the median of a few hundred photons is meaningless for a long two-component decay
        ys = _num(cfg.get("materials", {}).get("yield_scale")) or 1.0
        n_photons = (_num(m.get("mean_n_det")) or 0) * events * ys
        if n_photons >= 300:
            out.append(_check("decay_time", "Медиана времени прихода света", "t_det_median_ns",
                              m.get("t_det_median_ns"), med, med * 1.35,
                              law=f"медиана распада: τ = {scint[0]:g}" + (f" ({scint[2] * 100:.0f} %) + {scint[1]:g} нс" if scint[1] else " нс")
                                  + f" → {_fmt(med)} нс; транспорт света и шаг гистограммы добавляют до ~35 %",
                              source="времена высвечивания (Materials.cc)", tol=0.1))

    # ---- light collection: escape-cone bound of a specular channel
    coat = o.get("coating")
    rough = _q(o.get("coating_sigma_alpha"), "angle", 0.0) or 0.0
    if mode != "slab" and core in SCINT and coat in SPECULAR and rough == 0 and optical.get("boundary", True):
        a, bb = SCINT[core][3], SCINT[core][4]
        lam = catalog.SCINTILLATORS[core][2]
        n_core = refractive_index(a, bb, lam)
        cm = g.get("coupling_material", "OpticalGrease")
        if cm in COUPLING_N:
            n_out = refractive_index(*COUPLING_N[cm], lam)
            bound = escape_cone_fraction(n_core, n_out)
            out.append(_check("escape_cone", "Светосбор не выше конуса выхода", "lce", m.get("lce"), 0.0, bound,
                              law=f"зеркальный канал сохраняет угол к оси: выходит только свет внутри θc = "
                                  f"asin(n_{cm}/n_{core}) = asin({_fmt(n_out)}/{_fmt(n_core)}) = "
                                  f"{math.degrees(math.asin(min(1, n_out / n_core))):.1f}°, доля 1 − cos θc = {_fmt(bound)}",
                              source="закон Снеллиуса, полное внутреннее отражение", tol=0.03,
                              err=_num(m.get("lce_err")) or 0,
                              note="Это верхняя граница: потери на отражениях, Френеле и QE сенсора её только уменьшают."))

    # ---- photo-statistics
    dy = _num(m.get("det_yield_per_keV"))
    e_mean = _num(m.get("e0_keV"))
    if dy and e_mean and dy * e_mean > 0 and _num(m.get("resolution_fwhm_poisson_limit")):
        est = 2.3548 / math.sqrt(dy * e_mean)
        out.append(_check("poisson", "Пуассоновский предел разрешения", "resolution_fwhm_poisson_limit",
                          m.get("resolution_fwhm_poisson_limit"), est,
                          law=f"FWHM = 2.355/√N, N = pe/кэВ × E = {_fmt(dy)} × {_fmt(e_mean)} = {_fmt(dy * e_mean)}",
                          source="статистика Пуассона", tol=0.25,
                          note="Предел по фиту пика выше оценки, если светосбор неоднороден (зависит от глубины или "
                               "места взаимодействия): пик сдвинут ниже среднего. Это свойство детектора, а не ошибка."))

    # ---- energy conservation
    bal = _num(m.get("energy_balance_max_rel"))
    if bal is not None:
        out.append(_check("energy", "Сохранение энергии", "energy_balance_max_rel", bal, 0.0, 1e-3,
                          law="|E₀ − E_выделено − E_ушло| / E₀ ≤ 10⁻³ в каждом событии", source="закон сохранения",
                          tol=0.0, approx=False))
    return [c for c in out if c["status"] != "n/a"]  # metric not produced by this run (e.g. optics off)


def summary(checks: list[dict]) -> dict:
    out = {"ok": 0, "warn": 0, "bad": 0, "n/a": 0}
    for c in checks:
        out[c["status"]] = out.get(c["status"], 0) + 1
    return out


def _load_run(d: Path) -> tuple[dict, dict, dict]:
    cfg = yaml.safe_load((d / "config.yaml").read_text()) if (d / "config.yaml").exists() else {}
    if cfg:  # older / hand-written configs may lack keys: complete them with defaults.yaml
        cfg = C.deep_merge(C.load(None), cfg)
    m = json.loads((d / "metrics.json").read_text()) if (d / "metrics.json").exists() else {}
    geom = json.loads((d / "geometry.json").read_text()) if (d / "geometry.json").exists() else {}
    return cfg or {}, m, geom


def checks_for_dir(d: Path) -> list[dict]:
    cfg, m, geom = _load_run(d)
    return run_checks(cfg, m, geom) if cfg else []


def point_estimates(base: Path, rows: list[dict]) -> dict:
    """Per simulated point of a study / optimisation (rows with run_dir relative to `base`): the
    expected value (or range) of every metric that has an estimate, for the approximation overlay."""
    out = {}
    for r in rows:
        rd = r.get("run_dir")
        if not isinstance(rd, str) or not rd:
            continue
        d = base / rd
        cfg, m, geom = _load_run(d)
        if not cfg:
            continue
        m = {**m, **{k: v for k, v in r.items() if k not in m}}
        est = {}
        for c in run_checks(cfg, m, geom):
            est[c["metric"]] = {"value": c["value"], "low": c["low"], "high": c["high"], "status": c["status"],
                                "measured": c["measured"], "id": c["id"], "title": c["title"]}
        out[rd] = est
    return out
