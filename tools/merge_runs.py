#!/usr/bin/env python3
"""Merge the 'events' ntuples of several runs into one Parquet file (adds a 'run' column).

    python tools/merge_runs.py runs/A runs/B ... -o merged.parquet
"""
import argparse
from pathlib import Path

import _common  # noqa: F401
import pandas as pd
import uproot


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("-o", "--out", default="merged_events.parquet")
    a = ap.parse_args()
    frames = []
    for r in a.runs:
        df = uproot.open(Path(r) / "srdet.root")["events"].arrays(library="pd")
        df.insert(0, "run", Path(r).name)
        frames.append(df)
    pd.concat(frames, ignore_index=True).to_parquet(a.out, compression="zstd")
    print(f"{sum(len(f) for f in frames)} events -> {a.out}")


if __name__ == "__main__":
    main()
