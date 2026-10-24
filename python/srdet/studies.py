"""Automatic experiments: parameter scans described in configs/studies/*.yaml.

Study file:
    name: U1_coating
    title: "U1 - light collection vs channel coating"
    description: >  what is isolated and why
    base: unit_optical.yaml          # detector config (configs/detector/)
    set: {run.events: 400}           # dotted overrides for every point
    scan:                            # one or more dotted keys
      optics.coating: [none, Al, Ag]
    mode: product                    # product | zip
    x: optics.coating                # x axis (default: first scan key)
    series: null                     # optional key drawn as separate curves
    quick: {run.events: 40}          # applied with --quick (CI)
    metrics: [lce, coat_abs_prob]
    labels: {lce: "Light collection efficiency"}
    logx: false
    reference: null                  # optional analytic overlay (see REFERENCES)

Output: runs/studies/<stamp>_<name>/{results.csv, results.md, report.md, plots/*.png, runs/...}
"""
from __future__ import annotations

import datetime as dt
import itertools
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import config as C
from .analysis import analyze_run
from .paths import configs_dir, runs_dir
from .plotting import process_counts, stacked_fractions, study_plot
from .runner import run


def study_files() -> dict[str, Path]:
    return {p.stem: p for p in sorted((configs_dir() / "studies").glob("*.yaml"))}


def load_study(name_or_path: str) -> dict:
    p = Path(name_or_path)
    if not p.exists():
        files = study_files()
        matches = [v for k, v in files.items() if k == name_or_path or k.split("_", 1)[-1] == name_or_path
                   or k.startswith(name_or_path)]
        if not matches:
            raise FileNotFoundError(f"study {name_or_path} not found; available: {', '.join(files)}")
        p = matches[0]
    s = yaml.safe_load(p.read_text())
    s["_file"] = str(p)
    return s


def points(study: dict) -> list[dict]:
    if "variants" in study:  # explicit list of labelled configurations
        return [{"variant": v["label"], **(v.get("set") or {})} for v in study["variants"]]
    scan = study.get("scan", {})
    keys = list(scan)
    if not keys:
        return [{}]
    if study.get("mode", "product") == "zip":
        combos = zip(*[scan[k] for k in keys])
    else:
        combos = itertools.product(*[scan[k] for k in keys])
    return [dict(zip(keys, c)) for c in combos]


def keys_of(study: dict) -> list[str]:
    return ["variant"] if "variants" in study else list(study.get("scan", {}))


def _label(v) -> str:
    return str(v).replace(" ", "").replace("/", "-")


def _numeric(v):
    """'2 mm' -> 2.0 for plotting (strings with units are converted to base units)."""
    if isinstance(v, (int, float)):
        return v
    for kind in ("length", "energy", "angle"):
        try:
            return C.quantity(v, kind)
        except ValueError:
            continue
    return v


# Analytic overlays drawn on study plots ------------------------------------
def _ref_reflectivity(df: pd.DataFrame, x: str, sdir: Path):
    """Specular mirror: photon trajectories do not depend on R, only their survival does.
    From the R = 1 run, every detected photon i with N_i wall reflections contributes R^N_i:
    LCE(R) = (1/N_emitted) * sum_i R^N_i. Exact up to statistics (needs photon_fraction = 1)."""
    import uproot
    r = df[x].astype(float)
    row = df.loc[r.idxmax()]
    if float(row[x]) < 1.0:
        return None
    f = uproot.open(sdir / row["run_dir"] / "srdet.root")
    n_coat = f["photons"]["n_coat_refl"].array(library="np")
    n_emitted = int(row["events"]) * int(row.get("photons_per_event", 1))
    xs = np.linspace(r.min(), 1.0, 200)
    lce = np.array([np.sum(R ** n_coat) for R in xs]) / n_emitted
    return {"lce": (xs, lce, "prediction Σ R$^{N_i}$ from the R = 1 trajectories")}


REFERENCES = {"reflectivity": _ref_reflectivity}


