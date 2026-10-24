#!/usr/bin/env python3
"""Install Geant4 datasets by NAME, reading versions/filenames/MD5 from the
G4DatasetDefinitions.cmake of the Geant4 source that was built.

Lookup order per dataset:
  1. --seed  directory: an extracted <NAME><VERSION>/ directory or a <FILENAME>.<VERSION>.<EXT> archive
  2. --cache directory: an archive downloaded by a previous build (BuildKit cache mount)
  3. download from https://cern.ch/geant4-data/datasets/ (MD5 verified)

    fetch_datasets.py --defs G4DatasetDefinitions.cmake --dest DATADIR [--cache D] [--seed D] NAME ...
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

URL = "https://cern.ch/geant4-data/datasets/"


def parse(defs: Path) -> dict[str, dict[str, str]]:
    out = {}
    for block in re.findall(r"geant4_add_dataset\((.*?)\)", defs.read_text(), re.S):
        fields = dict(re.findall(r"(NAME|VERSION|FILENAME|EXTENSION|ENVVAR|MD5SUM)\s+(\S+)", block))
        out[fields["NAME"]] = fields
    return out


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".part")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.rename(target)
            return
        except Exception as e:  # network hiccups: retry with back-off
            print(f"  download failed ({e}), retry {attempt + 1}/5", flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"cannot download {url}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--defs", required=True, type=Path)
    ap.add_argument("--dest", required=True, type=Path)
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--seed", type=Path)
    ap.add_argument("names", nargs="+")
    a = ap.parse_args()
    defs = parse(a.defs)
    a.dest.mkdir(parents=True, exist_ok=True)
    for name in a.names:
        if name not in defs:
            print(f"unknown dataset {name}; known: {', '.join(defs)}")
            return 1
        d = defs[name]
        dirname = f"{d['NAME']}{d['VERSION']}"
        archive = f"{d['FILENAME']}.{d['VERSION']}.{d['EXTENSION']}"
        if (a.dest / dirname).is_dir():
            print(f"{name}: already installed")
            continue
        if a.seed and (a.seed / dirname).is_dir():
            print(f"{name}: copied from seed directory", flush=True)
            shutil.copytree(a.seed / dirname, a.dest / dirname)
            continue
        src = None
        for cand in ([a.seed / archive] if a.seed else []) + ([a.cache / archive] if a.cache else []):
            if cand.exists() and md5(cand) == d["MD5SUM"]:
                src = cand
                break
        if src is None:
            target = (a.cache or a.dest) / archive
            print(f"{name}: downloading {archive}", flush=True)
            download(URL + archive, target)
            if md5(target) != d["MD5SUM"]:
                target.unlink()
                raise RuntimeError(f"MD5 mismatch for {archive}")
            src = target
        else:
            print(f"{name}: using cached {src}", flush=True)
        with tarfile.open(src) as t:
            t.extractall(a.dest, filter="data")
        if src.parent == a.dest:
            src.unlink()
        if not (a.dest / dirname).is_dir():
            raise RuntimeError(f"{archive} did not unpack to {dirname}")
    print("installed:", " ".join(sorted(p.name for p in a.dest.iterdir())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
