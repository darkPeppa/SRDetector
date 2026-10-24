"""Labelled, uniformly styled figures for runs and studies.

Every figure has a title, axis labels with units, a legend where needed and a small
info box (configuration, beam, statistics) so that a PNG is self-explanatory.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .analysis import FATE_LABELS, FATES, FIRST_PROC, K_ALPHA, OP_CLASSES, OP_LABELS, PROCS, Run  # noqa: E402

COLORS = ["#2a6fdb", "#e8743b", "#19a979", "#945ecf", "#ed4a7b", "#13a4b4", "#525df4", "#bf399e", "#6c8893",
          "#ee6868"]


def style() -> None:
    plt.rcParams.update({
        "figure.figsize": (7.5, 4.8), "figure.dpi": 110, "savefig.dpi": 140, "savefig.bbox": "tight",
        "axes.grid": True, "grid.alpha": 0.3, "axes.spines.top": False, "axes.spines.right": False,
        "axes.titlesize": 12, "axes.labelsize": 11, "legend.fontsize": 9, "legend.frameon": False,
        "axes.prop_cycle": matplotlib.cycler(color=COLORS), "font.family": "DejaVu Sans",
    })


style()


GREEK = {"lambda": "λ", "gamma": "γ", "mu": "μ", "sigma": "σ", "theta": "θ", "alpha": "α"}


def root_to_mpl(s: str) -> str:
    """ROOT TLatex ('E_{dep}', 'E_{#gamma}', '#lambda') to matplotlib mathtext / unicode."""
    def sub(m):
        inner = re.sub(r"#(\w+)", lambda g: "\\" + g.group(1), m.group(2))
        return f"$\\mathregular{{{m.group(1)}{{{inner}}}}}$"
    s = re.sub(r"([_^])\{([^}]*)\}", sub, s)
    return re.sub(r"#(\w+)", lambda g: GREEK.get(g.group(1), g.group(1)), s)


def beam_label(cfg: dict) -> str:
    b = cfg.get("beam", {})
    if b.get("type") == "optical":
        o = b.get("optical", {})
        ang = "isotropic" if float(str(o.get("theta", -1)).split()[0]) < 0 else f"θ={o.get('theta')}"
        return f"optical gun, {o.get('n')} photons/event, {ang}"
    spec = b.get("spectrum")
    if spec:
        e = spec.get("source") or (f"tube {spec['xray_tube'].get('kvp')} kVp" if "xray_tube" in spec else "spectrum")
    else:
        e = b.get("energy")
    return f"{b.get('particle')} {e}, {b.get('type')} beam"


FLUO_LINES = {"I Kα": 28.61, "Cs Kα": 30.97, "I Kβ": 32.29, "Cs Kβ": 34.99, "Pb Lα": 10.55, "Pb Lβ": 12.61,
              "Pb Kα": 74.97, "Ag Kα": 22.16, "Au Lα": 9.71, "Bi Kα": 77.11, "Lu Kα": 54.07, "Gd Kα": 43.00}


def info_box(ax, run: Run, extra: str = "", loc: str = "upper right") -> None:
    g = run.cfg.get("geometry", {})
    o = run.cfg.get("optics", {})
    txt = (f"{run.cfg.get('name', run.name)}\n{beam_label(run.cfg)}\n"
           f"{g.get('mode')}: L={g.get('length')}, pitch={g.get('pitch')}, D={g.get('channel_diameter')}\n"
           f"core {g.get('core_material')}, wall {g.get('wall_material')}, coating {o.get('coating')}\n"
           f"N events = {len(run.events)}")
    if run.yield_scale != 1:
        txt += f", yield × {run.yield_scale:g}"
    if extra:
        txt += "\n" + extra
    x, ha = (0.99, "right") if "right" in loc else (0.01, "left")
    y, va = (0.98, "top") if "upper" in loc else (0.02, "bottom")
    ax.text(x, y, txt, transform=ax.transAxes, ha=ha, va=va, fontsize=7.5,
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="0.7", alpha=0.85))


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_th1(ax, h, label=None, density=False, **kw):
    v, e = h.to_numpy()
    if density and v.sum() > 0:
        v = v / v.sum() / np.diff(e)
    ax.stairs(v, e, label=label, **kw)
    return v, e


def axis_titles(h) -> tuple[str, str]:
    try:
        return (root_to_mpl(str(h.member("fXaxis").member("fTitle"))),
                root_to_mpl(str(h.member("fYaxis").member("fTitle"))))
    except Exception:
        return "", ""


# ---------------------------------------------------------------- run figures
def run_plots(run: Run, m: dict) -> list[Path]:
    out = run.path / "plots"
    ev = run.events
    files: list[Path] = []
    title = run.cfg.get("name", run.name)

    if not run.optical_gun:
        # energy deposit spectrum with photopeak and K-escape markers
        fig, ax = plt.subplots()
        e0 = m.get("e0_keV", ev["e0_keV"].max())
        bins = np.linspace(0, max(e0 * 1.05, 1), 400)
        ax.hist(ev["edep_total_keV"], bins=bins, histtype="step", lw=2.2, alpha=0.6, label="whole detector")
        ax.hist(ev["edep_core_keV"], bins=bins, histtype="step", lw=1.2, label="scintillator cores")
        ax.set_yscale("log")
        core = run.cfg.get("geometry", {}).get("core_material", "")
        for el, ka in K_ALPHA.items():
            if el in core.replace("_", "") and e0 > ka + 5:
                ax.axvline(e0 - ka, color="0.4", ls=":", lw=1)
                ax.text(e0 - ka, ax.get_ylim()[1] * 0.3, f" E₀−Kα({el})", rotation=90, fontsize=7, va="top")
        ax.axvline(e0, color="k", ls="--", lw=0.8)
        ax.set(xlabel="Deposited energy E$_{dep}$ [keV]", ylabel="Events / bin",
               title=f"Energy deposit spectrum — {title}")
        ax.legend(loc="upper left")
        info_box(ax, run, f"photopeak {m.get('photopeak_fraction', float('nan')):.3f}, "
                          f"K-escape {m.get('k_escape_fraction', float('nan')):.3f}")
        files.append(_save(fig, out / "edep_spectrum.png"))

        # detected photon (photo-electron) spectrum
        if ev["n_det"].sum() > 0:
            fig, ax = plt.subplots()
            nd = ev["n_det"]  # observed counts (statistics of the scaled yield)
            top = int(nd.max()) + 2
            bins = np.arange(-0.5, top + 0.5, max(1, top // 200))
            ax.hist(nd, bins=bins, histtype="stepfilled", alpha=0.35, label="all events")
            if "resolution_fwhm_scaled" in m:
                from .analysis import photopeak_mask
                pk = photopeak_mask(ev, e0)
                ax.hist(nd[pk], bins=bins, histtype="step", lw=1.4, label="photopeak events")
            xl = "Detected photons per event N$_{det}$"
            if run.yield_scale != 1:
                xl += f" (simulated with yield × {run.yield_scale:g}; physical = N / {run.yield_scale:g})"
            ax.set(xlabel=xl, ylabel="Events / bin", title=f"Light output — {title}")
            ax.legend(loc="upper left")
            info_box(ax, run, f"⟨N_det⟩ = {m.get('mean_n_det', 0):.1f}, LY = {m.get('det_yield_per_keV', 0):.2f} pe/keV\n"
                              f"FWHM (scaled stats) = {100 * m.get('resolution_fwhm_scaled', float('nan')):.1f} %")
            files.append(_save(fig, out / "ndet_spectrum.png"))

        # primary first interaction
        fig, ax = plt.subplots()
        labels = [FIRST_PROC[k] for k in FIRST_PROC]
        vals = [m.get(f"first_{lab}", 0) for lab in labels]
        bars = ax.bar(["no interaction", "photoelectric", "Compton", "Rayleigh", "pair", "other"], vals,
                      color=COLORS[:6])
        ax.bar_label(bars, fmt="%.3f", fontsize=8)
        ax.set(ylabel="Fraction of primaries", title=f"First interaction of the primary — {title}")
        info_box(ax, run)
        files.append(_save(fig, out / "first_interaction.png"))

        # EM process invocations per event
        fig, ax = plt.subplots()
        vals = [m.get(f"mean_{p}", 0) for p in PROCS]
        bars = ax.bar([p[2:] for p in PROCS], vals, color=COLORS[: len(PROCS)])
        ax.bar_label(bars, fmt="%.2g", fontsize=8)
        ax.set_yscale("log")
        lo, hi = ax.get_ylim()
        ax.set_ylim(lo, hi * 30)  # room for the info box
        ax.set(ylabel="Mean invocations per event", xlabel="Geant4 process",
               title=f"EM process frequency — {title}")
        info_box(ax, run)
        files.append(_save(fig, out / "em_processes.png"))

    # optical photon fates
    fates = [m.get(f"fate_{f}", 0) for f in FATES]
    if sum(fates) > 0:
        fig, ax = plt.subplots()
        bars = ax.barh([FATE_LABELS[f] for f in FATES], fates, color=COLORS[: len(FATES)])
        ax.bar_label(bars, fmt="%.2e", fontsize=8)
        ax.invert_yaxis()
        nz = [f for f in fates if f > 0]
        if nz and min(nz) < 0.01:
            ax.set_xscale("log")
            ax.set_xlim(min(nz) / 3, 2)
        ax.set(xlabel="Fraction of produced optical photons", title=f"Fate of optical photons — {title}")
        info_box(ax, run, f"LCE = {m.get('lce', 0):.4f}, exit = {m.get('lce_exit', 0):.4f}")
        files.append(_save(fig, out / "photon_fates.png"))

        fig, ax = plt.subplots()
        vals = [m.get(f"mean_{k}", 0) for k in OP_CLASSES]
        bars = ax.barh([OP_LABELS[k] for k in OP_CLASSES], vals, color=COLORS[: len(OP_CLASSES)])
        ax.bar_label(bars, fmt="%.3g", fontsize=8)
        ax.invert_yaxis()
        ax.set_xscale("symlog", linthresh=1)
        ax.set(xlabel="Mean number per event", title=f"Optical boundary interactions — {title}")
        info_box(ax, run)
        files.append(_save(fig, out / "boundary_processes.png"))

    # Geant4 H1 histograms of photons
    for key, fname, logy in [("t_det", "arrival_time.png", True), ("nrefl_det", "reflections.png", False),
                             ("birthz_det", "emission_depth_detected.png", False),
                             ("fluo_energy", "fluorescence_xrays.png", True)]:
        h = run.hists.get(key)
        if h is None or h.to_numpy()[0].sum() == 0:
            continue
        fig, ax = plt.subplots()
        plot_th1(ax, h, lw=1.3)
        xt, yt = axis_titles(h)
        ax.set(xlabel=xt, ylabel=yt, title=f"{root_to_mpl(h.title)} — {title}")
        if logy:
            ax.set_yscale("log")
        box_loc = "upper left" if key in ("fluo_energy", "t_det") else "upper right"
        if key == "fluo_energy":
            v, edges = h.to_numpy()
            nz = np.nonzero(v)[0]
            if len(nz):
                ax.set_xlim(edges[max(nz[0] - 20, 0)], edges[min(nz[-1] + 20, len(edges) - 1)])
            lo, hi = ax.get_xlim()
            for lab, e in FLUO_LINES.items():
                if lo < e < hi:
                    ax.axvline(e, color="0.5", ls=":", lw=0.8)
                    ax.text(e, ax.get_ylim()[1], f" {lab}", rotation=90, fontsize=7, va="top", ha="right")
        info_box(ax, run, loc=box_loc)
        files.append(_save(fig, out / fname))

    # wavelength: produced vs detected, with sensor efficiency
    hs, hd = run.hists.get("lambda_scint"), run.hists.get("lambda_det")
    if hd is not None and hd.to_numpy()[0].sum() > 0:
        fig, ax = plt.subplots()
        if hs is not None and hs.to_numpy()[0].sum() > 0:
            plot_th1(ax, hs, label="produced (scintillation)", density=True, lw=1.3)
        plot_th1(ax, hd, label="detected", density=True, lw=1.3)
        eff = run.geom.get("sensor_efficiency")
        if eff:
            ax2 = ax.twinx()
            lam = 1239.84193 / np.array(eff["energy_eV"])
            ax2.plot(lam, eff["efficiency"], color="0.3", ls="--", lw=1, label="sensor QE × fill factor")
            ax2.set_ylabel("Sensor efficiency")
            ax2.set_ylim(0, 1.05)
            ax2.legend(loc="center right")
        ax.set(xlabel="Wavelength λ [nm]", ylabel="Probability density [1/nm]",
               title=f"Optical spectrum — {title}", xlim=(280, 800))
        ax.legend(loc="upper left")
        files.append(_save(fig, out / "wavelength.png"))

    # 2D maps
    for key, fname in [("det_xy", "sensor_hitmap.png"), ("first_xy", "first_interaction_map.png")]:
        h = run.hists.get(key)
        if h is None:
            continue
        v, xe, ye = h.to_numpy()
        if v.sum() == 0:
            continue
        fig, ax = plt.subplots(figsize=(6.2, 5.2))
        im = ax.pcolormesh(xe, ye, np.ma.masked_equal(v.T, 0), norm=matplotlib.colors.LogNorm(), cmap="viridis")
        fig.colorbar(im, ax=ax, label="counts")
        r = run.geom.get("matrix_radius_mm")
        if r:
            t = np.linspace(0, 2 * np.pi, 300)
            ax.plot(r * np.cos(t), r * np.sin(t), color="w", lw=0.8, ls="--")
        ax.set_aspect("equal")
        ax.grid(False)
        xt, yt = axis_titles(h)
        ax.set(xlabel=xt or "x [mm]", ylabel=yt or "y [mm]", title=f"{root_to_mpl(h.title)}\n{title}")
        files.append(_save(fig, out / fname))

    files += material_plots(run)
    return files


def material_plots(run: Run) -> list[Path]:
    mats = {k: v for k, v in run.mats.items() if "RINDEX" in v.get("vectors", {})}
    if not mats:
        return []
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    for name, d in mats.items():
        vec = d["vectors"]
        lam = 1239.84193 / np.array(vec["RINDEX"]["energy_eV"])
        axes[0].plot(lam, vec["RINDEX"]["value"], label=name)
        if "ABSLENGTH" in vec:
            lam_a = 1239.84193 / np.array(vec["ABSLENGTH"]["energy_eV"])
            axes[1].plot(lam_a, np.array(vec["ABSLENGTH"]["value"]) / 10, label=name)
        if "SCINTILLATIONCOMPONENT1" in vec:
            lam_s = 1239.84193 / np.array(vec["SCINTILLATIONCOMPONENT1"]["energy_eV"])
            axes[2].plot(lam_s, vec["SCINTILLATIONCOMPONENT1"]["value"], label=name)
    axes[0].set(xlabel="Wavelength λ [nm]", ylabel="Refractive index n", title="RINDEX")
    axes[1].set(xlabel="Wavelength λ [nm]", ylabel="Absorption length [cm]", title="ABSLENGTH", yscale="log")
    axes[2].set(xlabel="Wavelength λ [nm]", ylabel="Relative intensity dN/dE", title="Scintillation emission")
    for a in axes:
        a.legend()
    fig.suptitle(f"Optical material properties used — {run.cfg.get('name', run.name)}")
    return [_save(fig, run.path / "plots" / "materials_optical.png")]


# ---------------------------------------------------------------- study figures
def study_plot(df, x: str, metrics: list[str], path: Path, title: str, xlabel: str | None = None,
               series: str | None = None, logx: bool = False, labels: dict | None = None,
               overlays: dict | None = None) -> Path:
    labels = labels or {}
    n = len(metrics)
    ncol = min(n, 2)
    nrow = math.ceil(n / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(6.4 * ncol, 4.2 * nrow), squeeze=False)
    import pandas as pd
    categorical = not pd.api.types.is_numeric_dtype(df[x])
    for i, met in enumerate(metrics):
        ax = axes[i // ncol][i % ncol]
        groups = df.groupby(series, sort=False) if series else [(None, df)]
        for j, (sname, g) in enumerate(groups):
            if met not in g:
                continue
            y = g[met].astype(float)
            err = g[f"{met}_err"].astype(float) if f"{met}_err" in g else None
            lab = None if sname is None else f"{series.split('.')[-1]} = {sname}"
            if categorical and not series:
                bars = ax.bar(g[x].astype(str), y, yerr=err, color=COLORS[: len(g)], capsize=3)
                ax.bar_label(bars, fmt="%.3g", fontsize=7, padding=2)
                ax.tick_params(axis="x", rotation=35)
                plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor")
            else:
                ax.errorbar(g[x] if not categorical else g[x].astype(str), y, yerr=err, marker="o", ms=4,
                            capsize=3, label=lab, color=COLORS[j % len(COLORS)])
                if categorical:
                    ax.tick_params(axis="x", rotation=35)
        if overlays and met in overlays:
            ox, oy, olab = overlays[met]
            ax.plot(ox, oy, "k--", lw=1, label=olab)
        if logx and not categorical:
            ax.set_xscale("log")
        ax.set(xlabel=xlabel or x, ylabel=labels.get(met, met))
        if series or (overlays and met in overlays):
            ax.legend()
    for k in range(n, nrow * ncol):
        axes[k // ncol][k % ncol].set_visible(False)
    fig.suptitle(title, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    return _save(fig, path)


def stacked_fractions(df, x: str, cols: list[str], names: list[str], path: Path, title: str, xlabel: str,
                      logx: bool = True, ref: dict | None = None) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    xs = df[x].astype(float).to_numpy()
    order = np.argsort(xs)
    ys = [df[c].astype(float).to_numpy()[order] for c in cols]
    ax.stackplot(xs[order], *ys, labels=names, colors=COLORS[: len(cols)], alpha=0.75)
    if ref:
        for (rx, ry, lab), col in zip(ref.values(), COLORS):
            ax.plot(rx, ry, ls="--", color="k", lw=0.9)
        ax.plot([], [], "k--", lw=0.9, label="NIST XCOM (cumulative)")
    if logx:
        ax.set_xscale("log")
    ax.set(xlabel=xlabel, ylabel="Fraction of primaries", ylim=(0, 1), title=title)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    return _save(fig, path)


def process_counts(df, x: str, path: Path, title: str, xlabel: str) -> Path:
    """Mean number of invocations per event of each EM process versus x (log-log)."""
    fig, ax = plt.subplots(figsize=(8, 5))
    xs = df[x].astype(float).to_numpy()
    order = np.argsort(xs)
    names = {"mean_n_phot": "photoelectric", "mean_n_compt": "Compton", "mean_n_rayl": "Rayleigh",
             "mean_n_conv": "pair production", "mean_n_eioni": "e⁻ ionisation (δ-rays)",
             "mean_n_ebrem": "bremsstrahlung", "mean_n_annihil": "annihilation", "mean_n_fluo": "fluorescence X-rays"}
    for (col, lab), c in zip(names.items(), COLORS):
        if col in df and (df[col] > 0).any():
            ax.plot(xs[order], df[col].astype(float).to_numpy()[order], marker="o", ms=3, label=lab, color=c)
    ax.set(xscale="log", yscale="log", xlabel=xlabel, ylabel="Mean invocations per event", title=title)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    return _save(fig, path)
