"""Render a configuration dictionary into a Geant4 macro for srdet-sim."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import catalog, spectra
from .config import g4, quantity

GEOM = [  # (yaml key, command, kind or None)
    ("mode", "mode", None), ("detector_radius", "detectorRadius", "length"), ("length", "length", "length"),
    ("pitch", "pitch", "length"), ("channel_diameter", "channelDiameter", "length"),
    ("channel_shape", "channelShape", None), ("wall_material", "wallMaterial", None),
    ("matrix_material", "matrixMaterial", None), ("core_material", "coreMaterial", None),
    ("coating_thickness", "coatingThickness", "length"), ("coating_material", "coatingMaterial", None),
    ("world_material", "worldMaterial", None), ("housing_material", "housingMaterial", None),
    ("housing_thickness", "housingThickness", "length"), ("window_material", "windowMaterial", None),
    ("window_thickness", "windowThickness", "length"), ("coupling_material", "couplingMaterial", None),
    ("coupling_thickness", "couplingThickness", "length"), ("sensor", "sensor", None),
    ("sensor_window_thickness", "sensorWindowThickness", "length"),
    ("sensor_active_thickness", "sensorActiveThickness", "length"), ("slab_material", "slabMaterial", None),
    ("slab_thickness", "slabThickness", "length"), ("slab_half_xy", "slabHalfXY", "length"),
    ("world_margin", "worldMargin", "length"), ("check_overlaps", "checkOverlaps", None),
]
OPTICS = [("coating", "coating", None), ("coating_reflectivity", "coatingReflectivity", None),
          ("coating_sigma_alpha", "coatingSigmaAlpha", "angle"), ("film_thickness", "filmThickness", "length"),
          ("entrance_coating", "entranceCoating", None)]
OPT_PROC = {"scintillation": "Scintillation", "cerenkov": "Cerenkov", "absorption": "OpAbsorption",
            "rayleigh": "OpRayleigh", "mie": "OpMieHG", "boundary": "OpBoundary", "wls": "OpWLS"}


def _val(v, kind):
    if kind:
        return g4(v, kind)
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def front_z(cfg: dict) -> float:
    """z of the detector entrance face (mm), same convention as DetectorConstruction."""
    g = cfg["geometry"]
    if g["mode"] == "slab":
        return -quantity(g["slab_thickness"], "length") / 2
    return -quantity(g["length"], "length") / 2 - quantity(g["window_thickness"], "length")


def detector_radius(cfg: dict) -> float:
    g = cfg["geometry"]
    pitch = quantity(g["pitch"], "length")
    return {"unit": pitch / np.sqrt(3), "cluster7": pitch * (1 + 1 / np.sqrt(3)),
            "slab": quantity(g["slab_half_xy"], "length")}.get(g["mode"], quantity(g["detector_radius"], "length"))


def beam_energy_max(cfg: dict) -> float:
    b = cfg["beam"]
    if b["type"] == "optical":
        return 0.0
    res = spectra.resolve(b.get("spectrum"))
    if res:
        return float(np.max(res[1]))
    return quantity(b["energy"], "energy")


def _energy_cmds(b: dict) -> list[str]:
    res = spectra.resolve(b.get("spectrum"))
    if res is None:
        return ["/gps/ene/type Mono", f"/gps/ene/mono {g4(b['energy'], 'energy')}"]
    kind, e, w = res
    out = ["/gps/ene/type User", "/gps/hist/type energy"]
    pts: list[tuple[float, float]] = []
    if kind == "lines":
        d = 0.02  # keV half width of a line bin
        order = np.argsort(e)
        pts.append((e[order[0]] - d, 0.0))
        for i, j in enumerate(order):
            if i > 0:
                pts.append((e[j] - d, 0.0))
            pts.append((e[j] + d, float(w[j])))
    else:
        step = float(np.median(np.diff(e))) if len(e) > 1 else 1.0
        pts.append((e[0] - step / 2, 0.0))
        pts += [(float(x) + step / 2, float(y)) for x, y in zip(e, w)]
    out += [f"/gps/hist/point {x / 1000:.8g} {y:.8g}" for x, y in pts]  # GPS histogram energies in MeV
    return out


def beam_cmds(cfg: dict) -> list[str]:
    b = cfg["beam"]
    t = b["type"]
    if t == "optical":
        o = b["optical"]
        out = ["/srdet/gun/mode optical", f"/srdet/gun/opt/n {int(o['n'])}",
               f"/srdet/gun/opt/energy {g4(o['energy'], 'energy')}", f"/srdet/gun/opt/z {g4(o['z'], 'length')}",
               f"/srdet/gun/opt/zUniform {_val(bool(o['z_uniform']), None)}",
               f"/srdet/gun/opt/rUniform {_val(bool(o['r_uniform']), None)}",
               f"/srdet/gun/opt/theta {g4(o['theta'], 'angle')}"]
        if o.get("absolute"):
            p = [quantity(x, "length") for x in o["pos"]]
            d = o["dir"]
            out += ["/srdet/gun/opt/absolute true", f"/srdet/gun/opt/pos {p[0]} {p[1]} {p[2]} mm",
                    f"/srdet/gun/opt/dir {d[0]} {d[1]} {d[2]}"]
        return out
    if t == "macro":
        return ["/srdet/gun/mode gps", f"/control/execute {b['macro']}"]

    x0, y0 = (quantity(v, "length") for v in b.get("position", [0, 0]))
    z0 = front_z(cfg) - 1.0
    out = ["/srdet/gun/mode gps", "/gps/verbose 0", f"/gps/particle {b['particle']}"]
    if b["particle"] == "ion":
        out.append(f"/gps/ion {b['ion']}")
    if t == "pencil":
        out += ["/gps/pos/type Point", f"/gps/pos/centre {x0} {y0} {z0} mm", "/gps/direction 0 0 1"]
    elif t == "parallel":
        out += ["/gps/pos/type Plane", "/gps/pos/shape Circle", f"/gps/pos/centre {x0} {y0} {z0} mm",
                f"/gps/pos/radius {g4(b['radius'], 'length')}", "/gps/direction 0 0 1"]
    elif t == "gauss":
        out += ["/gps/pos/type Beam", f"/gps/pos/centre {x0} {y0} {z0} mm",
                f"/gps/pos/sigma_r {g4(b['sigma'], 'length')}", "/gps/direction 0 0 1"]
    elif t in ("divergent", "isotropic"):
        zs = front_z(cfg) - quantity(b["distance"], "length")
        out += ["/gps/pos/type Point", f"/gps/pos/centre {x0} {y0} {zs} mm", "/gps/ang/type iso"]
        if t == "divergent":
            # GPS 'iso' emits along -(sin t cos p, sin t sin p, cos t): theta = 180 deg is +z
            a = quantity(b["half_angle"], "angle")
            out += [f"/gps/ang/mintheta {180 - a} deg", "/gps/ang/maxtheta 180 deg"]
    else:
        raise ValueError(f"unknown beam type {t}")
    return out + _energy_cmds(b)


def histogram_cmds(cfg: dict) -> list[str]:
    """Upper edges of the event histograms (z and x-y ranges follow the geometry in C++)."""
    if cfg["run"].get("histograms", "auto") != "auto":
        return [str(c) for c in cfg["run"]["histograms"]]
    g = cfg["geometry"]
    emax = max(beam_energy_max(cfg) * 1.05, 1.0)
    core = g["slab_material"] if g["mode"] == "slab" else g["core_material"]
    ly, tau, _ = catalog.SCINTILLATORS.get(core, (10000, 1000, 500))
    ys = float(cfg["materials"]["yield_scale"])
    if cfg["beam"]["type"] == "optical":
        nsc = 10.0
        ndet = float(cfg["beam"]["optical"]["n"]) * 1.05 + 1
        tmax = max(0.5, 0.25 * quantity(g["length"], "length"))  # photons start at t = 0
    else:
        nsc = ly * ys * emax / 1000 * 1.3 + 10
        ndet = nsc
        tmax = max(50.0, 6 * tau)
    return [f"/srdet/out/histEmax {emax:.6g} keV", f"/srdet/out/histNScintMax {nsc:.6g}",
            f"/srdet/out/histNDetMax {ndet:.6g}", f"/srdet/out/histTmax {tmax:.6g} ns"]


def render(cfg: dict, out_dir: Path) -> str:
    g, o, m, p, r = cfg["geometry"], cfg["optics"], cfg["materials"], cfg["physics"], cfg["run"]
    L = [f"# generated by srdet for config '{cfg.get('name')}'", "/control/verbose 1", "/run/verbose 1",
         "/control/cout/ignoreThreadsExcept 0", f"/srdet/out/dir {out_dir}"]
    # empty strings mean "use the C++ default" and are not sent (G4 would keep the quotes)
    L += [f"/srdet/geom/{cmd} {_val(g[k], kind)}" for k, cmd, kind in GEOM if k in g and g[k] != ""]
    L += [f"/srdet/optics/{cmd} {_val(o[k], kind)}" for k, cmd, kind in OPTICS if k in o]
    L.append(f"/srdet/mat/yieldScale {float(m['yield_scale'])}")
    L += [f"/srdet/mat/{line}" for line in m.get("overrides", [])]
    L.append(f"/srdet/phys/em {p['em']}")
    if p.get("radioactive"):
        L.append("/srdet/phys/radioactive true")
    L += [f"/process/em/fluo {_val(bool(p['fluo']), None)}", f"/process/em/auger {_val(bool(p['auger']), None)}",
          f"/process/em/augerCascade {_val(bool(p['auger']), None)}",
          f"/process/em/pixe {_val(bool(p['pixe']), None)}",
          f"/process/em/deexcitationIgnoreCut {_val(bool(p['deexcitation_ignore_cut']), None)}",
          f"/cuts/setLowEdge {g4(p['low_edge'], 'energy')}", f"/run/setCut {g4(p['cut_world'], 'length')}",
          "/process/optical/verbose 0"]
    opt = p["optical"]
    L += [f"/process/optical/processActivation {name} {_val(bool(opt[k]), None)}" for k, name in OPT_PROC.items()]
    L += [f"/process/optical/cerenkov/setMaxPhotons {int(opt['cerenkov_max_photons'])}",
          f"/process/optical/cerenkov/setMaxBetaChange {float(opt['cerenkov_max_beta_change'])}",
          f"/process/optical/cerenkov/setTrackSecondariesFirst {_val(bool(opt['track_secondaries_first']), None)}",
          f"/process/optical/scintillation/setTrackSecondariesFirst {_val(bool(opt['track_secondaries_first']), None)}",
          f"/process/optical/scintillation/setFiniteRiseTime {_val(bool(opt['finite_rise_time']), None)}",
          f"/srdet/out/photonFraction {float(r['photon_fraction'])}",
          f"/srdet/out/cellHits {_val(bool(r['cell_hits']), None)}", f"/srdet/out/gdml {_val(bool(r['gdml']), None)}",
          "/run/initialize",
          f"/run/setCutForRegion Detector {g4(p['cut_detector'], 'length')}",
          f"/analysis/setFileName {out_dir}/srdet"]
    L += histogram_cmds(cfg)
    L += beam_cmds(cfg)
    seed = int(r["seed"])
    n = int(r["events"])
    L += [f"/random/setSeeds {seed} {seed + 7919}", f"/run/printProgress {max(1, n // 10)}"]
    L += [str(c) for c in r.get("extra_commands", [])]
    L.append(f"/run/beamOn {n}")
    L += [str(c) for c in r.get("post_commands", [])]
    return "\n".join(L) + "\n"
