"""Form schema for the web UI, derived from configs/defaults.yaml: every leaf key becomes a field
with its default, type, unit, help text (the trailing comment) and choices from the catalogues."""
from __future__ import annotations

import re

import yaml

from .. import catalog, spectra
from ..paths import configs_dir

_LINE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][\w]*):\s*(?P<value>[^#]*?)\s*(?:#\s*(?P<comment>.*))?$")
_QTY = re.compile(r"^\s*[-+0-9.eE]+\s*(nm|um|mm|cm|m|eV|keV|MeV|GeV|deg|rad|mrad)\s*$")
UNIT_KIND = {"nm": "length", "um": "length", "mm": "length", "cm": "length", "m": "length", "eV": "energy",
             "keV": "energy", "MeV": "energy", "GeV": "energy", "deg": "angle", "rad": "angle", "mrad": "angle"}

GLASSES = catalog.GLASSES + ["G4_Pyrex_Glass", "G4_SILICON_DIOXIDE", "G4_GLASS_PLATE"]
CHOICES = {
    "geometry.mode": ["full", "cluster7", "unit", "slab"],
    "geometry.channel_shape": ["circle", "hex"],
    "geometry.core_material": list(catalog.SCINTILLATORS),
    "geometry.slab_material": list(catalog.SCINTILLATORS) + GLASSES + ["G4_Al", "G4_Si", "G4_WATER", "G4_Pb"],
    "geometry.wall_material": GLASSES,
    "geometry.matrix_material": [""] + GLASSES,
    "geometry.coating_material": ["", "G4_Al", "G4_Ag", "G4_Au", "G4_TITANIUM_DIOXIDE", "G4_BARIUM_SULFATE",
                                  "G4_TEFLON", "G4_MYLAR", "Air"],
    "geometry.world_material": ["Air", "Vacuum"],
    "geometry.housing_material": ["G4_Al", "G4_STAINLESS-STEEL", "G4_Cu", "G4_W", "CarbonFiber"],
    "geometry.window_material": ["G4_Be", "G4_Al", "CarbonFiber", "G4_KAPTON", "G4_MYLAR"],
    "geometry.coupling_material": ["OpticalGrease", "Epoxy", "Air"],
    "geometry.sensor": list(catalog.SENSORS),
    "optics.coating": list(catalog.COATINGS),
    "optics.entrance_coating": list(catalog.COATINGS),
    "physics.em": ["livermore", "option4", "penelope", "standard", "option3"],
    "beam.type": ["pencil", "parallel", "gauss", "divergent", "isotropic", "optical", "macro"],
    "beam.particle": ["gamma", "e-", "e+", "mu-", "proton", "alpha", "neutron", "geantino"],
}
HELP = {
    "geometry.core_material": {k: f"{v[0]:,} ph/MeV, τ={v[1]} ns, λ={v[2]} nm"
                               for k, v in catalog.SCINTILLATORS.items()},
    "optics.coating": catalog.COATINGS,
    "optics.entrance_coating": catalog.COATINGS,
    "geometry.sensor": {k: f"{v[0]}; fill {v[1]}, pixel {v[2]} mm, noise {v[3]} e-, cost ×{v[4]}"
                        for k, v in catalog.SENSORS.items()},
}
SECTION_TITLES = {"geometry": "Геометрия", "optics": "Оптика и покрытия", "materials": "Материалы",
                  "physics": "Физика", "beam": "Пучок", "run": "Прогон"}


def _kind(value):
    if isinstance(value, bool):
        return "bool", None
    if isinstance(value, int):
        return "int", None
    if isinstance(value, float):
        return "float", None
    if isinstance(value, str) and _QTY.match(value):
        unit = value.split()[-1] if " " in value.strip() else re.sub(r"[-+0-9.eE]", "", value)
        return "quantity", unit
    if isinstance(value, list):
        return "list", None
    if value is None or isinstance(value, dict):
        return "special", None
    return "string", None


def form_schema() -> dict:
    lines = (configs_dir() / "defaults.yaml").read_text().splitlines()
    stack: list[tuple[int, str]] = []
    sections: dict[str, list] = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        indent = len(m["indent"])
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key, raw = m["key"], m["value"]
        if raw == "":
            stack.append((indent, key))
            continue
        path = ".".join([k for _, k in stack] + [key])
        if "." not in path:
            continue  # name / description
        try:
            value = yaml.safe_load(raw)
        except yaml.YAMLError:
            value = raw
        kind, unit = _kind(value)
        field = {"path": path, "key": key, "default": value, "kind": kind, "unit": unit,
                 "unit_kind": UNIT_KIND.get(unit), "help": (m["comment"] or "").strip()}
        if path in CHOICES:
            field["choices"] = CHOICES[path]
            field["kind"] = "choice" if kind in ("string", "special") else kind
        if path in HELP:
            field["choice_help"] = HELP[path]
        sections.setdefault(path.split(".")[0], []).append(field)
    return {"sections": [{"id": s, "title": SECTION_TITLES.get(s, s), "fields": f} for s, f in sections.items()],
            "spectra": {"sources": list(spectra.NUCLIDES)}}