def run_study(name_or_path: str, quick: bool = False, analyze_only: Path | None = None,
              extra_sets: list[str] | None = None) -> Path:
    study = load_study(name_or_path)
    name = study["name"]
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    sdir = analyze_only or (runs_dir() / "studies" / f"{stamp}_{name}{'_quick' if quick else ''}")
    (sdir / "runs").mkdir(parents=True, exist_ok=True)
    (sdir / "study.yaml").write_text(yaml.safe_dump({k: v for k, v in study.items() if not k.startswith("_")},
                                                    sort_keys=False, allow_unicode=True))
    base = C.load(study["base"])
    for k, v in (study.get("set") or {}).items():
        C.set_path(base, k, v)
    if quick:
        for k, v in (study.get("quick") or {"run.events": 20}).items():
            C.set_path(base, k, v)
    base = C.apply_sets(base, extra_sets)
    if not quick:  # one backup per study (base config + scan definition), not one per point
        from .runner import backup_config
        backup_config({**base, "name": f"study_{name}", "study": {k: v for k, v in study.items()
                                                                    if not k.startswith("_")}})

    rows = []
    pts = points(study)
    for i, pt in enumerate(pts):
        cfg = C.deep_merge(base, {})
        for k, v in pt.items():
            if k != "variant":
                C.set_path(cfg, k, v)
        if "variant" in pt:
            label = _label(pt["variant"])
        else:
            label = "_".join(f"{k.split('.')[-1]}-{_label(v)}" for k, v in pt.items()) or "point"
        label = re.sub(r"[^A-Za-z0-9_.+-]", "", label)[:80]
        cfg["name"] = f"{name}__{label}"
        print(f"[srdet] study {name}: point {i + 1}/{len(pts)} {pt}")
        existing = sorted((sdir / "runs").glob(f"*_{cfg['name']}"))
        if analyze_only and existing:
            rdir, ok = existing[-1], (existing[-1] / "STATUS").read_text().startswith("ok")
            m = analyze_run(rdir) if ok else {}
        else:
            res = run(cfg, name=cfg["name"], parent=sdir / "runs", backup=False)
            rdir, ok = res.path, res.ok
            m = json.loads((rdir / "metrics.json").read_text()) if (rdir / "metrics.json").exists() else {}
        row = {k: _numeric(v) for k, v in pt.items()}
        if study.get("x_names"):  # display names for non-scalar scan values (e.g. spectra)
            row[study.get("x") or keys_of(study)[0]] = study["x_names"][i]
        row.update({"run_dir": str(rdir.relative_to(sdir)), "ok": ok})
        row.update({k: v for k, v in m.items() if not isinstance(v, (list, dict))})
        rows.append(row)

    pd.DataFrame(rows).to_csv(sdir / "results.csv", index=False)
    write_report(study, pd.read_csv(sdir / "results.csv"), sdir)  # same typed data as `srdet analyze`
    print(f"[srdet] study {name} done: {sdir}")
    return sdir


def write_report(study: dict, df: pd.DataFrame, sdir: Path) -> Path:
    keys = keys_of(study)
    x = study.get("x") or (keys[0] if keys else None)
    metrics = [m for m in study.get("metrics", []) if m in df]
    plots = []
    good = df[df["ok"]] if "ok" in df else df
    if x and metrics and len(good):
        overlays = None
        ref = study.get("reference")
        if ref in REFERENCES:
            overlays = REFERENCES[ref](good, x, sdir)
        plots.append(study_plot(good, x, metrics, sdir / "plots" / f"{study['name']}.png",
                                study.get("title", study["name"]), xlabel=study.get("xlabel", x),
                                series=study.get("series"), logx=study.get("logx", False),
                                labels=study.get("labels"), overlays=overlays))
        if study.get("process_fractions"):
            cols = ["first_phot", "first_compt", "first_Rayl", "first_conv", "first_none"]
            if all(c in good for c in cols):
                plots.append(stacked_fractions(good, x, cols, ["photoelectric", "Compton", "Rayleigh",
                                                               "pair production", "no interaction"],
                                               sdir / "plots" / f"{study['name']}_processes.png",
                                               f"{study.get('title', study['name'])}: first interaction",
                                               study.get("xlabel", x), logx=study.get("logx", True)))
        if study.get("process_counts"):
            plots.append(process_counts(good, x, sdir / "plots" / f"{study['name']}_process_counts.png",
                                        f"{study.get('title', study['name'])}: process frequency",
                                        study.get("xlabel", x)))
    cols = [c for c in (keys + metrics) if c in df]
    table = good[cols].to_markdown(index=False, floatfmt=".4g") if cols and len(good) else "(no successful runs)"
    (sdir / "results.md").write_text(table + "\n")

    lines = [f"# {study.get('title', study['name'])}", "", study.get("description", "").strip(), "",
             f"Base configuration: `{study.get('base')}`; fixed overrides: `{study.get('set') or {}}`", "",
             "## Results", "", table, ""]
    for p in plots:
        lines += [f"![{p.stem}](plots/{p.name})", ""]
    lines += ["## Automatic observations", ""] + observations(study, good, x, metrics)
    failed = df[~df["ok"]] if "ok" in df else df.iloc[0:0]
    if len(failed):
        lines += ["", "## Failed points", "", failed[keys + ["run_dir"]].to_markdown(index=False)]
    path = sdir / "report.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def observations(study: dict, df: pd.DataFrame, x: str | None, metrics: list[str]) -> list[str]:
    out = []
    if not x or not len(df):
        return out
    for met in metrics:
        if met not in df or df[met].isna().all():
            continue
        s = df[[x, met]].dropna()
        best = s.loc[s[met].idxmax()]
        worst = s.loc[s[met].idxmin()]
        out.append(f"- **{study.get('labels', {}).get(met, met)}**: max {best[met]:.4g} at {x} = {best[x]}, "
                   f"min {worst[met]:.4g} at {x} = {worst[x]} (ratio {best[met] / worst[met]:.3g})"
                   if worst[met] not in (0, 0.0) else
                   f"- **{met}**: max {best[met]:.4g} at {x} = {best[x]}, min 0 at {x} = {worst[x]}")
        xv = pd.to_numeric(s[x], errors="coerce")
        if xv.notna().all() and len(s) >= 3:
            rho = np.corrcoef(xv, s[met])[0, 1]
            trend = "increases" if rho > 0.5 else "decreases" if rho < -0.5 else "has no monotonic trend"
            out.append(f"  - {met} {trend} with {x} (Pearson r = {rho:.2f})")
    return out
