"""Web API tests (FastAPI TestClient, no Geant4): schema, configs, macro preview, run browsing,
geometry, file access control, job validation and result parsing."""
from __future__ import annotations

import json
import shutil
import uuid

import pytest

from conftest import ROOT

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from srdet.web.jobs import JobManager  # noqa: E402
from srdet.web.server import create_app  # noqa: E402


@pytest.fixture(scope="module")
def fake_run():
    d = ROOT / "runs" / f"zz_test_web_{uuid.uuid4().hex[:6]}"
    (d / "plots").mkdir(parents=True)
    (d / "config.yaml").write_text("name: fake\ngeometry: {mode: unit, length: 2 mm, coating_thickness: 2 um}\n"
                                   "optics: {coating: Ag}\nbeam: {particle: gamma, energy: 60 keV, type: pencil}\n")
    (d / "metrics.json").write_text(json.dumps({"det_yield_per_keV": 8.2, "detection_efficiency": 0.9,
                                                "lce": float("nan"), "sanity_problems": []}))
    (d / "meta.json").write_text(json.dumps({"name": "fake", "wall_time_s": 1.5}))
    (d / "STATUS").write_text("ok\n")
    (d / "geometry.json").write_text(json.dumps({"mode": "unit", "pitch_mm": 0.208, "channel_diameter_mm": 0.2,
                                                 "matrix_radius_mm": 0.121, "cells": [[0, 0, 0.0, 0.0]],
                                                 "n_cells": 1, "length_mm": 2, "z_front_mm": -1.5,
                                                 "z_back_mm": 1.07, "z_sensor_mm": 1.05}))
    (d / "plots" / "edep_spectrum.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    yield d.relative_to(ROOT).as_posix()
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    jm = JobManager(tmp_path_factory.mktemp("jobs"))
    return TestClient(create_app(jm))


def test_index_and_static(client):
    assert "SRDetector" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.js").headers["cache-control"] == "no-cache"


def test_schema_has_typed_fields(client):
    s = client.get("/api/schema").json()
    fields = {f["path"]: f for sec in s["sections"] for f in sec["fields"]}
    assert fields["geometry.length"]["kind"] == "quantity" and fields["geometry.length"]["unit_kind"] == "length"
    assert "Ag" in fields["optics.coating"]["choices"]
    assert fields["geometry.check_overlaps"]["kind"] == "bool"
    assert fields["beam.spectrum"]["kind"] == "special"
    assert fields["geometry.pitch"]["help"]  # trailing comment of defaults.yaml
    assert "Am241" in s["spectra"]["sources"]


def test_configs_and_macro(client):
    names = [c["name"] for c in client.get("/api/configs").json()]
    assert "full" in names and "unit_optical" in names
    cfg = client.get("/api/configs/full").json()
    assert cfg["geometry"]["mode"] == "full"
    r = client.post("/api/macro", json={"base": "unit_xray", "overrides": {"geometry.length": "2 mm"}})
    assert r.status_code == 200 and "/srdet/geom/length 2 mm" in r.json()["macro"]


def test_run_browsing(client, fake_run):
    runs = client.get("/api/runs").json()
    me = next(r for r in runs if r["path"] == fake_run)
    assert me["metrics"]["det_yield_per_keV"] == 8.2 and me["coating"] == "Ag"
    run = client.get("/api/run", params={"path": fake_run}).json()
    assert run["metrics_all"]["lce"] is None          # NaN is sent as null
    assert run["plots"][0]["path"].endswith("plots/edep_spectrum.png")
    assert run["config"]["optics"]["coating"] == "Ag"
    g = client.get("/api/run/geometry", params={"path": fake_run}).json()
    assert g["n_cells"] == 1 and g["config_optics"]["coating"] == "Ag"
    assert client.get(f"/files/{fake_run}/plots/edep_spectrum.png").status_code == 200


def test_file_access_is_restricted(client):
    assert client.get("/files/python/srdet/web/server.py").status_code == 403
    assert client.get("/files/runs/../../etc/passwd").status_code in (403, 404)
    assert client.get("/api/doc", params={"path": "app/srdet.cc"}).status_code == 403
    assert client.get("/api/doc", params={"path": "README.md"}).json()["markdown"].startswith("#")


def test_job_validation(client):
    assert client.post("/api/jobs", json={"kind": "study", "target": "../evil"}).status_code == 400
    assert client.post("/api/jobs", json={"kind": "rm -rf"}).status_code == 400


def test_job_result_parsing():
    log = "[srdet] run x: /work/runs/a\n[srdet] study U01 done: /work/runs/studies/20261024_U01\n"
    assert JobManager._result(log).endswith("runs/studies/20261024_U01")
    assert JobManager._result("[srdet] optimize done: /work/runs/optimize/O1/report.md").endswith("runs/optimize/O1")


def test_studies_and_optimizations_listing(client):
    st = client.get("/api/studies").json()
    assert any(s["name"] == "U01_coating" for s in st["specs"])
    op = client.get("/api/optimizations").json()
    assert any(s["name"].startswith("O01") for s in op["specs"])
