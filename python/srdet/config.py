"""YAML configuration: inheritance (`extends:`), dotted overrides and unit-aware quantities.

A config file may contain `extends: other.yaml` (path relative to the file or to configs/);
the chain always starts at configs/defaults.yaml, which documents every key.
"""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from .paths import configs_dir

UNITS = {
    "length": {"nm": 1e-6, "um": 1e-3, "mm": 1.0, "cm": 10.0, "m": 1000.0},
    "energy": {"eV": 1e-3, "keV": 1.0, "MeV": 1e3, "GeV": 1e6},
    "angle": {"deg": 1.0, "rad": 57.29577951308232, "mrad": 0.05729577951308232},
}
BASE = {"length": "mm", "energy": "keV", "angle": "deg"}
_Q = re.compile(r"^\s*([-+0-9.eE]+)\s*([A-Za-z]+)?\s*$")


def quantity(value: Any, kind: str) -> float:
    """'200 um' -> 0.2 (mm); bare numbers are taken in the base unit (mm, keV, deg)."""
    if isinstance(value, (int, float)):
        return float(value)
    m = _Q.match(str(value))
    if not m:
        raise ValueError(f"cannot parse {kind} quantity {value!r}")
    num, unit = float(m.group(1)), m.group(2)
    if unit is None:
        return num
    try:
        return num * UNITS[kind][unit]
    except KeyError as e:
        raise ValueError(f"unknown {kind} unit {unit!r} in {value!r}") from e


def g4(value: Any, kind: str) -> str:
    """Quantity formatted for a Geant4 command ('0.2 mm')."""
    return f"{quantity(value, kind):.10g} {BASE[kind]}"


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _resolve(path: str | Path, rel_to: Path | None) -> Path:
    p = Path(path)
    if p.is_absolute() and p.exists():
        return p
    for cand in ([rel_to / p] if rel_to else []) + [Path.cwd() / p, configs_dir() / p,
                                                    configs_dir() / "detector" / p]:
        if cand.exists():
            return cand.resolve()
        if cand.with_suffix(".yaml").exists():
            return cand.with_suffix(".yaml").resolve()
    raise FileNotFoundError(f"config {path} not found")


def load(path: str | Path | None, _rel: Path | None = None, _seen: tuple = ()) -> dict:
    defaults = configs_dir() / "defaults.yaml"
    if path is None:
        return yaml.safe_load(defaults.read_text())
    p = _resolve(path, _rel)
    if p in _seen:
        raise ValueError(f"circular extends: {p}")
    data = yaml.safe_load(p.read_text()) or {}
    parent = data.pop("extends", None)
    if parent:
        base = load(parent, p.parent, _seen + (p,))
    elif p.resolve() != defaults.resolve():
        base = yaml.safe_load(defaults.read_text())
    else:
        base = {}
    cfg = deep_merge(base, data)
    cfg.setdefault("_sources", [])
    cfg["_sources"] = list(base.get("_sources", [])) + [str(p)]
    return cfg


def parse_scalar(text: str) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return text


def set_path(cfg: dict, dotted: str, value: Any) -> None:
    node = cfg
    keys = dotted.split(".")
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    if isinstance(value, dict) and isinstance(node.get(keys[-1]), dict) and not _replaces(keys[-1]):
        node[keys[-1]] = deep_merge(node[keys[-1]], value)  # partial update of a sub-section
    else:
        node[keys[-1]] = value


def _replaces(key: str) -> bool:
    """Keys whose dict value is a complete object (not a partial update)."""
    return key in ("spectrum",)


def get_path(cfg: dict, dotted: str, default: Any = None) -> Any:
    node: Any = cfg
    for k in dotted.split("."):
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def apply_sets(cfg: dict, sets: list[str] | None) -> dict:
    """--set geometry.length=10mm  (value parsed as YAML scalar)"""
    cfg = copy.deepcopy(cfg)
    for s in sets or []:
        if "=" not in s:
            raise ValueError(f"--set expects key=value, got {s!r}")
        k, v = s.split("=", 1)
        set_path(cfg, k.strip(), parse_scalar(v.strip()))
    return cfg


def dump(cfg: dict) -> str:
    return yaml.safe_dump({k: v for k, v in cfg.items()}, sort_keys=False, allow_unicode=True)


def digest(cfg: dict) -> str:
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    return hashlib.sha1(yaml.safe_dump(clean, sort_keys=True).encode()).hexdigest()[:10]
