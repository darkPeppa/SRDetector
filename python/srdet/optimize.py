"""Search for optimal detector / material parameters (configs/optimize/*.yaml).

Spec:
    name: O01_geometry
    title: "..."
    base: full.yaml                       # detector config the search starts from
    set: {beam.energy: 60 keV}            # fixed dotted overrides
    space:                                # free parameters, keyed by a short alias
      L:    {path: geometry.length, low: 0.5 mm, high: 5 mm, log: true}
      D:    {path: geometry.channel_diameter, low: 100 um, high: 400 um, log: true}
      wall: {low: 2 um, high: 60 um}       # no path -> virtual, used in `derived`
      coat: {path: optics.coating, values: [Al, Ag, ESR_LUT]}
      n:    {path: run.events, type: int, low: 100, high: 500}
    derived:                              # dotted path -> expression of aliases (base units mm/keV/deg)
      geometry.pitch: {expr: "D + 2*0.002 + wall", unit: mm}
    objective: {expr: "det_yield_per_keV * detection_efficiency", direction: maximize}
    constraints: ["detection_efficiency >= 0.8", "psf_r50_um <= 150"]
    pareto: {x: psf_r50_um, x_dir: min, y: det_yield_per_keV, y_dir: max}   # optional
    search:
      sampler: lhs                        # lhs | random | grid
      initial: 24                         # candidates in the first stage (grid: all combinations)
      events: [300, 900, 2700]            # statistics per successive-halving stage
      eta: 3                              # keep the best 1/eta after each stage
      refine: {iterations: 6, events: 2700, step: 0.2, min_gain: 0.03}   # coordinate search, optional
      final: {top: 3, events: 5000, repeats: 3}                         # validation with new seeds
      seed: 1
    quick: {initial: 6, events: [50, 150], refine: null, final: {top: 1, events: 200, repeats: 2}}

Expressions are arithmetic over metric names (see analysis.metrics), parameter aliases and math
functions (log, exp, sqrt, min, max, abs); they are parsed with a whitelist (no attributes, no
indexing, no other calls), so specs written in the web UI cannot run code. A missing / NaN metric
makes a trial infeasible.

Output: runs/optimize/<stamp>_<name>/ trials.csv, best.yaml, report.md, plots/*.png, runs/...
"""
from __future__ import annotations

import ast
import copy
import datetime as dt
import functools
import itertools
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml

from . import config as C
from .paths import configs_dir, runs_dir

BASE_UNIT = {"length": "mm", "energy": "keV", "angle": "deg"}
SAFE = {"log": math.log, "log10": math.log10, "exp": math.exp, "sqrt": math.sqrt, "min": min, "max": max,
        "abs": abs, "pi": math.pi}
MIN_WALL_MM = 0.001  # cells must keep at least 1 um of glass between coatings
SAMPLERS = ("lhs", "random", "grid")
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,59}")

Evaluator = Callable[[dict, str, Path], dict]  # (config, name, parent dir) -> metrics ({} if failed)


# ------------------------------------------------------------------ parameters
@dataclass
class Param:
    alias: str
    path: str | None
    kind: str                      # float | int | choice
    low: float = 0.0
    high: float = 1.0
    log: bool = False
    unit_kind: str | None = None   # length | energy | angle | None
    values: list = field(default_factory=list)
    steps: int = 3                 # grid points for float/int in grid sampling

    def value_to_config(self, v):
        if self.kind == "choice":
            return v
        if self.kind == "int":
            return int(round(v))
        return f"{v:.6g} {BASE_UNIT[self.unit_kind]}" if self.unit_kind else float(v)

    def unit_from(self, u: float) -> float:
        """Map u in [0, 1] to the parameter range."""
        if self.log:
            v = math.exp(math.log(self.low) + u * (math.log(self.high) - math.log(self.low)))
        else:
            v = self.low + u * (self.high - self.low)
        return int(round(v)) if self.kind == "int" else v

    def to_unit(self, v: float) -> float:
        if self.log:
            return (math.log(v) - math.log(self.low)) / (math.log(self.high) - math.log(self.low))
        return (v - self.low) / (self.high - self.low)


def _quantity(x) -> tuple[float, str | None]:
    if isinstance(x, (int, float)):
        return float(x), None
    for kind in ("length", "energy", "angle"):
        try:
            return C.quantity(x, kind), kind
        except ValueError:
            continue
    raise ValueError(f"cannot parse {x!r}")


def parse_space(space: dict) -> list[Param]:
    out = []
    for alias, d in space.items():
        if not re.fullmatch(r"[A-Za-z_]\w*", alias):
            raise ValueError(f"parameter alias {alias!r} must be an identifier")
        if not isinstance(d, dict):
            raise ValueError(f"{alias}: expected a mapping (path / low / high or values)")
        if "values" in d:
            if not d["values"]:
                raise ValueError(f"{alias}: empty list of values")
            out.append(Param(alias, d.get("path"), "choice", values=list(d["values"])))
            continue
        if "low" not in d or "high" not in d:
            raise ValueError(f"{alias}: needs low and high (or values)")
        lo, k1 = _quantity(d["low"])
        hi, k2 = _quantity(d["high"])
        if k1 and k2 and k1 != k2:
            raise ValueError(f"{alias}: low is a {k1}, high is a {k2}")
        if hi <= lo:
            raise ValueError(f"{alias}: high must exceed low")
        log = bool(d.get("log", False))
        if log and lo <= 0:
            raise ValueError(f"{alias}: a log scale needs low > 0")
        kind = d.get("type", "float")
        if kind not in ("float", "int"):
            raise ValueError(f"{alias}: type must be float or int")
        out.append(Param(alias, d.get("path"), kind, lo, hi, log, k1 or k2, steps=max(2, int(d.get("steps", 3)))))
    return out


