"""srdet - command line front-end.

  srdet run CONFIG [--set key=value ...] [--events N] [--archive]   custom run
  srdet study NAME [--quick] [--archive]                            automatic experiment (configs/studies)
  srdet study --list | srdet study all [--quick]
  srdet analyze RUN_DIR                                             (re)compute metrics + plots
  srdet compare RUN_DIR RUN_DIR ...                                 table of metrics
  srdet archive RUN_OR_STUDY_DIR                                    pack into results/ for git
  srdet list                                                        recent runs and their status
  srdet catalog [materials|coatings|sensors]                        what can be configured
  srdet macro CONFIG                                                print the generated macro
  srdet vis CONFIG                                                  geometry pictures (VRML + PNG)
  srdet jsroot PATH.root                                            browse a ROOT file in the browser
  srdet shell                                                       interactive Geant4 session
  srdet validate [--quick]                                          physics sanity tests (pytest)
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import socketserver
import subprocess
import sys
from pathlib import Path

from . import catalog
from . import config as C


def _cfg(args) -> dict:
    cfg = C.load(args.config)
    cfg = C.apply_sets(cfg, args.set)
    if getattr(args, "events", None):
        cfg["run"]["events"] = args.events
    if getattr(args, "threads", None) is not None:
        cfg["run"]["threads"] = args.threads
    if getattr(args, "name", None):
        cfg["name"] = args.name
    return cfg


def cmd_run(args) -> int:
    from .archive import pack
    from .runner import run
    res = run(_cfg(args), analyze=not args.no_analyze)
    if res.ok and args.archive:
        pack(res.path)
    return 0 if res.ok else 1


def cmd_study(args) -> int:
    from .archive import pack
    from .studies import run_study, study_files
    if args.list or not args.names:
        for k, p in study_files().items():
            import yaml
            s = yaml.safe_load(p.read_text())
            print(f"{k:28s} {s.get('title', '')}")
        return 0
    names = list(study_files()) if args.names == ["all"] else args.names
    failed = []
    for n in names:
        try:
            d = run_study(n, quick=args.quick, extra_sets=args.set)
            if args.archive:
                pack(d)
        except Exception as e:  # one broken study must not stop the others
            print(f"[srdet] study {n} FAILED: {e}")
            failed.append(n)
    if failed:
        print(f"[srdet] failed studies: {', '.join(failed)}")
    return 1 if failed else 0


def cmd_analyze(args) -> int:
    from .analysis import analyze_run
    from .studies import load_study, write_report
    p = Path(args.path)
    if (p / "study.yaml").exists():
        import pandas as pd
        study = load_study(str(p / "study.yaml"))
        write_report(study, pd.read_csv(p / "results.csv"), p)
        print(f"report: {p / 'report.md'}")
        return 0
    m = analyze_run(p)
    print(json.dumps({k: v for k, v in m.items() if not isinstance(v, (list, dict))}, indent=1, default=float))
    return 0


def cmd_compare(args) -> int:
    import pandas as pd
    rows = []
    for d in args.runs:
        mf = Path(d) / "metrics.json"
        if not mf.exists():
            from .analysis import analyze_run
            analyze_run(d, plots=False)
        m = json.loads(mf.read_text())
        rows.append({k: v for k, v in m.items() if not isinstance(v, (list, dict))})
    df = pd.DataFrame(rows).set_index("name")
    cols = args.metrics.split(",") if args.metrics else [c for c in [
        "e0_keV", "detection_efficiency", "photopeak_fraction", "k_escape_fraction", "lce", "lce_exit",
        "det_yield_per_keV", "resolution_fwhm_poisson_limit", "em_crosstalk", "optical_crosstalk",
        "snr_60keV_per_channel", "det_yield_per_cost", "wall_time_s"] if c in df]
    print(df[cols].T.to_markdown(floatfmt=".4g"))
    if args.out:
        df.to_csv(args.out)
    return 0


def cmd_archive(args) -> int:
    from .archive import pack
    for p in args.paths:
        pack(p, budget_mb=args.budget, force=args.force)
    return 0


def cmd_list(args) -> int:
    from .paths import runs_dir
    base = runs_dir()
    for d in sorted(base.glob("*"))[-args.n:]:
        s = (d / "STATUS").read_text().strip() if (d / "STATUS").exists() else "-"
        print(f"{d.name:60s} {s}")
    return 0


def cmd_catalog(args) -> int:
    what = args.what or "all"
    if what in ("all", "materials"):
        print("Scintillators (yield ph/MeV, slow decay ns, peak nm):")
        for k, v in catalog.SCINTILLATORS.items():
            print(f"  {k:14s} {v}")
        print("Glasses:", ", ".join(catalog.GLASSES))
        print("Other:", ", ".join(catalog.OTHER_MATERIALS), "+ any Geant4 NIST material (G4_*)")
    if what in ("all", "coatings"):
        print("Coatings:")
        for k, v in catalog.COATINGS.items():
            print(f"  {k:12s} {v}")
    if what in ("all", "sensors"):
        print("Sensors (description, fill factor, pixel mm, read noise e-, relative cost):")
        for k, v in catalog.SENSORS.items():
            print(f"  {k:13s} {v}")
    return 0


def cmd_macro(args) -> int:
    from .macro import render
    print(render(_cfg(args), Path("OUT")))
    return 0


def cmd_vis(args) -> int:
    from .runner import run
    cfg = _cfg(args)
    cfg["run"]["events"] = args.events
    cfg["run"]["threads"] = 1
    from .macro import detector_radius
    from .paths import repo_root
    vis = repo_root() / "macros" / "vis"
    # the scene extent is a sphere around the matrix: zoom so that the cross-section fills the front view
    half_len = C.quantity(cfg["geometry"]["length"], "length") / 2
    zoom = max(1.0, 0.9 * (half_len ** 2 + detector_radius(cfg) ** 2) ** 0.5 / detector_radius(cfg))
    cfg["run"]["extra_commands"] = list(cfg["run"].get("extra_commands", [])) + [
        f"/control/alias srdetFrontZoom {zoom:.3f}", f"/control/execute {vis}/offscreen.mac"]
    cfg["run"]["post_commands"] = list(cfg["run"].get("post_commands", [])) + [f"/control/execute {vis}/offscreen_post.mac"]
    res = run(cfg, name=f"vis_{cfg.get('name')}", analyze=False)
    print(f"pictures in {res.path}")
    return 0 if res.ok else 1


def cmd_jsroot(args) -> int:
    """Serve JSROOT (loaded from a CDN in the browser) next to the ROOT file: no ROOT install needed."""
    p = Path(args.path).resolve()
    root_dir = p.parent
    page = root_dir / "jsroot.html"
    page.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><title>{p.name}</title>
<script type="module">
import {{ buildGUI }} from 'https://cdn.jsdelivr.net/npm/jsroot@7.7.4/modules/gui.mjs';
buildGUI('gui').then(h => h.openRootFile('{p.name}'));
</script></head><body><div id="gui" style="position:absolute;inset:0"></div></body></html>""")
    os.chdir(root_dir)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", args.port), handler) as httpd:
        print(f"open http://localhost:{args.port}/jsroot.html  (Ctrl+C to stop)")
        httpd.serve_forever()
    return 0


