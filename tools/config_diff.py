#!/usr/bin/env python3
"""Show the differences between two (resolved) configurations or run folders.

    python tools/config_diff.py configs/detector/full.yaml runs/<run>/config.yaml
"""
import argparse
from pathlib import Path

import _common  # noqa: F401
from srdet import config as C


def flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        if k.startswith("_"):
            continue
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flat(v, key + "."))
        else:
            out[key] = v
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    a = ap.parse_args()
    paths = [Path(p) / "config.yaml" if Path(p).is_dir() else Path(p) for p in (a.a, a.b)]
    fa, fb = (flat(C.load(p)) for p in paths)
    for k in sorted(set(fa) | set(fb)):
        if fa.get(k) != fb.get(k):
            print(f"{k:40s} {fa.get(k)!s:>25}  ->  {fb.get(k)!s}")


if __name__ == "__main__":
    main()