def sample(params: list[Param], n: int, method: str, rng: np.random.Generator) -> list[dict]:
    if method == "grid":
        axes = []
        for p in params:
            if p.kind == "choice":
                axes.append(p.values)
            else:
                axes.append([p.unit_from(u) for u in np.linspace(0, 1, p.steps)])
        return [dict(zip([p.alias for p in params], combo)) for combo in itertools.product(*axes)]
    pts = [{} for _ in range(n)]
    for p in [q for q in params if q.kind == "choice"]:
        # balanced assignment of categories, then shuffled
        vals = [p.values[i % len(p.values)] for i in range(n)]
        rng.shuffle(vals)
        for pt, v in zip(pts, vals):
            pt[p.alias] = v
    # continuous axes: Latin hypercube *within* every combination of categories, so each category
    # covers the whole continuous range (otherwise one category may only get bad corners)
    groups: dict[tuple, list[int]] = {}
    for i, pt in enumerate(pts):
        groups.setdefault(tuple(str(pt.get(p.alias)) for p in params if p.kind == "choice"), []).append(i)
    for p in [q for q in params if q.kind != "choice"]:
        for idx in groups.values():
            m = len(idx)
            u = (rng.permutation(m) + rng.random(m)) / m if method == "lhs" else rng.random(m)
            for i, x in zip(idx, u):
                pts[i][p.alias] = p.unit_from(x)
    return pts


# ------------------------------------------------------------------ expressions
_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Call, ast.Name,
          ast.Load, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub,
          ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In,
          ast.NotIn, ast.Tuple, ast.List)


@functools.lru_cache(maxsize=1024)
def compile_expr(expr: str):
    """Parse an objective / constraint / derived expression; only arithmetic, comparisons, names and
    calls of the SAFE functions are accepted."""
    try:
        tree = ast.parse(str(expr).strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"syntax error in {expr!r}: {e.msg}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _NODES):
            raise ValueError(f"{type(node).__name__} is not allowed in {expr!r}")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError(f"name {node.id!r} is not allowed")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and callable(SAFE.get(node.func.id))
                                               and not node.keywords):
            raise ValueError(f"only {', '.join(k for k, v in SAFE.items() if callable(v))} can be called in {expr!r}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, str, bool)):
            raise ValueError(f"constant {node.value!r} is not allowed")
    return compile(tree, "<spec expression>", "eval")


def expr_names(expr: str) -> set[str]:
    """Metric / parameter names an expression refers to (function names excluded)."""
    compile_expr(expr)
    tree = ast.parse(str(expr).strip(), mode="eval")
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in SAFE}


def safe_eval(expr: str, names: dict) -> Any:
    return eval(compile_expr(expr), {"__builtins__": {}}, {**SAFE, **names})  # noqa: S307 - whitelisted AST


