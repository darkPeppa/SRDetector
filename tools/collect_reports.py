#!/usr/bin/env python3
"""Collect the latest report of every study into results/studies/<study>/ (plots, tables,
report.md) and write results/studies/README.md with an index. Run after `srdet study all`.

    python tools/collect_reports.py [--studies-dir runs/studies]
"""
import argparse
import shutil
from pathlib import Path

import _common  # noqa: F401
from srdet.paths import results_dir, runs_dir


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--studies-dir", default=str(runs_dir() / "studies"))
    ap.add_argument("--include-quick", action="store_true")
    a = ap.parse_args()
    latest = {}
    for d in sorted(Path(a.studies_dir).glob("*")):
        if not (d / "report.md").exists() or (d.name.endswith("_quick") and not a.include_quick):
            continue
        name = d.name.split("_", 1)[1].removesuffix("_quick")
        latest[name] = d
    out = results_dir() / "studies"
    out.mkdir(parents=True, exist_ok=True)
    index = ["# Study results", "", "| study | source run | report |", "|---|---|---|"]
    for name, d in sorted(latest.items()):
        dst = out / name
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir()
        for f in ["report.md", "results.csv", "results.md", "study.yaml"]:
            if (d / f).exists():
                shutil.copy2(d / f, dst / f)
        if (d / "plots").exists():
            shutil.copytree(d / "plots", dst / "plots")
        index.append(f"| {name} | `{d.name}` | [report]({name}/report.md) |")
    (out / "README.md").write_text("\n".join(index) + "\n")
    print(f"{len(latest)} studies -> {out}")


if __name__ == "__main__":
    main()