def cmd_shell(args) -> int:
    from .paths import sim_binary
    return subprocess.call([sim_binary()])


def cmd_validate(args) -> int:
    from .paths import repo_root
    env = dict(os.environ)
    if args.quick:
        env["SRDET_QUICK"] = "1"
    return subprocess.call([sys.executable, "-m", "pytest", "-v", str(repo_root() / "tests")] + args.pytest, env=env)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="srdet", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_cfg(p):
        p.add_argument("config", help="YAML config (configs/detector/*.yaml) ")
        p.add_argument("--set", action="append", default=[], help="override, e.g. geometry.length=10mm")
        p.add_argument("--name")

    p = sub.add_parser("run", help="custom run of one configuration")
    add_cfg(p)
    p.add_argument("--events", type=int)
    p.add_argument("--threads", type=int)
    p.add_argument("--no-analyze", action="store_true")
    p.add_argument("--archive", action="store_true", help="pack into results/ if successful")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("study", help="automatic experiment from configs/studies")
    p.add_argument("names", nargs="*", help="study names, or 'all'")
    p.add_argument("--list", action="store_true")
    p.add_argument("--quick", action="store_true", help="low statistics (CI)")
    p.add_argument("--archive", action="store_true")
    p.add_argument("--set", action="append", default=[])
    p.set_defaults(fn=cmd_study)

    p = sub.add_parser("analyze", help="metrics and plots of a run (or a study report)")
    p.add_argument("path")
    p.set_defaults(fn=cmd_analyze)

    p = sub.add_parser("compare", help="compare runs")
    p.add_argument("runs", nargs="+")
    p.add_argument("--metrics")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("archive", help="pack successful runs/studies into results/")
    p.add_argument("paths", nargs="+")
    p.add_argument("--budget", type=float, default=45.0, help="max archive size in MB")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_archive)

    p = sub.add_parser("list", help="recent runs")
    p.add_argument("-n", type=int, default=30)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("catalog", help="materials, coatings, sensors")
    p.add_argument("what", nargs="?", choices=["materials", "coatings", "sensors"])
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("macro", help="print the macro generated for a config")
    add_cfg(p)
    p.set_defaults(fn=cmd_macro)

    p = sub.add_parser("vis", help="geometry / track pictures")
    add_cfg(p)
    p.add_argument("--events", type=int, default=5)
    p.set_defaults(fn=cmd_vis)

    p = sub.add_parser("jsroot", help="browse a ROOT file with JSROOT")
    p.add_argument("path")
    p.add_argument("--port", type=int, default=8090)
    p.set_defaults(fn=cmd_jsroot)

    p = sub.add_parser("shell", help="interactive Geant4 terminal")
    p.set_defaults(fn=cmd_shell)

    p = sub.add_parser("validate", help="run physics sanity tests")
    p.add_argument("--quick", action="store_true")
    p.set_defaults(fn=cmd_validate)

    args, extra = ap.parse_known_args(argv)
    if extra and args.cmd != "validate":
        ap.error(f"unrecognized arguments: {' '.join(extra)}")
    args.pytest = extra  # validate: everything unknown goes to pytest (e.g. -k fresnel)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