def _num(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


# ------------------------------------------------------------------ the optimiser
class Optimizer:
    def __init__(self, spec: dict, quick: bool = False, evaluator: Evaluator | None = None,
                 out_dir: Path | None = None, extra_sets: list[str] | None = None):
        self.spec = copy.deepcopy(spec)
        # --set overrides become part of the spec, so spec.yaml (resume, scans) keeps them
        fixed = dict(self.spec.get("set") or {})
        for s in extra_sets or []:
            if "=" not in s:
                raise ValueError(f"--set expects key=value, got {s!r}")
            k, v = s.split("=", 1)
            fixed[k.strip()] = C.parse_scalar(v.strip())
        self.spec["set"] = fixed
        self.search = effective_search(self.spec, quick)
        self.params = parse_space(self.spec["space"])
        self.objective = self.spec["objective"]
        self.maximize = self.objective.get("direction", "maximize").startswith("max")
        self.constraints = list(self.spec.get("constraints", []))
        self.rng = np.random.default_rng(int(self.search.get("seed", 1)))
        self.base = C.load(self.spec["base"]) if isinstance(self.spec["base"], str) else copy.deepcopy(self.spec["base"])
        for k, v in fixed.items():
            C.set_path(self.base, k, v)
        self.evaluator = evaluator or default_evaluator
        name = self.spec["name"]
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = out_dir or runs_dir() / "optimize" / f"{stamp}_{name}{'_quick' if quick else ''}"
        (self.dir / "runs").mkdir(parents=True, exist_ok=True)
        self.trials: list[dict] = []
        self._cache: dict[tuple, dict] = {}
        self._planned = plan_search(self.params, self.search)["sims"]
        self._load_existing()

    # ---------------- configuration of one candidate
    def config_for(self, point: dict) -> tuple[dict | None, str]:
        return build_config(self.base, self.params, self.spec.get("derived"), point)

    # ---------------- evaluation with caching / resume
    def _key(self, cfg: dict, events: int, seed: int) -> tuple:
        return (C.digest(cfg), int(events), int(seed))

    def _load_existing(self):
        f = self.dir / "trials.csv"
        if f.exists():
            for row in pd.read_csv(f).to_dict("records"):
                self.trials.append(row)
                self._cache[(row["digest"], int(row["events"]), int(row["seed"]))] = row
            print(f"[srdet] optimize: resumed {len(self.trials)} trials from {f}")

    def evaluate(self, point: dict, events: int, seed: int, stage: str) -> dict:
        cfg, reason = self.config_for(point)
        rec = {"trial": len(self.trials), "stage": stage, "events": int(events), "seed": int(seed),
               **{p.alias: point[p.alias] for p in self.params}}
        if cfg is None:
            rec.update({"digest": "", "ok": False, "feasible": False, "objective": float("nan"),
                        "violations": f"invalid geometry: {reason}", "run_dir": ""})
            self._append(rec)
            return rec
        cfg["run"]["events"] = int(events)
        cfg["run"]["seed"] = int(seed)
        key = self._key(cfg, events, seed)
        if key in self._cache:
            cached = dict(self._cache[key])
            cached.update({"trial": len(self.trials), "stage": stage})
            self._append(cached)
            return cached
        name = f"t{len(self.trials):04d}_{stage}"
        cfg["name"] = f"{self.spec['name']}__{name}"
        metrics = self.evaluator(cfg, cfg["name"], self.dir / "runs")
        rec.update({"digest": key[0], "ok": bool(metrics), "run_dir": metrics.get("_run_dir", "")})
        rec.update({k: v for k, v in metrics.items() if isinstance(v, (int, float)) and not k.startswith("_")})
        obj, feasible, viol = self.score(metrics, point)
        rec.update({"objective": obj, "feasible": feasible, "violations": "; ".join(viol)})
        self._append(rec)
        self._cache[key] = rec
        status = f"{obj:.4g}" if feasible else f"infeasible ({'; '.join(viol)})"
        print(f"[srdet] optimize {name}: {self._fmt(point)} -> {status}")
        return rec

    def score(self, metrics: dict, point: dict) -> tuple[float, bool, list[str]]:
        if not metrics:
            return float("nan"), False, ["run failed"]
        names = {k: _num(v) for k, v in metrics.items() if not k.startswith("_")}
        names.update({k: (v if isinstance(v, str) else float(v)) for k, v in point.items()})
        viol = []
        try:
            obj = float(safe_eval(self.objective["expr"], names))
        except (NameError, ArithmeticError, ValueError, TypeError) as e:  # missing metric, log(0), 1/0 ...
            return float("nan"), False, [f"objective: {e}"]
        if not math.isfinite(obj):
            viol.append("objective is NaN")
        for c in self.constraints:
            try:
                if not safe_eval(c, names):
                    viol.append(c)
            except (NameError, ArithmeticError, ValueError, TypeError) as e:
                viol.append(f"{c} ({e})")
        return obj, not viol, viol

    def _append(self, rec: dict):
        self.trials.append(rec)
        pd.DataFrame(self.trials).to_csv(self.dir / "trials.csv", index=False)
        self._progress(stage=str(rec.get("stage", "")))

    def _progress(self, **extra):
        """progress.json: what the web UI shows while the search is running."""
        done = sum(1 for t in self.trials if not str(t.get("stage", "")).startswith("scan_"))
        info = {"done": done, "planned": self._planned, "updated": dt.datetime.now().isoformat(timespec="seconds"),
                "finished": False, **extra}
        (self.dir / "progress.json").write_text(json.dumps(info))

    def _fmt(self, point: dict) -> str:
        return ", ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}" for k, v in point.items())

    def _rank(self, recs: list[dict]) -> list[dict]:
        sign = -1 if self.maximize else 1
        return sorted(recs, key=lambda r: (not r["feasible"], sign * r["objective"]
                                           if math.isfinite(_num(r["objective"])) else math.inf))

    # ---------------- search
    def run(self) -> Path:
        s = self.search
        # the search actually used (quick budget included) is what a resume must repeat
        saved = {k: v for k, v in self.spec.items() if not k.startswith("_")}
        saved["search"] = copy.deepcopy(s)
        (self.dir / "spec.yaml").write_text(yaml.safe_dump(saved, sort_keys=False, allow_unicode=True))
        # resume: previous trials stay in the cache and are re-appended in order as the search
        # reaches them again (no duplicates in trials.csv); one-parameter scans are kept as they are
        self.trials = [t for t in self.trials if str(t.get("stage", "")).startswith("scan_")]
        seed0 = int(s.get("seed", 1)) * 100000
        events = [int(e) for e in s.get("events", [300])]
        points = sample(self.params, int(s.get("initial", 12)), s.get("sampler", "lhs"), self.rng)
        eta = float(s.get("eta", 3))
        survivors = points
        for k, ev in enumerate(events):
            recs = [self.evaluate(pt, ev, seed0 + 1000 * k + i, f"s{k}") for i, pt in enumerate(survivors)]
            ranked = self._rank(recs)
            if k < len(events) - 1:
                keep = max(1, math.ceil(len(ranked) / eta))
                survivors = [self._point(r) for r in ranked[:keep] if r["feasible"]] or [self._point(ranked[0])]
        self._last_stage = f"s{len(events) - 1}"
        best = self._rank([r for r in self.trials if r["stage"] == self._last_stage])[0]

        ref = s.get("refine")
        if ref:
            best = self.refine(self._point(best), best, ref, seed0 + 500000)

        fin = s.get("final") or {}
        top = int(fin.get("top", 0))
        if top:
            self.validate(top, int(fin.get("events", events[-1])), int(fin.get("repeats", 3)), seed0 + 900000)
        return self.report()

    def _point(self, rec: dict) -> dict:
        pt = {}
        for p in self.params:
            v = rec[p.alias]
            pt[p.alias] = v if p.kind == "choice" else (int(round(float(v))) if p.kind == "int" else float(v))
        return pt

    def refine(self, point: dict, best: dict, ref: dict, seed: int) -> dict:
        """Coordinate search around the best point: other values of each categorical parameter,
        then +-step on every continuous parameter (unit cube, log-aware); the step halves when a
        full sweep brings no improvement."""
        step = float(ref.get("step", 0.2))
        gain = float(ref.get("min_gain", 0.03))
        ev = int(ref.get("events", self.search.get("events", [300])[-1]))
        cur = self.evaluate(point, ev, seed, "r0") if int(best["events"]) != ev else best
        it = 0
        for it in range(1, int(ref.get("iterations", 6)) + 1):
            improved = False
            # categorical moves: every other value of each category at the current point
            for p in [q for q in self.params if q.kind == "choice"]:
                for v in p.values:
                    if str(v) == str(point[p.alias]):
                        continue
                    cand = dict(point, **{p.alias: v})
                    rec = self.evaluate(cand, ev, seed + it, f"r{it}")
                    if self._better(rec, cur, gain):
                        point, cur, improved = cand, rec, True
            for p in [q for q in self.params if q.kind != "choice"]:
                for sgn in (+1, -1):
                    u = min(1.0, max(0.0, p.to_unit(float(point[p.alias])) + sgn * step))
                    cand = dict(point, **{p.alias: p.unit_from(u)})
                    if cand[p.alias] == point[p.alias]:
                        continue
                    rec = self.evaluate(cand, ev, seed + it, f"r{it}")
                    if self._better(rec, cur, gain):
                        point, cur, improved = cand, rec, True
                        break
            if not improved:
                step /= 2
                if step < 0.01:
                    break
        return cur

    def _better(self, a: dict, b: dict, gain: float) -> bool:
        if not a["feasible"]:
            return False
        if not b["feasible"]:
            return True
        oa, ob = float(a["objective"]), float(b["objective"])
        rel = (oa - ob) / max(abs(ob), 1e-12)
        return rel > gain if self.maximize else -rel > gain

    def validate(self, top: int, events: int, repeats: int, seed: int):
        """Re-run the best distinct candidates with fresh seeds; report mean +- std."""
        seen, cands = set(), []
        for r in self._rank([t for t in self.trials if t["feasible"]]):
            key = tuple(str(r[p.alias]) for p in self.params)
            if key not in seen:
                seen.add(key)
                cands.append(self._point(r))
            if len(cands) >= top:
                break
        for i, pt in enumerate(cands):
            for j in range(repeats):
                self.evaluate(pt, events, seed + 100 * i + j, f"final{i}")

    # ---------------- reporting
    def summary_table(self) -> pd.DataFrame:
        df = pd.DataFrame(self.trials)
        fin = df[df["stage"].astype(str).str.startswith("final")]
        if not len(fin):
            return pd.DataFrame()
        aliases = [p.alias for p in self.params]
        metric_cols = [c for c in fin.columns if c not in aliases + ["trial", "stage", "events", "seed", "digest",
                                                                      "ok", "feasible", "violations", "run_dir"]]
        g = fin.groupby("stage")
        rows = []
        for stage, grp in g:
            row = {a: grp[a].iloc[0] for a in aliases}
            row["n"] = len(grp)
            row["feasible_all"] = bool(grp["feasible"].all())
            for c in metric_cols:
                vals = pd.to_numeric(grp[c], errors="coerce")
                row[c] = vals.mean()
                row[f"{c}_std"] = vals.std(ddof=1) if len(vals) > 1 else 0.0
            rows.append(row)
        out = pd.DataFrame(rows)
        # candidates that violated a constraint in any repeat never come before feasible ones
        out["_rank"] = ~out["feasible_all"]
        out = out.sort_values(["_rank", "objective"], ascending=[True, not self.maximize], na_position="last")
        return out.drop(columns="_rank").reset_index(drop=True)

    def report(self) -> Path:
        from .optimize_plots import convergence, pareto, sensitivity

        df = pd.DataFrame(self.trials)
        plots = [convergence(df, self.dir / "plots" / "convergence.png", self.maximize, self.spec),
                 *sensitivity(df, self.params, self.dir / "plots", self.spec)]
        par = self.spec.get("pareto")
        front = None
        if par:
            path, front = pareto(df, par, self.dir / "plots" / "pareto.png", self.spec, self.params)
            plots.append(path)
        summary = self.summary_table()
        if len(summary):
            summary.to_csv(self.dir / "final.csv", index=False)
            best_row = summary.iloc[0]
            best_pt = self._point(best_row)
        else:
            best_rec = self._rank(self.trials)[0]
            best_row, best_pt = pd.Series(best_rec), self._point(best_rec)
        n_feasible = int(df["feasible"].astype(bool).sum()) if "feasible" in df else 0
        cfg, why_not = self.config_for(best_pt)
        best_yaml = self.write_best(cfg, best_row) if cfg is not None else None
        if best_yaml is None:
            (self.dir / "best.yaml").unlink(missing_ok=True)

        aliases = [p.alias for p in self.params]
        key_metrics = [m for m in dict.fromkeys(self.spec.get("report_metrics", []) +
                                                re.findall(r"[A-Za-z_]\w*", self.objective["expr"]) +
                                                [re.split(r"[<>=! ]", c.strip())[0] for c in self.constraints])
                       if m in df.columns and m not in aliases and m not in SAFE]
        n_runs = int((df["digest"] != "").sum()) if "digest" in df else len(df)
        lines = [f"# {self.spec.get('title', self.spec['name'])}", "",
                 str(self.spec.get("description", "")).strip(), "",
                 f"* Base configuration: `{self.spec['base']}`, fixed: `{self.spec.get('set') or {}}`",
                 f"* Objective: `{self.objective['expr']}` ({'maximise' if self.maximize else 'minimise'})",
                 f"* Constraints: {', '.join(f'`{c}`' for c in self.constraints) or 'none'}",
                 f"* Search: `{ {k: v for k, v in self.search.items()} }`",
                 f"* Simulations: {n_runs}, feasible: {n_feasible} / {len(df)}", "",
                 "## Метод поиска", ""] + [f"{i}. {st['text']}" for i, st in
                                           enumerate(plan_search(self.params, self.search)["steps"], 1)] + [""]
        if not n_feasible:
            lines += ["> **No trial satisfied the constraints.** The configuration below is the least bad "
                      "one; relax the constraints or widen the parameter ranges.", ""]
        lines += ["## Best configuration", "",
                  "Validated with independent seeds (mean ± std):" if len(summary) else
                  "Best trial of the last stage (no validation stage):", ""]
        for a in aliases:
            lines.append(f"* **{a}** = {best_row[a]}")
        for mname in ["objective"] + key_metrics:
            if mname in best_row:
                std = best_row.get(f"{mname}_std")
                lines.append(f"* {mname} = {_num(best_row[mname]):.4g}" +
                             (f" ± {_num(std):.2g}" if std is not None and math.isfinite(_num(std)) else ""))
        from .paths import repo_root
        if best_yaml is not None:
            rel = best_yaml.relative_to(repo_root()) if best_yaml.is_relative_to(repo_root()) else best_yaml
            lines += ["", f"Ready-to-run configuration: [`best.yaml`](best.yaml) (`srdet run {rel}`)", ""]
        else:
            lines += ["", f"No `best.yaml`: the best point is not a valid geometry ({why_not}).", ""]
        if len(summary):
            cols = aliases + ["objective", "objective_std"] + [m for m in key_metrics if m in summary]
            lines += ["## Validated candidates", "", summary[cols].to_markdown(index=False, floatfmt=".4g"), ""]
        last = df[df["stage"] == getattr(self, "_last_stage", None)]
        top = pd.DataFrame(self._rank((last if len(last) else df).to_dict("records"))[:10])
        if len(top):
            cols = ["trial", "stage", "events"] + aliases + ["objective", "feasible"] + key_metrics
            lines += ["## Top of the last screening stage", "",
                      top[[c for c in cols if c in top]].to_markdown(index=False, floatfmt=".4g"), ""]
        if front is not None and len(front):
            lines += ["## Pareto front", "", front.to_markdown(index=False, floatfmt=".4g"), ""]
        lines += ["## Plots", ""] + [f"![{p.stem}](plots/{p.name})" for p in plots if p] + [""]
        lines += ["## Notes", "",
                  "* Screening stages use few events: rankings there are noisy, which is why the best "
                  "fraction is re-simulated with more statistics and fresh seeds (successive halving).",
                  "* Infeasible trials (violated constraints, impossible geometry) are kept in `trials.csv` "
                  "with the reason in `violations`.", ""]
        (self.dir / "report.md").write_text("\n".join(lines))
        self._progress(finished=True)
        print(f"[srdet] optimize done: {self.dir / 'report.md'}")
        return self.dir

    def write_best(self, cfg: dict, row) -> Path:
        base = self.spec["base"]
        over: dict = {}
        flat_paths = [p.path for p in self.params if p.path] + list((self.spec.get("derived") or {}).keys()) + \
            list((self.spec.get("set") or {}).keys())
        for path in flat_paths:
            C.set_path(over, path, C.get_path(cfg, path))
        over.setdefault("run", {}).pop("seed", None)
        doc = {"extends": base if isinstance(base, str) else None, "name": f"{self.spec['name']}_best",
               "description": f"Best configuration found by optimisation {self.spec['name']} "
                              f"(objective {self.objective['expr']} = {_num(row['objective']):.4g})",
               **over}
        path = self.dir / "best.yaml"
        path.write_text(yaml.safe_dump({k: v for k, v in doc.items() if v is not None}, sort_keys=False,
                                       allow_unicode=True))
        return path


