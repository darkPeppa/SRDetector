#!/usr/bin/env python3
"""Write an approximate W-anode X-ray tube spectrum (Kramers + W K lines, Al filtration)
as a two-column CSV usable with `beam.spectrum: {file: ...}`, and plot it.

    python tools/xray_spectrum.py --kvp 80 --filter 2.5 -o spectra/w80.csv
"""
import argparse

import _common  # noqa: F401
import numpy as np
from srdet import spectra


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kvp", type=float, default=80)
    ap.add_argument("--filter", type=float, default=2.5, help="mm Al")
    ap.add_argument("-o", "--out", default="xray_spectrum.csv")
    a = ap.parse_args()
    e, w = spectra.xray_tube(a.kvp, a.filter)
    np.savetxt(a.out, np.c_[e, w], delimiter=",", header=f"W anode {a.kvp} kVp, {a.filter} mm Al\nE_keV,weight")
    import matplotlib.pyplot as plt
    from srdet import plotting  # noqa: F401  (style)
    fig, ax = plt.subplots()
    ax.step(e, w, where="mid")
    ax.set(xlabel="Photon energy [keV]", ylabel="Relative fluence per bin",
           title=f"Approximate W-anode spectrum, {a.kvp:g} kVp, {a.filter:g} mm Al")
    fig.savefig(a.out.rsplit(".", 1)[0] + ".png")
    print(f"mean energy {np.sum(e * w):.1f} keV -> {a.out}")


if __name__ == "__main__":
    main()
