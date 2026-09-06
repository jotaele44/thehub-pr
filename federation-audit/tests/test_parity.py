from __future__ import annotations

import json
from pathlib import Path

from federation_audit.parity import audit_repository, certify_federation

SHA = "a" * 40
AUTHORITY = {
    "semantic_authority": "fixture-domain",
    "mutation_authority": "fixture-domain-state-only",
    "identity_authority": "fixture-domain-identities",
    "geometry_authority": "fixture-geometry",
    "provenance_authority": "fixture-provenance",
}
MATRIX = {"repositories": {"fixture-pr": dict(AUTHORITY)}}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _contract(**overrides):
    value = {
        "schema_version": "federation.gui-backend-contract/1.0",
        "repository": "fixture/fixture-pr",
        "source_commit": SHA,
        "policy": {
            "require_zero_material_residue": True,
            "dimensions": ["executability", "semantic", "state", "auth", "data", "provenance", "device", "identity", "geometry", "authority"],
        },
        "discovery": {
            "backend_roots": ["server"],
            "frontend_roots": ["frontend"],
            "route_files": ["frontend/App.jsx"],
            "navigation_files": ["frontend/App.jsx"],
            "existing_gui_capability_manifests": [".federation/gui-capabilities.json"],
        },
        "authority": dict(AUTHORITY),
        "auth": {
            "mutating_route_policy": "require_guard_or_explicit_public",
            "guard_patterns": [r"Depends\(", r"require_admin"],
            "explicit_public_mutations": [],
        },
        "provenance": {
            "required_fields_when_available": ["source_ref"],
            "frontend_evidence_files": ["frontend/App.jsx"],
        },
        "devices": {
            "desktop": True,
            "mobile_web": True,
            "native_ios": False,
            "native_evidence_files": [],
            "intentional_restrictions": [],
        },
        "backend_only_allowlist": [],
        "gui_only_allowlist": [],
        "state_claims": [],
        "runtime_evidence": {
            "data": {"state": "PASS", "evidence": ["fixture:data"]},
            "identity": {"state": "PASS", "evidence": ["fixture:identity"]},
            "geometry": {"state": "PASS", "evidence": ["fixture:geometry"]},
            "device": {"state": "PASS", "evidence": ["fixture:device"]},
        },
        "certification": {"state": "OPEN", "material_residue": []},
    }
    for key, item in overrides.items():
        value[key] = item
    return value


def _repo():
    return {
        "id": "fixture-pr",
        "repository": "fixture/fixture-pr",
        "commit": SHA,
        "workspace_directory": "fixture-pr",
    }


def _fixture(root: Path, *, fetch_target: str = "/items", guarded: bool = True, risky: str = "") -> None:
    guard = ", _=Depends(require_admin)" if guarded else ""
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI, Depends\n"
        "app = FastAPI()\n"
        "def require_admin(): return True\n"
        "@app.get('/items')\n"
        "def items(): return []\n"
        "@app.post('/items')\n"
        f"def create_item(value: dict{guard}): return value\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        "export default function App(){\n"
        f"  const load = async () => {{ await fetch('{fetch_target}'); }};\n"
        f"  const source_ref = 'source_ref'; const status = '{risky}';\n"
        "  return <><Route path=\"/\" element={<div />} /><button onClick={load}>Load</button></>;\n"
        "}\n",
    )
    _write(
        root,
        ".federation/gui-capabilities.json",
        json.dumps({
            "capabilities": [{
                "id": "items",
                "status": "active",
                "backend": {"endpoints": ["GET /items", "POST /items"]},
                "frontend": {"routes": ["/"]},
            }]
        }),
    )
    _write(root, ".federation/gui_backend_contract.json", json.dumps(_contract()))


def _codes(report):
    return {item["code"] for item in report["findings"]}


def test_clean_fixture_can_close_all_static_and_runtime_dimensions(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _fixture(root)
    report = audit_repository(root, _repo(), _contract(), contract_source="repository", authority_matrix=MATRIX)
    assert report["state"] == "PASS", report["findings"]
    assert report["material_residue"] == 0


def test_gui_target_missing_is_p0(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _fixture(root, fetch_target="/missing")
    report = audit_repository(root, _repo(), _contract(), contract_source="repository", authority_matrix=MATRIX)
    assert "GUI_ONLY_UNJUSTIFIED" in _codes(report)
    assert report["state"] == "BLOCKED"


def test_unguarded_mutation_is_p0(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _fixture(root, guarded=False)
    contract = _contract()
    report = audit_repository(root, _repo(), contract, contract_source="repository", authority_matrix=MATRIX)
    assert "AUTH_DRIFT_UNGUARDED_MUTATION" in _codes(report)
    assert report["state"] == "BLOCKED"


def test_high_strength_state_language_requires_backend_predicate(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _fixture(root, risky="CURRENT")
    report = audit_repository(root, _repo(), _contract(), contract_source="repository", authority_matrix=MATRIX)
    assert "UNDECLARED_STATE_CLAIM" in _codes(report)


def test_authority_drift_fails_closed(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _fixture(root)
    contract = _contract()
    contract["authority"]["geometry_authority"] = "wrong-repo"
    report = audit_repository(root, _repo(), contract, contract_source="repository", authority_matrix=MATRIX)
    assert "AUTHORITY_DRIFT" in _codes(report)
    assert report["state"] == "BLOCKED"


def test_missing_gui_provenance_field_is_explicit(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _fixture(root)
    contract = _contract()
    contract["provenance"]["required_fields_when_available"] = ["source_ref", "source_hash"]
    report = audit_repository(root, _repo(), contract, contract_source="repository", authority_matrix=MATRIX)
    assert "PROVENANCE_GAP" in _codes(report)


def test_runtime_dimensions_cannot_pass_from_static_wiring(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _fixture(root)
    contract = _contract()
    contract["runtime_evidence"]["geometry"] = {"state": "OPEN", "evidence": []}
    report = audit_repository(root, _repo(), contract, contract_source="repository", authority_matrix=MATRIX)
    assert "RUNTIME_DIMENSION_OPEN" in _codes(report)
    assert report["state"] == "OPEN"


def test_control_plane_fallback_is_never_repository_certification(tmp_path: Path):
    workspace = tmp_path / "workspace"
    root = workspace / "fixture-pr"
    _fixture(root)
    (root / ".federation/gui_backend_contract.json").unlink()
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    (fallback / "fixture-pr.json").write_text(json.dumps(_contract()), encoding="utf-8")
    result = certify_federation(
        workspace,
        {"repositories": [_repo()]},
        authority_matrix=MATRIX,
        fallback_contract_root=fallback,
    )
    codes = {f["code"] for f in result["repositories"][0]["findings"]}
    assert "CONTRACT_NOT_LOCAL" in codes
    assert result["certified"] is False