# ------------------------------------------------------------------ helpers
DEFAULT_QUICK = {"initial": 6, "events": [50, 150], "refine": None, "final": {"top": 1, "events": 200, "repeats": 2}}
SAMPLER_TEXT = {"lhs": "латинским гиперкубом (по каждой непрерывной оси ровно одна точка на интервал, "
                       "категории поровну, внутри каждой категории — весь диапазон)",
                "random": "случайно, равномерно в диапазонах", "grid": "полным перебором сетки"}


def effective_search(spec: dict, quick: bool = False) -> dict:
    search = dict(spec.get("search") or {})
    if quick:
        search.update(spec.get("quick") or DEFAULT_QUICK)
    return search


def build_config(base: dict, params: list[Param], derived: dict | None, point: dict) -> tuple[dict | None, str]:
    """Configuration of one candidate; (None, reason) when its geometry cannot be built."""
    cfg = copy.deepcopy(base)
    for p in params:
        if p.path:
            C.set_path(cfg, p.path, p.value_to_config(point[p.alias]))
    names = {k: (v if isinstance(v, str) else float(v)) for k, v in point.items()}
    for path, d in (derived or {}).items():
        d = d if isinstance(d, dict) else {"expr": d}
        v = safe_eval(d["expr"], names)
        unit = d.get("unit")
        C.set_path(cfg, path, f"{v:.6g} {unit}" if unit else v)
    reason = geometry_problem(cfg)
    return (None, reason) if reason else (cfg, "")


