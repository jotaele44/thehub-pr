"""API tests for the project-signs endpoints (build/preview/generate)."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import server.backend.main as backend_main  # noqa: E402

_TS = "2026-01-01T00:00:00Z"
_LINEAGE = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}
SRC = "src_0123456789abcdef0123456789abcdef"
RECIPIENT = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0001"
AGENCY = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0002"
AWD = "awd_" + "1" * 32


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    agg = tmp_path / "aggregate"
    agg.mkdir()
    _write_jsonl(agg / "entities.jsonl", [
        {"entity_id": RECIPIENT, "source_id": SRC, "name": "Urb. Encantada",
         "normalized_name": "URB. ENCANTADA", "entity_type": "project", "jurisdiction": "PR",
         "confidence": 0.9, "lineage": _LINEAGE, "synthetic": True,
         "created_at": _TS, "extracted_at": _TS},
        {"entity_id": AGENCY, "source_id": SRC, "name": "Senado de Puerto Rico",
         "normalized_name": "SENADO", "entity_type": "organization", "jurisdiction": "PR",
         "confidence": 0.9, "lineage": _LINEAGE, "synthetic": True,
         "created_at": _TS, "extracted_at": _TS},
    ])
    _write_jsonl(agg / "funding_awards.jsonl", [
        {"award_id": AWD, "source_id": SRC, "recipient_entity_id": RECIPIENT,
         "funding_agency_entity_id": AGENCY, "amount": 800000.0, "currency": "USD",
         "fiscal_year": 2026, "award_type": "Pavimentación", "award_date": "2026-01-01",
         "confidence": 0.9, "location": {"municipality": "Urb. Encantada",
         "municipality_name": "Trujillo Alto"}, "lineage": _LINEAGE, "synthetic": True,
         "created_at": _TS, "extracted_at": _TS},
    ])
    monkeypatch.setattr(backend_main, "AGGREGATE_PATH", agg)
    monkeypatch.setattr(backend_main, "SIGNS_OUT", tmp_path / "signs")
    with TestClient(backend_main.app) as c:
        yield c


def test_list_signs(client):
    r = client.get("/api/project-signs")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["signs"][0]["title"] == "Pavimentación"


def test_sign_html_preview(client):
    project_id = client.get("/api/project-signs").json()["signs"][0]["project_id"]
    r = client.get(f"/api/project-signs/{project_id}/html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Senado de Puerto Rico" in r.text
    assert "$800,000.00" in r.text


def test_sign_html_missing_returns_404(client):
    r = client.get("/api/project-signs/sgn_deadbeefdeadbeef/html")
    assert r.status_code == 404


def test_generate_without_write(client):
    r = client.post("/api/project-signs/generate", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["out_dir"] is None


def test_generate_with_write_persists_files(client, tmp_path):
    r = client.post("/api/project-signs/generate", json={"write": True})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["out_dir"] is not None
    assert (tmp_path / "signs" / "index.json").exists()
