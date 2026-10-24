"""Run one simulation: prepare a run folder, back up the configuration, call srdet-sim,
validate the output and (optionally) analyse it.

runs/<YYYYmmdd-HHMMSS>_<name>/
    config.yaml        fully resolved configuration
    run.mac            generated macro
    meta.json          git commit, Geant4 version, host, command, timing
    srdet.root         histograms + ntuples
    geometry.json      cells and derived dimensions      (written by srdet-sim)
    materials.json     optical tables actually used      (written by srdet-sim)
    run_summary.json   quick numbers                     (written by srdet-sim)
    log.txt            full Geant4 output
    STATUS             "ok" or "failed: <reason>"
"""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from . import config as C
from . import macro as M
from .paths import configs_dir, repo_root, runs_dir, sim_binary


@dataclass
class RunResult:
    path: Path
    ok: bool
    reason: str = ""


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=repo_root(), capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return ""


def _g4_version() -> str:
    try:
        return subprocess.run(["geant4-config", "--version"], capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return "unknown"


def backup_config(cfg: dict) -> Path | None:
    """Store every distinct configuration once in configs/history/ (hash-named).
    Disabled with SRDET_NO_HISTORY=1 (tests)."""
    if os.environ.get("SRDET_NO_HISTORY") == "1":
        return None
    hist = configs_dir() / "history"
    hist.mkdir(parents=True, exist_ok=True)
    h = C.digest(cfg)
    existing = list(hist.glob(f"*_{h}_*.yaml"))
    if existing:
        return existing[0]
    stamp = dt.datetime.now().strftime("%Y%m%d")
    path = hist / f"{stamp}_{h}_{cfg.get('name', 'config')}.yaml"
    path.write_text(C.dump({k: v for k, v in cfg.items() if not k.startswith("_")}))
    return path


def threads(cfg: dict) -> int:
    n = int(os.environ.get("SRDET_THREADS", 0) or cfg["run"].get("threads", 0) or 0)
    return n if n > 0 else (os.cpu_count() or 1)


def check_output(run_dir: Path, log: str, rc: int) -> tuple[bool, str]:
    if rc != 0:
        return False, f"srdet-sim exit code {rc}"
    if "G4Exception" in log and "-------- EEEE" in log:
        return False, "Geant4 fatal exception"
    for f in ("srdet.root", "run_summary.json", "geometry.json"):
        if not (run_dir / f).exists():
            return False, f"missing {f}"
    if "Overlap is detected" in log:
        return False, "geometry overlaps detected"
    return True, ""


def run(cfg: dict, name: str | None = None, parent: Path | None = None, analyze: bool = True,
        quiet: bool = False, backup: bool = True) -> RunResult:
    name = name or cfg.get("name", "run")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = parent if parent else runs_dir()
    run_dir = (base / f"{stamp}_{name}").resolve()
    i = 1
    while run_dir.exists():
        run_dir = (base / f"{stamp}_{name}_{i}").resolve()
        i += 1
    run_dir.mkdir(parents=True)

    (run_dir / "config.yaml").write_text(C.dump(cfg))
    macro_text = M.render(cfg, run_dir)
    (run_dir / "run.mac").write_text(macro_text)
    hist_path = backup_config(cfg) if backup else None

    cmd = [sim_binary(), str(run_dir / "run.mac"), "-t", str(threads(cfg))]
    meta = {
        "name": name, "started": dt.datetime.now().isoformat(timespec="seconds"), "command": cmd,
        "git_commit": _git("rev-parse", "HEAD"), "git_dirty": bool(_git("status", "--porcelain")),
        "geant4": _g4_version(), "host": platform.node(), "config_digest": C.digest(cfg),
        "config_backup": (str(hist_path.relative_to(repo_root())) if hist_path.is_relative_to(repo_root())
                          else str(hist_path)) if hist_path else None,
        "config_sources": cfg.get("_sources", []),
    }
    t0 = time.time()
    if not quiet:
        print(f"[srdet] run {name}: {run_dir}")
    with open(run_dir / "log.txt", "w") as logf:
        proc = subprocess.run(cmd, cwd=run_dir, stdout=logf, stderr=subprocess.STDOUT)
    log = (run_dir / "log.txt").read_text(errors="replace")
    meta["wall_time_s"] = round(time.time() - t0, 2)
    ok, reason = check_output(run_dir, log, proc.returncode)

    if ok and analyze:
        try:
            from .analysis import analyze_run
            analyze_run(run_dir, plots=True)
        except Exception as e:  # analysis failure does not hide a good simulation
            reason = f"analysis failed: {e}"
            ok = False
    meta["status"] = "ok" if ok else f"failed: {reason}"
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    (run_dir / "STATUS").write_text(meta["status"] + "\n")
    if not quiet:
        print(f"[srdet] {meta['status']} ({meta['wall_time_s']} s)")
        if not ok:
            print("\n".join(log.splitlines()[-25:]))
    return RunResult(run_dir, ok, reason)


def clean_failed(base: Path | None = None) -> list[Path]:
    removed = []
    for d in (base or runs_dir()).glob("*"):
        s = d / "STATUS"
        if s.exists() and not s.read_text().startswith("ok"):
            shutil.rmtree(d)
            removed.append(d)
    return removed