def _n(x) -> str:
    return f"{int(x):,}".replace(",", " ")


def plan_search(params: list[Param], search: dict) -> dict:
    """The search as a list of stages with simulation counts and a plain-language description
    (shown in the web UI before the launch and in report.md)."""
    sampler = search.get("sampler", "lhs")
    if sampler == "grid":
        n = math.prod(len(p.values) if p.kind == "choice" else p.steps for p in params) if params else 1
    else:
        n = int(search.get("initial", 12))
    events = [int(e) for e in search.get("events", [300])] or [300]
    eta = float(search.get("eta", 3))
    steps, sims, total = [], 0, 0
    for k, ev in enumerate(events):
        if k == 0:
            text = f"Отбор: {_n(n)} кандидатов, выбранных {SAMPLER_TEXT.get(sampler, sampler)}, по {_n(ev)} событий."
        else:
            text = (f"Отсев: лучшие {_n(n)} (доля 1/{eta:g} предыдущей ступени, допустимые впереди) пересчитываются "
                    f"с {_n(ev)} событий и новыми seed — шумные оценки малой статистики отсеивают только явно плохих.")
        steps.append({"id": f"s{k}", "kind": "screen" if k == 0 else "halving", "candidates": n, "events": ev,
                      "sims": n, "text": text})
        sims, total = sims + n, total + n * ev
        if k < len(events) - 1:
            n = max(1, math.ceil(n / eta))
    ref = search.get("refine")
    if ref:
        moves = sum(len(p.values) - 1 for p in params if p.kind == "choice") + \
            2 * sum(1 for p in params if p.kind != "choice")
        it, ev = int(ref.get("iterations", 6)), int(ref.get("events", events[-1]))
        m = (1 if ev != events[-1] else 0) + it * moves
        steps.append({"id": "refine", "kind": "refine", "candidates": m, "events": ev, "sims": m,
                      "text": f"Уточнение вокруг лучшей точки, до {it} итераций: пробуются другие значения каждой "
                              f"категории и ±{float(ref.get('step', 0.2)):g} диапазона по каждой непрерывной оси "
                              f"(для log-осей — в логарифме). Шаг принимается, если цель выросла больше чем на "
                              f"{100 * float(ref.get('min_gain', 0.03)):g} %, иначе шаг уменьшается вдвое. "
                              f"Не более {_n(m)} симуляций по {_n(ev)} событий."})
        sims, total = sims + m, total + m * ev
    fin = search.get("final") or {}
    top = int(fin.get("top", 0) or 0)
    if top:
        rep, ev = int(fin.get("repeats", 3)), int(fin.get("events", events[-1]))
        steps.append({"id": "final", "kind": "final", "candidates": top * rep, "events": ev, "sims": top * rep,
                      "text": f"Проверка: {top} лучших различных кандидатов × {rep} повтора с новыми seed по "
                              f"{_n(ev)} событий. Итог — среднее ± σ; best.yaml берётся по проверке."})
        sims, total = sims + top * rep, total + top * rep * ev
    else:
        steps.append({"id": "final", "kind": "final", "candidates": 0, "events": 0, "sims": 0,
                      "text": "Проверки повторами нет: лучший берётся из последней ступени (оценка шумнее)."})
    return {"steps": steps, "sims": sims, "events": total}


