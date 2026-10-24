"""Shared fixtures. Physics tests run short simulations and are skipped when srdet-sim is
not available (e.g. outside the Docker image). SRDET_QUICK=1 lowers the statistics."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
os.environ.setdefault("SRDET_REPO", str(ROOT))
os.environ["SRDET_NO_HISTORY"] = "1"  # test runs are not configuration backups

from srdet import config as C  # noqa: E402
from srdet.paths import sim_binary  # noqa: E402


def have_sim() -> bool:
    try:
        sim_binary()
        return True
    except FileNotFoundError:
        return False


QUICK = os.environ.get("SRDET_QUICK") == "1"
needs_sim = pytest.mark.skipif(not have_sim(), reason="srdet-sim not available")


def scale(n: int) -> int:
    return max(200, n // 5) if QUICK else n


@pytest.fixture(scope="session")
def workdir(tmp_path_factory):
    d = tmp_path_factory.mktemp("srdet_tests")
    os.environ["SRDET_RUNS"] = str(d)
    yield d
    if os.environ.get("SRDET_KEEP_TEST_RUNS") != "1":
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def simulate(workdir):
    """simulate(base_config, {dotted: value}) -> (Run, metrics)"""
    from srdet.analysis import load_run, metrics
    from srdet.runner import run

    cache = {}

    def _sim(base: str, sets: dict, name: str):
        key = (base, tuple(sorted((k, str(v)) for k, v in sets.items())))
        if key in cache:
            return cache[key]
        cfg = C.load(base)
        for k, v in sets.items():
            C.set_path(cfg, k, v)
        cfg["name"] = name
        cfg["run"]["threads"] = int(os.environ.get("SRDET_TEST_THREADS", 0)) or os.cpu_count()
        res = run(cfg, name=name, parent=workdir, analyze=False, quiet=True)
        log = (res.path / "log.txt").read_text(errors="replace")
        assert res.ok, f"{name} failed: {res.reason}\n" + "\n".join(log.splitlines()[-30:])
        r = load_run(res.path)
        cache[key] = (r, metrics(r), log)
        return cache[key]

    return _sim
