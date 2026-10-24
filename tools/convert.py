#!/usr/bin/env python3
"""Convert the ntuples / histograms of a run (srdet.root) to CSV and Parquet.

    python tools/convert.py runs/<run> [--format csv|parquet|both]
Creates <run>/export/{events,photons,cells}.{csv,parquet} and one CSV per histogram
(bin edges, contents) with the axis titles in the header.
"""
import argparse
from pathlib import Path

import _common  # noqa: F401
import numpy as np
import uproot


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--format", default="both", choices=["csv", "parquet", "both"])
    a = ap.parse_args()
    run = Path(a.run)
    out = run / "export"
    out.mkdir(exist_ok=True)
    f = uproot.open(run / "srdet.root")
    for key, cls in f.classnames().items():
        name = key.split(";")[0]
        obj = f[key]
        if cls == "TTree":
            df = obj.arrays(library="pd")
            if a.format in ("csv", "both"):
                df.to_csv(out / f"{name}.csv", index=False)
            if a.format in ("parquet", "both"):
                df.to_parquet(out / f"{name}.parquet", compression="zstd")
            print(f"{name}: {len(df)} rows")
        elif cls.startswith("TH1"):
            v, e = obj.to_numpy()
            xt = obj.member("fXaxis").member("fTitle")
            np.savetxt(out / f"h1_{name}.csv", np.c_[e[:-1], e[1:], v], delimiter=",",
                       header=f"{obj.title}\nlow,high,counts  (x: {xt})")
        elif cls.startswith("TH2"):
            v, xe, ye = obj.to_numpy()
            np.savetxt(out / f"h2_{name}.csv", v, delimiter=",",
                       header=f"{obj.title}; x edges {xe[0]}..{xe[-1]} ({len(xe) - 1}), y edges {ye[0]}..{ye[-1]} ({len(ye) - 1})")
    print(f"exported to {out}")


if __name__ == "__main__":
    main()