def _known_metric(name: str) -> bool:
    from .labels import METRIC_HELP
    return name in METRIC_HELP or bool(re.match(r"(first_|mean_|fate_|coat_)\w+$", name))


_MISSING = object()


def check_spec(spec: dict, quick: bool = False) -> dict:
    """Validate a spec without simulating: errors block the launch, warnings are hints.
    Also returns the search plan (stages, simulations, events)."""
    errors: list[str] = []
    warnings: list[str] = []
    defaults = C.load(None)
    name = str(spec.get("name") or "")
    if not NAME_RE.fullmatch(name):
        errors.append("name: латиница, цифры, _ и -, до 60 символов (это имя папки результата)")
    base = None
    if not spec.get("base"):
        errors.append("base: выберите базовую конфигурацию детектора")
    else:
        try:
            base = C.load(spec["base"]) if isinstance(spec["base"], str) else copy.deepcopy(spec["base"])
        except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
            errors.append(f"base: {e}")
    for k, v in (spec.get("set") or {}).items():
        if C.get_path(defaults, k, _MISSING) is _MISSING:
            warnings.append(f"фиксированный параметр {k} не найден в defaults.yaml — опечатка?")
        if base is not None:
            C.set_path(base, k, v)
    params: list[Param] = []
    space_ok = True
    try:
        params = parse_space(spec.get("space") or {})
        if not params:
            errors.append("space: нужен хотя бы один свободный параметр")
    except (ValueError, KeyError, TypeError) as e:
        errors.append(f"space: {e}")
        space_ok = False
    aliases = {p.alias for p in params}
    derived = spec.get("derived") or {}
    used_in_derived: set[str] = set()
    for path, d in derived.items():
        expr = d.get("expr") if isinstance(d, dict) else d
        try:
            names = expr_names(expr)
            used_in_derived |= names
            if space_ok and names - aliases:
                errors.append(f"derived {path}: неизвестные имена {sorted(names - aliases)} (можно только параметры)")
        except ValueError as e:
            errors.append(f"derived {path}: {e}")
        if C.get_path(defaults, path, _MISSING) is _MISSING:
            warnings.append(f"derived {path}: такого ключа нет в defaults.yaml")
    for p in params:
        if p.path and C.get_path(defaults, p.path, _MISSING) is _MISSING:
            warnings.append(f"{p.alias}: ключа {p.path} нет в defaults.yaml — значение ни на что не повлияет")
        if not p.path and p.alias not in used_in_derived:
            warnings.append(f"{p.alias}: параметр без path не используется в derived — он ничего не меняет")
    if any(p.path == "run.events" for p in params):
        warnings.append("run.events задаётся ступенями поиска, свободный параметр будет перезаписан")
    obj = spec.get("objective") or {}
    expr_list = []
    if not obj.get("expr"):
        errors.append("objective: задайте выражение цели")
    else:
        expr_list.append(("цель", obj["expr"]))
    if str(obj.get("direction", "maximize"))[:3] not in ("max", "min"):
        errors.append("objective.direction: maximize или minimize")
    for c in spec.get("constraints") or []:
        expr_list.append(("ограничение", c))
        try:
            tree = ast.parse(str(c).strip(), mode="eval")
            if not isinstance(tree.body, (ast.Compare, ast.BoolOp)):
                warnings.append(f"ограничение {c!r} не является сравнением (нужно, например, 'psf_r50_um <= 120')")
        except SyntaxError:
            pass
    for what, e in expr_list:
        try:
            for n in sorted(expr_names(e) - aliases):
                if not _known_metric(n):
                    warnings.append(f"{what} {e!r}: неизвестная метрика {n} — без неё испытание будет недопустимым")
        except ValueError as err:
            errors.append(f"{what}: {err}")
    par = spec.get("pareto")
    if par:
        for ax in ("x", "y"):
            if not par.get(ax):
                errors.append(f"pareto.{ax}: выберите метрику")
            elif not _known_metric(par[ax]):
                warnings.append(f"pareto.{ax}: неизвестная метрика {par[ax]}")
    search = effective_search(spec, quick)
    if search.get("sampler", "lhs") not in SAMPLERS:
        errors.append(f"search.sampler: одно из {', '.join(SAMPLERS)}")
    try:
        events = [int(e) for e in search.get("events", [300])]
        if not events or min(events) < 1:
            errors.append("search.events: положительные числа событий по ступеням")
        elif any(b < a for a, b in zip(events, events[1:])):
            warnings.append("search.events: статистика обычно растёт от ступени к ступени")
        if len(events) > 1 and float(search.get("eta", 3)) <= 1:
            errors.append("search.eta должно быть > 1 (во сколько раз сокращается число кандидатов)")
        if search.get("sampler", "lhs") != "grid" and int(search.get("initial", 12)) < 1:
            errors.append("search.initial: хотя бы один кандидат")
        plan = plan_search(params, search)
    except (TypeError, ValueError) as e:
        errors.append(f"search: {e}")
        plan = {"steps": [], "sims": 0, "events": 0}
    if search.get("sampler") == "grid" and plan["steps"] and plan["steps"][0]["candidates"] > 300:
        warnings.append(f"сетка из {plan['steps'][0]['candidates']} точек — это долго; уменьшите steps или значения")
    invalid = None
    if base is not None and params and not errors:
        pts = sample(params, 24, "lhs" if search.get("sampler") != "grid" else "grid", np.random.default_rng(0))
        bad = []
        for pt in pts:
            try:
                cfg, why = build_config(base, params, derived, pt)
            except (ValueError, ArithmeticError, TypeError, NameError) as e:
                cfg, why = None, str(e)
            if cfg is None:
                bad.append(why)
        invalid = len(bad) / max(1, len(pts))
        if bad and len(bad) == len(pts):
            errors.append(f"ни одна пробная точка не даёт допустимую геометрию: {bad[0]}")
        elif bad:
            warnings.append(f"{len(bad)} из {len(pts)} пробных точек — невозможная геометрия ({bad[0]}); "
                            "они не симулируются, но тратят место в отборе")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "plan": plan, "search": search,
            "invalid_fraction": invalid}


