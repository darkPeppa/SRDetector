"""SRDetector web application: configure and launch simulations, studies and optimisations,
browse results (labelled plots, metrics, geometry), compare runs and read the documentation.

    srdet web [--host 0.0.0.0] [--port 8080]
    docker compose up web            ->  http://localhost:8080
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__, catalog
from .. import config as C
from ..paths import configs_dir, repo_root, runs_dir
from .jobs import JobManager
from .schema import form_schema

STATIC = Path(__file__).parent / "static"
FILE_ROOTS = ("runs", "results", "docs", "configs", "legacy", "README.md")
SKIP_RUN_DIRS = {"studies", "optimize", "web_jobs", "web_configs", "_spec_check"}
KEY_METRICS = ["e0_keV", "detection_efficiency", "photopeak_fraction", "k_escape_fraction", "lce", "lce_exit",
               "det_yield_per_keV", "resolution_fwhm_poisson_limit", "em_crosstalk", "optical_crosstalk",
               "psf_r50_um", "psf_in_cell_fraction", "mean_cells_hit", "t_det_median_ns",
               "snr_60keV_per_channel", "det_yield_per_cost", "wall_time_s"]
from ..labels import METRIC_LABELS  # noqa: E402  (shared with the Excel export)


def _clean(o: Any) -> Any:
    """JSON-safe: NaN / inf -> None, numpy scalars -> python."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item"):
        o = o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


def _rel(p: Path) -> str:
    return str(p.resolve().relative_to(repo_root().resolve()))


def _safe(rel: str) -> Path:
    root = repo_root().resolve()
    p = (root / rel).resolve()
    if not p.is_relative_to(root) or not any(p.is_relative_to(root / r) for r in FILE_ROOTS):
        raise HTTPException(403, "path outside the allowed folders")
    if not p.exists():
        raise HTTPException(404, f"{rel} not found")
    return p


def _plots(d: Path) -> list[dict]:
    out = []
    for p in sorted(list(d.glob("plots/*.png")) + list(d.glob("*.png"))):
        out.append({"path": _rel(p), "name": p.stem.replace("_", " ")})
    return out


def _run_summary(d: Path) -> dict:
    meta, m = _json(d / "meta.json"), _json(d / "metrics.json")
    status = (d / "STATUS").read_text().strip() if (d / "STATUS").exists() else "running?"
    cfg = {}
    if (d / "config.yaml").exists():
        try:
            cfg = yaml.safe_load((d / "config.yaml").read_text()) or {}
        except yaml.YAMLError:
            pass
    g, o, b = cfg.get("geometry", {}), cfg.get("optics", {}), cfg.get("beam", {})
    return {"path": _rel(d), "name": meta.get("name", d.name), "status": status,
            "started": meta.get("started"), "wall_time_s": meta.get("wall_time_s"),
            "mode": g.get("mode"), "length": g.get("length"), "coating": o.get("coating"),
            "core": g.get("core_material"), "sensor": g.get("sensor"),
            "beam": f"{b.get('particle', '')} {b.get('energy', '')} {b.get('type', '')}".strip(),
            "metrics": {k: m.get(k) for k in KEY_METRICS if k in m}}


SKINS = ("pink", "rap")


