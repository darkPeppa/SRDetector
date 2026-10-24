"""Pack successful runs / studies into results/<name>.tar.xz, small enough for GitHub.

Kept: configs, macros, meta, json summaries, logs (tail), plots, results tables, and a reduced
ROOT file with the histograms only. The 'events' ntuple is converted to Parquet (zstd) when it
fits the budget; 'photons' / 'cells' ntuples are dropped first. GitHub rejects files > 100 MB
and warns above 50 MB, so the default budget per archive is 45 MB.
"""
from __future__ import annotations

import io
import json
import tarfile
import tempfile
from pathlib import Path

from .paths import results_dir

KEEP_SUFFIX = {".yaml", ".mac", ".json", ".png", ".pdf", ".csv", ".md", ".txt", ".gdml"}
SKIP_NAMES = {"log.txt"}


def _reduce_root(src: Path, dst_dir: Path, budget: int) -> list[Path]:
    import uproot

    out = []
    f = uproot.open(src)
    hist_path = dst_dir / "histograms.root"
    titles = {}
    # Geant4-written TH1/TH2 cannot be re-serialised by uproot directly: write the arrays and
    # keep titles / axis labels in a JSON side-car
    with uproot.recreate(hist_path) as w:
        for key, cls in f.classnames().items():
            if cls.startswith("TH"):
                h = f[key]
                name = key.split(";")[0]
                w[name] = h.to_numpy()
                axes = [h.member(a).member("fTitle") for a in ("fXaxis", "fYaxis") if h.has_member(a)]
                titles[name] = {"title": h.title, "axes": [str(a) for a in axes]}
    (dst_dir / "histogram_titles.json").write_text(json.dumps(titles, indent=1))
    out += [hist_path, dst_dir / "histogram_titles.json"]
    if "events" in f:
        pq = dst_dir / "events.parquet"
        f["events"].arrays(library="pd").to_parquet(pq, compression="zstd")
        if pq.stat().st_size < budget:
            out.append(pq)
        else:
            pq.unlink()
    return out


def is_ok(d: Path) -> bool:
    s = d / "STATUS"
    if s.exists():
        return s.read_text().startswith("ok")
    return (d / "results.csv").exists()  # study folder


def pack(path: str | Path, budget_mb: float = 45.0, out_dir: Path | None = None, force: bool = False) -> Path:
    path = Path(path).resolve()
    if not force and not is_ok(path):
        raise RuntimeError(f"{path} is not a successful run (STATUS != ok); use --force to archive anyway")
    out_dir = out_dir or results_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    budget = int(budget_mb * 1024 * 1024)
    target = out_dir / f"{path.name}.tar.xz"
    with tempfile.TemporaryDirectory() as tmp, tarfile.open(target, "w:xz") as tar:
        tmp = Path(tmp)
        for f in sorted(path.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(path.parent)
            if f.name == "srdet.root":
                sub = tmp / rel.parent
                sub.mkdir(parents=True, exist_ok=True)
                for r in _reduce_root(f, sub, budget // 4):
                    tar.add(r, arcname=str(rel.parent / r.name))
            elif f.name == "log.txt":
                tail = "\n".join(f.read_text(errors="replace").splitlines()[-400:]).encode()
                info = tarfile.TarInfo(str(rel.parent / "log_tail.txt"))
                info.size = len(tail)
                tar.addfile(info, io.BytesIO(tail))
            elif f.suffix in KEEP_SUFFIX and f.name not in SKIP_NAMES:
                tar.add(f, arcname=str(rel))
    size = target.stat().st_size
    if size > budget:
        target.unlink()
        raise RuntimeError(f"archive would be {size / 1e6:.1f} MB > {budget_mb} MB: reduce the run or use Git LFS")
    (out_dir / "INDEX.json").write_text(json.dumps(_index(out_dir), indent=2))
    print(f"[srdet] archived {path.name} -> {target} ({size / 1e6:.2f} MB)")
    return target


def _index(out_dir: Path) -> list[dict]:
    return [{"archive": p.name, "size_MB": round(p.stat().st_size / 1e6, 3)} for p in sorted(out_dir.glob("*.tar.xz"))]


def unpack(archive: str | Path, dest: Path) -> Path:
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter="data")
    return dest