def geometry_problem(cfg: dict) -> str:
    g = cfg["geometry"]
    if g.get("mode") == "slab":
        return ""
    try:
        pitch = C.quantity(g["pitch"], "length")
        d = C.quantity(g["channel_diameter"], "length")
        t = C.quantity(g["coating_thickness"], "length")
        length = C.quantity(g["length"], "length")
    except (KeyError, ValueError) as e:
        return f"cannot read geometry ({e})"
    if d <= 0 or length <= 0:
        return "non-positive size"
    if pitch - d - 2 * t < MIN_WALL_MM:
        return f"wall {1000 * (pitch - d - 2 * t):.2f} um < {1000 * MIN_WALL_MM:.0f} um"
    if g.get("mode") == "full":
        r = C.quantity(g["detector_radius"], "length")
        n_cells = math.pi * r * r / (math.sqrt(3) / 2 * pitch * pitch)
        if n_cells > 3e5:
            return f"{n_cells:.0f} cells: too many for the full detector (raise D or lower detector_radius)"
    return ""


def default_evaluator(cfg: dict, name: str, parent: Path) -> dict:
    from .runner import run
    res = run(cfg, name=name, parent=parent, backup=False, quiet=True, plots=False)
    mf = res.path / "metrics.json"
    if not res.ok or not mf.exists():
        return {}
    m = json.loads(mf.read_text())
    m["_run_dir"] = str(res.path.relative_to(parent.parent))
    return m