def create_app(jobs: JobManager | None = None, skin: str | None = None) -> FastAPI:
    app = FastAPI(title="SRDetector", version=__version__)
    if skin and skin not in SKINS:
        raise ValueError(f"unknown skin {skin}; available: {', '.join(SKINS)}")
    jm = jobs or JobManager()
    app.state.jobs = jm

    # ---------------- static UI and files
    @app.get("/", response_class=HTMLResponse)
    def index():
        html = (STATIC / "index.html").read_text()
        if skin:  # decorative skin: own stylesheet + vocabulary, applied by themes/skin.js
            html = html.replace("</head>", f'<link rel="stylesheet" href="/static/themes/{skin}.css">\n'
                                f'<script src="/static/themes/{skin}.js"></script>\n'
                                f'<script src="/static/themes/skin.js"></script>\n</head>')
        return html

    @app.get("/api/skin")
    def skin_info():
        if not skin:
            return {"name": None, "images": []}
        d = STATIC / "themes" / skin / "user"
        imgs = sorted(p for p in d.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif"))
        return {"name": skin, "images": [f"/static/themes/{skin}/user/{p.name}" for p in imgs]}

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.middleware("http")
    async def no_stale_ui(request, call_next):
        resp = await call_next(request)
        if request.url.path.startswith("/static") or request.url.path == "/":
            resp.headers["Cache-Control"] = "no-cache"  # always revalidate the UI after an update
        return resp

    @app.get("/files/{rel:path}")
    def files(rel: str):
        return FileResponse(_safe(rel))

    # ---------------- catalogue, schema, configs
    @app.get("/api/info")
    def info():
        return {"version": __version__, "repo": str(repo_root()), "metric_labels": METRIC_LABELS,
                "key_metrics": KEY_METRICS}

    @app.get("/api/catalog")
    def get_catalog():
        return {"scintillators": catalog.SCINTILLATORS, "glasses": catalog.GLASSES, "coatings": catalog.COATINGS,
                "sensors": {k: {"description": v[0], "fill": v[1], "pixel_mm": v[2], "read_noise": v[3],
                                "cost": v[4]} for k, v in catalog.SENSORS.items()}}

    @app.get("/api/schema")
    def schema():
        return form_schema()

    @app.get("/api/configs")
    def configs():
        out = []
        for p in sorted((configs_dir() / "detector").glob("*.yaml")):
            d = yaml.safe_load(p.read_text()) or {}
            out.append({"name": p.stem, "description": d.get("description", "")})
        return out

    @app.get("/api/configs/{name}")
    def config(name: str):
        cfg = C.load(f"{name}.yaml" if not name.endswith(".yaml") else name)
        return _clean({k: v for k, v in cfg.items() if not k.startswith("_")})

    def _write_config(base: str, overrides: dict, name: str) -> Path:
        d = runs_dir() / "web_configs"
        d.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name or base)[:60]
        doc = {"extends": str((configs_dir() / "detector" / f"{base}.yaml").resolve()), "name": safe}
        for k, v in overrides.items():
            C.set_path(doc, k, v)
        path = d / f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}_{safe}.yaml"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
        return path

    def _set_arg(key: str, value) -> str:
        if not re.fullmatch(r"[A-Za-z_][\w.]*", str(key)):
            raise HTTPException(400, f"bad override key {key!r}")
        # JSON is valid YAML: None -> null, True -> true, dicts / lists keep their structure
        return f"{key}={value if isinstance(value, str) else json.dumps(value)}"

    def _write_spec(spec: dict) -> Path:
        d = runs_dir() / "web_configs" / "optimize"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}_{spec['name']}.yaml"
        path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
        return path

    @app.post("/api/macro")
    def macro(body: dict = Body(...)):
        from ..macro import render
        cfg = C.load(f"{body.get('base', 'full')}.yaml")
        for k, v in (body.get("overrides") or {}).items():
            C.set_path(cfg, k, v)
        try:
            return {"macro": render(cfg, Path("<run folder>"))}
        except Exception as e:  # show configuration errors in the UI
            raise HTTPException(400, str(e))

    # ---------------- jobs
    @app.post("/api/jobs")
    def submit(body: dict = Body(...)):
        kind = body.get("kind")
        name = body.get("name") or ""
        quick = ["--quick"] if body.get("quick") else []
        archive = ["--archive"] if body.get("archive") else []
        meta = {}
        if kind in ("run", "vis"):
            if body.get("config_path"):
                cfg_path = _safe(body["config_path"])
                meta["source_run"] = str(Path(body["config_path"]).parent) if kind == "vis" else None
            else:
                cfg_path = _write_config(body.get("base", "full"), body.get("overrides") or {}, name)
            args = [kind, str(cfg_path)]
            if body.get("events"):
                args += ["--events", str(int(body["events"]))]
            if kind == "run":
                args += archive
            title = f"{kind}: {name or cfg_path.stem}"
        elif kind == "optimize" and body.get("spec"):  # spec built in the constructor of the UI
            from ..optimize import check_spec
            spec = body["spec"]
            if not isinstance(spec, dict):
                raise HTTPException(400, "spec must be an object")
            chk = check_spec(spec, quick=bool(quick))
            if not chk["ok"]:
                raise HTTPException(400, "; ".join(chk["errors"]))
            path = _write_spec(spec)
            args = [kind, str(path), *quick, *archive]
            meta["spec_file"] = _rel(path)
            title = f"optimize: {spec['name']}{' (quick)' if quick else ''}"
        elif kind in ("study", "optimize"):
            target = body.get("target")
            if not target or not re.fullmatch(r"[A-Za-z0-9_]+", target):
                raise HTTPException(400, "target required")
            sets = [a for k, v in (body.get("overrides") or {}).items() for a in ("--set", _set_arg(k, v))]
            args = [kind, target, *quick, *archive, *sets]
            title = f"{kind}: {target}{' (quick)' if quick else ''}"
        elif kind == "tracks":  # short re-run of a run's configuration that stores trajectories for 3D
            cfg_path = _safe(body["config_path"])
            n = max(1, min(int(body.get("events", 20)), 500))
            src = str(Path(body["config_path"]).parent)
            args = ["run", str(cfg_path), "--events", str(n), "--set", f"run.tracks={n}",
                    "--name", re.sub(r"^\d{8}-\d{6}_", "", Path(src).name)[:40] + "_3d"]
            meta["source_run"] = src
            title = f"3D-треки: {Path(src).name}"
        elif kind == "scan":
            d = _safe(body["path"])
            alias = body.get("alias", "")
            if not re.fullmatch(r"[A-Za-z_]\w*", alias):
                raise HTTPException(400, "alias required")
            args = ["optimize", "--resume", str(d), "--scan", alias, "--points", str(int(body.get("points", 6)))]
            if body.get("events"):
                args += ["--events", str(int(body["events"]))]
            title = f"scan {alias}: {d.name}"
        elif kind == "validate":
            args = ["validate", *quick]
            title = f"physics validation{' (quick)' if quick else ''}"
        elif kind == "archive":
            args = ["archive", str(_safe(body["path"]))]
            title = f"archive: {body['path']}"
        else:
            raise HTTPException(400, f"unknown job kind {kind}")
        return jm.submit(kind, args, title, meta)

    @app.get("/api/jobs")
    def list_jobs():
        return [jm.get(j["id"], tail=3) for j in jm.list()[:100]]

    @app.get("/api/jobs/{jid}")
    def job(jid: str, tail: int = 300):
        j = jm.get(jid, tail)
        if not j:
            raise HTTPException(404)
        return j

    @app.post("/api/jobs/{jid}/cancel")
    def cancel(jid: str):
        return {"cancelled": jm.cancel(jid)}

    # ---------------- runs
    @app.get("/api/runs")
    def runs(limit: int = 200):
        base = runs_dir()
        root = repo_root().resolve()
        dirs = [d for d in base.glob("*") if d.is_dir() and d.name not in SKIP_RUN_DIRS
                and d.resolve().is_relative_to(root)]  # only folders the file API may serve
        dirs.sort(key=lambda d: d.name, reverse=True)
        return _clean([_run_summary(d) for d in dirs[:limit]])

    @app.get("/api/run")
    def run(path: str = Query(...)):
        d = _safe(path)
        m = _json(d / "metrics.json")
        vis = [v for v in json.loads((d / "vis.json").read_text())] if (d / "vis.json").exists() else []
        vis_plots = [p for v in vis if (repo_root() / v).exists() for p in _plots(repo_root() / v)
                     if not p["path"].count("/plots/")]
        tracks = [d / "tracks.jsonl"] + [repo_root() / v / "tracks.jsonl" for v in reversed(vis)]
        tracks_src = next((t for t in tracks if t.exists()), None)
        files = [{"path": _rel(f), "size": f.stat().st_size} for f in sorted(d.iterdir()) if f.is_file()]
        cfg = yaml.safe_load((d / "config.yaml").read_text()) if (d / "config.yaml").exists() else {}
        return _clean({**_run_summary(d), "metrics_all": {k: v for k, v in m.items()
                                                          if not isinstance(v, (list, dict))},
                       "sanity": m.get("sanity_problems", []), "meta": _json(d / "meta.json"),
                       "config_yaml": (d / "config.yaml").read_text() if (d / "config.yaml").exists() else "",
                       "config": {k: v for k, v in (cfg or {}).items() if not k.startswith("_")},
                       "config_sources": (cfg or {}).get("_sources", []),
                       "macro": (d / "run.mac").read_text() if (d / "run.mac").exists() else "",
                       "plots": [p for p in _plots(d) if "/plots/" in p["path"]],
                       "pictures": [p for p in _plots(d) if "/plots/" not in p["path"]] + vis_plots,
                       "files": files, "has_root": (d / "srdet.root").exists(),
                       "tracks_run": _rel(tracks_src.parent) if tracks_src else None,
                       "log_tail": "\n".join((d / "log.txt").read_text(errors="replace").splitlines()[-60:])
                       if (d / "log.txt").exists() else ""})

    @app.get("/api/run/geometry")
    def run_geometry(path: str = Query(...)):
        d = _safe(path)
        g = _json(d / "geometry.json")
        if not g:
            raise HTTPException(404, "no geometry.json")
        cfg = yaml.safe_load((d / "config.yaml").read_text()) if (d / "config.yaml").exists() else {}
        return _clean({**g, "config_geometry": cfg.get("geometry", {}), "config_optics": cfg.get("optics", {})})

    @app.get("/api/run/hist")
    def run_hist(path: str = Query(...), name: str = Query(...)):
        """One histogram of srdet.root as arrays (for overlays in the UI)."""
        import uproot
        d = _safe(path)
        f = uproot.open(d / "srdet.root")
        if name not in [k.split(";")[0] for k in f.keys()]:
            raise HTTPException(404, f"no histogram {name}")
        h = f[name]
        vals, *edges = h.to_numpy()
        axes = [str(h.member(a).member("fTitle")) for a in ("fXaxis", "fYaxis") if h.has_member(a)]
        return _clean({"name": name, "title": h.title, "axes": axes, "values": vals.tolist(),
                       "edges": [e.tolist() for e in edges], "entries": float(vals.sum())})

    @app.post("/api/compare")
    def compare(body: dict = Body(...)):
        rows = []
        for p in body.get("paths", []):
            d = _safe(p)
            rows.append({"path": p, "name": _json(d / "meta.json").get("name", d.name),
                         **{k: v for k, v in _json(d / "metrics.json").items() if not isinstance(v, (list, dict))}})
        return _clean(rows)

    @app.delete("/api/run")
    def delete_run(path: str = Query(...)):
        d = _safe(path)
        if not d.is_relative_to(runs_dir().resolve()) or d == runs_dir().resolve():
            raise HTTPException(403, "only runs/ entries can be deleted")
        shutil.rmtree(d)
        return {"deleted": path}

    # ---------------- studies
    @app.get("/api/studies")
    def studies():
        from ..studies import points, study_files
        specs = []
        for name, p in study_files().items():
            s = yaml.safe_load(p.read_text()) or {}
            scan = s.get("scan") or {"вариант": [v["label"] for v in s.get("variants", [])]}
            specs.append({"name": name, "title": s.get("title", ""), "description": s.get("description", ""),
                          "explain": s.get("explain") or {}, "base": s.get("base"), "set": s.get("set") or {},
                          "scan": scan, "x_names": s.get("x_names"), "mode": s.get("mode", "product"),
                          "n_points": len(points(s)), "derived": s.get("derived") or {},
                          "metrics": s.get("metrics", []), "labels": s.get("labels") or {}})
        done = []
        for root in (runs_dir() / "studies", repo_root() / "results" / "studies"):
            for d in sorted(root.glob("*"), reverse=True):
                if (d / "report.md").exists():
                    done.append({"path": _rel(d), "name": d.name, "collected": "results" in _rel(d)})
        return {"specs": specs, "results": done}

    @app.get("/api/study")
    def study(path: str = Query(...)):
        d = _safe(path)
        rows = pd.read_csv(d / "results.csv").to_dict("records") if (d / "results.csv").exists() else []
        return _clean({"path": path, "report": (d / "report.md").read_text(), "rows": rows,
                       "spec": yaml.safe_load((d / "study.yaml").read_text()) if (d / "study.yaml").exists() else {},
                       "plots": _plots(d)})

    # ---------------- optimisation
    @app.get("/api/optimizations")
    def optimizations():
        from ..optimize import spec_files
        specs = []
        for name, p in spec_files().items():
            s = yaml.safe_load(p.read_text()) or {}
            specs.append({"name": name, "title": s.get("title", ""), "description": s.get("description", ""),
                          "space": s.get("space", {}), "objective": s.get("objective", {}),
                          "constraints": s.get("constraints", []), "spec": s})
        done = []
        for d in sorted((runs_dir() / "optimize").glob("*"), reverse=True):
            # a search that has just started has spec.yaml but no trials yet: list it as running
            if not d.is_dir() or not ((d / "trials.csv").exists() or (d / "spec.yaml").exists()):
                continue
            fin = pd.read_csv(d / "final.csv") if (d / "final.csv").exists() else None
            best = _clean(fin.iloc[0].to_dict()) if fin is not None and len(fin) else None
            spec = yaml.safe_load((d / "spec.yaml").read_text()) if (d / "spec.yaml").exists() else {}
            done.append({"path": _rel(d), "name": d.name, "title": spec.get("title", ""),
                         "finished": (d / "report.md").exists(), "best": best,
                         "progress": _json(d / "progress.json"),
                         "aliases": list((spec.get("space") or {}).keys()),
                         "objective": (spec.get("objective") or {}).get("expr")})
        return {"specs": specs, "results": done}

    @app.get("/api/optimize/meta")
    def optimize_meta():
        """Everything the optimisation constructor needs: metrics with meaning and direction,
        configurable parameters (from defaults.yaml) and base configurations."""
        from ..labels import METRIC_HELP
        from ..optimize import DEFAULT_QUICK, SAMPLER_TEXT, SAFE
        fields = [f for sec in form_schema()["sections"] for f in sec["fields"]
                  if f["kind"] in ("quantity", "int", "float", "choice", "bool", "string")]
        metrics = [{"name": k, "label": METRIC_LABELS.get(k, k), "help": h, "better": b}
                   for k, (h, b) in METRIC_HELP.items()]
        return {"metrics": metrics, "fields": fields, "samplers": SAMPLER_TEXT, "quick_default": DEFAULT_QUICK,
                "functions": [k for k, v in SAFE.items() if callable(v)],
                "bases": [c["name"] + ".yaml" for c in configs()]}

    @app.post("/api/optimize/check")
    def optimize_check(body: dict = Body(...)):
        from ..optimize import check_spec
        spec = body.get("spec")
        if not isinstance(spec, dict):
            raise HTTPException(400, "spec must be an object")
        try:
            res = check_spec(spec, quick=bool(body.get("quick")))
        except Exception as e:  # malformed input from the editor: report, do not crash
            res = {"ok": False, "errors": [f"{type(e).__name__}: {e}"], "warnings": [],
                   "plan": {"steps": [], "sims": 0, "events": 0}}
        res["yaml"] = yaml.safe_dump(spec, sort_keys=False, allow_unicode=True)
        return _clean(res)

    @app.post("/api/optimize/save")
    def optimize_save(body: dict = Body(...)):
        """Store a constructor spec as configs/optimize/<name>.yaml (a new preset)."""
        from ..optimize import check_spec
        spec = body.get("spec")
        if not isinstance(spec, dict):
            raise HTTPException(400, "spec must be an object")
        chk = check_spec(spec)
        if not chk["ok"]:
            raise HTTPException(400, "; ".join(chk["errors"]))
        path = configs_dir() / "optimize" / f"{spec['name']}.yaml"
        if path.exists() and not body.get("overwrite"):
            raise HTTPException(409, f"{_rel(path)} уже существует")
        path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
        return {"path": _rel(path)}

    @app.get("/api/optimization")
    def optimization(path: str = Query(...)):
        from ..optimize import check_spec
        d = _safe(path)
        spec = yaml.safe_load((d / "spec.yaml").read_text()) if (d / "spec.yaml").exists() else {}
        trials = pd.read_csv(d / "trials.csv").to_dict("records") if (d / "trials.csv").exists() else []
        final = pd.read_csv(d / "final.csv").to_dict("records") if (d / "final.csv").exists() else []
        try:
            plan = check_spec(spec)["plan"] if spec else None
        except Exception:  # an old / hand-edited spec must not break the page
            plan = None
        return _clean({"path": path, "spec": spec, "trials": trials, "final": final, "plan": plan,
                       "progress": _json(d / "progress.json"), "finished": (d / "report.md").exists(),
                       "report": (d / "report.md").read_text() if (d / "report.md").exists() else "",
                       "best_yaml": (d / "best.yaml").read_text() if (d / "best.yaml").exists() else "",
                       "best_path": _rel(d / "best.yaml") if (d / "best.yaml").exists() else None,
                       "plots": _plots(d)})

    # ---------------- analytic cross-checks (NIST XCOM, simple laws)
    @app.get("/api/estimates")
    def estimates(path: str = Query(...)):
        """Run folder: list of checks. Study / optimisation folder: expected values per simulated
        point (for the approximation overlay) and how many points each check passes; for an
        optimisation also the checks of the best validated run."""
        from .. import estimates as E
        d = _safe(path)
        if (d / "metrics.json").exists() and (d / "config.yaml").exists():
            checks = E.checks_for_dir(d)
            return _clean({"kind": "run", "checks": checks, "summary": E.summary(checks)})
        table = d / "trials.csv" if (d / "trials.csv").exists() else d / "results.csv"
        if not table.exists():
            return {"kind": "none", "points": {}}
        rows = pd.read_csv(table).to_dict("records")
        points = E.point_estimates(d, rows)
        per_check: dict[str, dict] = {}
        for est in points.values():
            for metric, e in est.items():
                s = per_check.setdefault(e["id"], {"metric": metric, "title": e["title"], "ok": 0, "warn": 0, "bad": 0})
                s[e["status"]] = s.get(e["status"], 0) + 1
        out = {"kind": "optimization" if table.name == "trials.csv" else "study", "points": points,
               "per_check": per_check}
        if table.name == "trials.csv":
            spec = yaml.safe_load((d / "spec.yaml").read_text()) if (d / "spec.yaml").exists() else {}
            aliases = list((spec.get("space") or {}).keys())
            fin = pd.read_csv(d / "final.csv").to_dict("records") if (d / "final.csv").exists() else []

            def same(a, b):
                try:
                    return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-12)
                except (TypeError, ValueError):
                    return str(a) == str(b)
            best = next((r for r in rows if fin and str(r.get("stage", "")).startswith("final")
                         and isinstance(r.get("run_dir"), str) and all(same(r.get(a), fin[0].get(a)) for a in aliases)),
                        None)
            if best is None:
                feas = [r for r in rows if r.get("feasible") and isinstance(r.get("run_dir"), str)]
                best = max(feas, key=lambda r: r.get("events", 0)) if feas else None
            if best is not None:
                checks = E.checks_for_dir(d / best["run_dir"])
                out.update({"best_run": best["run_dir"], "checks": checks, "summary": E.summary(checks)})
        return _clean(out)

    @app.get("/api/run/theory")
    def run_theory(path: str = Query(...)):
        """Histograms of a run with the theory curves / lines drawn over them (srdet/theory.py)."""
        from ..theory import run_theory as rt
        return _clean(rt(_safe(path)))

    def _latest_study(name: str) -> Path | None:
        cands = [d for d in (runs_dir() / "studies").glob(f"*_{name}") if (d / "results.csv").exists()]
        return sorted(cands)[-1] if cands else None

    @app.get("/api/verify/length")
    def verify_length(energy: float = 60.0, coating: str = "Ag", sensor_qe: bool = True):
        """Why the channel length matters: NIST absorption and the channel model versus the
        simulated studies U04 (light collection) and U04c (X-rays, signal per incident keV)."""
        import numpy as np
        from .. import estimates as E_
        from .. import theory as T
        if coating not in T.METAL_NK and coating not in ("ideal", "mirror"):
            raise HTTPException(400, "coating: Al, Ag, Au, ideal")
        if not 5 <= energy <= 5000:
            raise HTTPException(400, "energy 5 .. 5000 keV")
        u04, u04c = _latest_study("U04_length"), _latest_study("U04c_length_xray")
        qe, qe_src = 1.0, "идеальный сенсор"
        sim_x = []
        if u04c is not None:
            df = pd.read_csv(u04c / "results.csv")
            df = df[df["ok"].astype(bool)] if "ok" in df else df
            energies = sorted(set(float(e) for e in df["beam.energy"]))
            sel = df[np.isclose(df["beam.energy"].astype(float), energy)]
            sim_x = sel.sort_values("geometry.length")[["geometry.length", "detection_efficiency", "det_yield_per_keV",
                                                       "pe_per_incident_keV", "run_dir"]].to_dict("records")
            if sensor_qe and len(df):
                g = _json(u04c / str(df.iloc[0]["run_dir"]) / "geometry.json")
                if g.get("sensor_efficiency"):
                    se = g["sensor_efficiency"]
                    qe = T.emission_weighted_qe("CsI_Tl", (se["energy_eV"], se["efficiency"]))
                    qe_src = f"{g.get('sensor')}: QE, усреднённая по спектру CsI(Tl)"
        else:
            energies = []
        lengths = np.geomspace(0.05, 100, 90)
        model = T.length_model(energy, coating, lengths, qe=qe)
        sim_lce, model_lce = {}, {}
        if u04 is not None:
            df = pd.read_csv(u04 / "results.csv")
            for coat, grp in df.groupby("optics.coating"):
                grp = grp.sort_values("geometry.length")
                sim_lce[coat] = {"L": grp["geometry.length"].tolist(), "lce": grp["lce"].tolist(),
                                 "refl": grp["mean_refl_det"].tolist()}
        for coat in ("Al", "Ag", "Au", "ideal"):
            m = T.length_model(energy, coat, lengths, qe=qe)
            model_lce[coat] = m["lce_uniform"]
        # light collection versus emission depth in a 30 mm channel (study U03) and the model
        u03, sim_depth, model_depth = _latest_study("U03_emission_depth"), {}, {}
        if u03 is not None:
            df = pd.read_csv(u03 / "results.csv")
            length = 30.0
            zs = np.linspace(-length / 2, length / 2, 120)
            lam = T.EMISSION["CsI_Tl"][0]
            n_core = E_.refractive_index(*E_.SCINT["CsI_Tl"][3:5], lam)
            n_out = E_.refractive_index(*E_.COUPLING_N["OpticalGrease"], lam)
            for coat, grp in df.groupby("optics.coating"):
                grp = grp.sort_values("beam.optical.z")
                sim_depth[coat] = {"z": grp["beam.optical.z"].tolist(), "lce": grp["lce"].tolist()}
                if coat in T.METAL_NK:
                    model_depth[coat] = {"z": zs.tolist(),
                                         "lce": T.channel_lce(zs + length / 2, length, 0.2, coat, n_core, n_out, lam).tolist()}
        return _clean({"energy": energy, "coating": coating, "model": model, "model_lce_uniform": model_lce,
                       "sim_xray": sim_x, "sim_lce": sim_lce, "sim_depth": sim_depth, "model_depth": model_depth, "energies_simulated": energies, "qe": qe,
                       "qe_source": qe_src,
                       "studies": {"U03": _rel(u03) if u03 else None, "U04": _rel(u04) if u04 else None,
                                   "U04c": _rel(u04c) if u04c else None}})

    @app.get("/api/verify/summary")
    def verify_summary():
        """For the newest result of every study and optimisation: how many simulated points
        agree with each analytic estimate."""
        from .. import estimates as E
        from ..studies import study_files
        rows = []
        targets = [(n, _latest_study(n), "study") for n in study_files()]
        opt_dirs = {}
        for d in sorted((runs_dir() / "optimize").glob("*")):
            if (d / "trials.csv").exists() and not d.name.endswith("_quick"):
                opt_dirs[re.sub(r"^\d{8}-\d{6}_", "", d.name)] = d
        targets += [(n, d, "optimization") for n, d in opt_dirs.items()]
        for name, d, kind in targets:
            if d is None:
                rows.append({"name": name, "kind": kind, "path": None, "checks": {}})
                continue
            table = d / ("trials.csv" if kind == "optimization" else "results.csv")
            pts = E.point_estimates(d, pd.read_csv(table).to_dict("records"))
            checks: dict = {}
            for est in pts.values():
                for e in est.values():
                    c = checks.setdefault(e["id"], {"title": e["title"], "ok": 0, "warn": 0, "bad": 0})
                    c[e["status"]] += 1
            rows.append({"name": name, "kind": kind, "path": _rel(d), "points": len(pts), "checks": checks})
        return _clean(rows)

    # ---------------- results archive + docs
    @app.get("/api/export")
    def export_dir(path: str = Query(...), fmt: str = "xlsx"):
        """Readable download of a run / study / optimisation (built on demand into <dir>/export/)."""
        from ..export import export
        if fmt not in ("xlsx", "zip"):
            raise HTTPException(400, "fmt: xlsx | zip")
        d = _safe(path)
        out = export(d, fmt)
        media = "application/zip" if fmt == "zip" else \
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return FileResponse(out, media_type=media, filename=out.name)

    @app.get("/api/archives")
    def archives():
        res = repo_root() / "results"
        return [{"path": _rel(p), "name": p.name, "size_MB": round(p.stat().st_size / 1e6, 2)}
                for p in sorted(res.glob("*.tar.xz"), reverse=True)]

    @app.get("/api/docs")
    def docs():
        items = [{"path": "README.md", "title": "README"}]
        guide = repo_root() / "docs" / "user_guide.md"
        docs_md = sorted((repo_root() / "docs").glob("*.md"), key=lambda p: (p != guide, p.name))
        for p in docs_md:
            first = next((l for l in p.read_text().splitlines() if l.startswith("# ")), p.stem)
            items.append({"path": _rel(p), "title": first.lstrip("# ").strip()})
        items.append({"path": "legacy/README.md", "title": "Legacy"})
        if (repo_root() / "results/studies/README.md").exists():
            items.append({"path": "results/studies/README.md", "title": "Отчёты исследований"})
        return items

    @app.get("/api/doc")
    def doc(path: str = Query(...)):
        p = _safe(path)
        if p.suffix != ".md":
            raise HTTPException(400, "markdown only")
        return {"path": path, "markdown": p.read_text()}

    @app.exception_handler(FileNotFoundError)
    def not_found(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    return app


def main(host: str = "0.0.0.0", port: int = 8080, skin: str | None = None):
    import uvicorn
    uvicorn.run(create_app(skin=skin), host=host, port=port, log_level="info")
