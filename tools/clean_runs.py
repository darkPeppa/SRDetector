#!/usr/bin/env python3
"""Delete failed runs (STATUS != ok) under runs/, optionally also runs older than N days.

    python tools/clean_runs.py [--older-than 30] [--dry-run]
"""
import argparse
import shutil
import time

import _common  # noqa: F401
from srdet.paths import runs_dir


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--older-than", type=float, default=None, help="days")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    now = time.time()
    for d in sorted(runs_dir().glob("*")):
        if not d.is_dir() or d.name == "studies":
            continue
        s = d / "STATUS"
        failed = not s.exists() or not s.read_text().startswith("ok")
        old = a.older_than is not None and now - d.stat().st_mtime > a.older_than * 86400
        if failed or old:
            print(("would remove " if a.dry_run else "remove ") + str(d))
            if not a.dry_run:
                shutil.rmtree(d)


if __name__ == "__main__":
    main()