def spec_files() -> dict[str, Path]:
    return {p.stem: p for p in sorted((configs_dir() / "optimize").glob("*.yaml"))}


def load_spec(name_or_path: str) -> dict:
    p = Path(name_or_path)
    if not p.exists():
        files = spec_files()
        matches = [v for k, v in files.items() if k == name_or_path or k.startswith(name_or_path)]
        if not matches:
            raise FileNotFoundError(f"optimisation {name_or_path} not found; available: {', '.join(files)}")
        p = matches[0]
    return yaml.safe_load(p.read_text())


def scan_parameter(opt_dir: Path, alias: str, points: int = 6, events: int | None = None,
                   evaluator: Evaluator | None = None) -> Path:
    """Vary one parameter over its whole range with all others fixed at the best point of a
    finished optimisation; the new trials (stage 'scan_<alias>') are added to trials.csv."""
    spec = yaml.safe_load((opt_dir / "spec.yaml").read_text())
    opt = Optimizer(spec, out_dir=opt_dir, evaluator=evaluator)
    p = next((q for q in opt.params if q.alias == alias), None)
    if p is None:
        raise ValueError(f"{alias} is not a parameter of {spec['name']}: {[q.alias for q in opt.params]}")
    final = opt.dir / "final.csv"
    best = (pd.read_csv(final).iloc[0].to_dict() if final.exists()
            else opt._rank([t for t in opt.trials if t.get("feasible")] or opt.trials)[0])
    base = opt._point(best)
    values = p.values if p.kind == "choice" else sorted({p.unit_from(u) for u in np.linspace(0, 1, max(2, points))})
    ev = int(events or best.get("events") or opt.search.get("events", [1000])[-1])
    seed = int(opt.search.get("seed", 1)) * 100000 + 700000
    for i, v in enumerate(values):
        opt.evaluate(dict(base, **{alias: v}), ev, seed + i, f"scan_{alias}")
    return opt.report()


def run_optimization(name_or_path: str, quick: bool = False, resume: Path | None = None,
                     extra_sets: list[str] | None = None) -> Path:
    spec = load_spec(name_or_path)
    if resume and (resume / "spec.yaml").exists():
        spec = yaml.safe_load((resume / "spec.yaml").read_text())  # continue with the original spec
    # finished trials are reused from trials.csv (same config, events and seed -> no new simulation)
    return Optimizer(spec, quick=quick, out_dir=resume, extra_sets=extra_sets).run()
