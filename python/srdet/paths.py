"""Locations of the repository, the Geant4 binary and output folders."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def repo_root() -> Path:
    """Repository root: $SRDET_REPO, else the first parent of cwd / this file that has configs/."""
    env = os.environ.get("SRDET_REPO")
    if env:
        return Path(env).resolve()
    for start in (Path.cwd(), Path(__file__).resolve()):
        for p in [start, *start.parents]:
            if (p / "configs").is_dir() and (p / "macros").is_dir():
                return p
    return Path.cwd()


def sim_binary() -> str:
    env = os.environ.get("SRDET_BIN")
    if env and Path(env).exists():
        return env
    found = shutil.which("srdet-sim")
    if found:
        return found
    for cand in (repo_root() / "build" / "srdet-sim",):
        if cand.exists():
            return str(cand)
    raise FileNotFoundError("srdet-sim not found: build it (cmake) or run inside the Docker image")


def runs_dir() -> Path:
    return Path(os.environ.get("SRDET_RUNS", repo_root() / "runs"))


def results_dir() -> Path:
    return repo_root() / "results"


def configs_dir() -> Path:
    return repo_root() / "configs"
