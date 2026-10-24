#!/usr/bin/env python3
"""Download photon cross sections from NIST XCOM (Berger et al.) into tests/data/xcom_<name>.csv.

Columns (cm^2/g): E_MeV, coherent, incoherent, photoelectric, pair_nuclear, pair_electron,
total_with_coherent, total_without_coherent. Absorption edges appear as duplicated energies.

    python tools/fetch_xcom.py                 # default material set
    python tools/fetch_xcom.py --formula CsI --name CsI
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://physics.nist.gov/cgi-bin/Xcom/xcom3_2"
DEFAULT = {
    "CsI": "CsI",
    "NaI": "NaI",
    "BGO": "Bi4Ge3O12",
    "LYSO": "Lu9Y1Si5O25",
    "GAGG": "Gd3Al2Ga3O12",
    "Al": "Al",
    "Be": "Be",
    "Si": "Si",
    "Pb": "Pb",
    "PbO": "PbO",
    "SiO2": "SiO2",
}
ROW = re.compile(r"^\s*(?:\d+\s+[KLMN]\s*\d*\s+)?((?:[0-9.]+E[+-]\d+\s+){7}[0-9.]+E[+-]\d+)\s*$")


def fetch(formula: str, emin=0.001, emax=20.0) -> list[list[float]]:
    data = urllib.parse.urlencode({
        "Formula": formula, "Name": "".join(c for c in formula if c.isalpha()), "Graph0": "on", "NumAdd": "1", "Energies": "",
        "Output": "on", "WindowXmin": str(emin), "WindowXmax": str(emax), "ResizeFlag": "on",
    }).encode()
    headers = {"User-Agent": "Mozilla/5.0 (srdet fetch_xcom)",
               "Referer": "https://physics.nist.gov/cgi-bin/Xcom/xcom2"}
    try:
        req = urllib.request.Request(URL, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as r:
            text = r.read().decode("latin-1")
    except urllib.error.URLError:
        # e.g. python.org builds on macOS without CA certificates: fall back to curl
        cmd = ["curl", "-s", "--max-time", "90", "-X", "POST", URL, "--data", data.decode()]
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
        text = subprocess.run(cmd, check=True, capture_output=True).stdout.decode("latin-1")
    text = html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " ")
    rows = []
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            rows.append([float(x) for x in m.group(1).split()])
    if not rows:
        raise RuntimeError(f"XCOM returned no table for {formula}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--formula")
    ap.add_argument("--name")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "tests" / "data"))
    a = ap.parse_args()
    todo = {a.name or a.formula: a.formula} if a.formula else DEFAULT
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    failed = []
    for name, formula in todo.items():
        rows = None
        for attempt in range(4):
            try:
                rows = fetch(formula)
                break
            except (RuntimeError, subprocess.CalledProcessError) as e:
                print(f"{name}: {e}, retry {attempt + 1}")
                time.sleep(5 * (attempt + 1))
        if rows is None:
            failed.append(name)
            continue
        time.sleep(2)
        path = out / f"xcom_{name}.csv"
        with open(path, "w") as f:
            f.write(f"# NIST XCOM, formula {formula}; cross sections in cm2/g\n")
            f.write("E_MeV,coherent,incoherent,photoelectric,pair_nuclear,pair_electron,"
                    "total_with_coherent,total_without_coherent\n")
            for r in rows:
                f.write(",".join(f"{x:.4E}" for x in r) + "\n")
        print(f"{name:6s} {formula:14s} {len(rows):4d} rows -> {path}")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
