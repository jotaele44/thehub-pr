from pathlib import Path

from federation_audit.resolver import build_resolution_index
from federation_audit.strict_scan import strict_scan_federation, strict_scan_repository


def _write(root: Path, relative_path: str, content: str) -> None:
    file_path = root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _repo() -> dict:
    return {
        "id": "fixture-pr",
        "repository": "fixture/fixture-pr",
        "commit": "a" * 40,
        "workspace_directory": "fixture-pr",
        "entry_points": [],
    }


def _fixture(root: Path, *, method: str = "GET") -> None:
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/items')\n"
        "def items(): return []\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        "export default function App() {\n"
        f"  const load = async () => {{ await fetch('/items', {{ method: '{method}' }}); }};\n"
        "  return <button onClick={load}>Load</button>;\n"
        "}\n",
    )


def test_strict_scan_promotes_exact_gui_to_api_binding(tmp_path: Path) -> None:
    root = tmp_path / "fixture-pr"
    _fixture(root)

    traces, index = strict_scan_repository(root, _repo())

    gui_trace = next(trace for trace in traces if trace.surface.get("kind") == "gui-control")
    assert gui_trace.classification == "EXECUTABLE_BY_CONTRACT"
    assert gui_trace.observations["resolved_target"] == "GET /items"
    assert gui_trace.observations["resolver_receipt_digest"]
    assert any(evidence.kind == "resolver-receipt" for evidence in gui_trace.evidence)
    assert len(index.routes) == 1


def test_strict_scan_keeps_method_mismatch_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "fixture-pr"
    _fixture(root, method="POST")

    traces, index = strict_scan_repository(root, _repo())

    gui_trace = next(trace for trace in traces if trace.surface.get("kind") == "gui-control")
    assert gui_trace.classification == "CONTRACT_MISMATCH"
    assert gui_trace.observations["contract_mismatch"] is True
    assert "resolver_receipt_digest" not in gui_trace.observations
    assert all(evidence.kind != "resolver-receipt" for evidence in gui_trace.evidence)
    assert len(index.routes) == 1


def test_strict_scan_federation_preserves_missing_repository_arithmetic(tmp_path: Path) -> None:
    manifest = {"repositories": [_repo()]}

    report = strict_scan_federation(tmp_path, manifest)

    assert report["coverage"]["repositories_present"] == 0
    assert report["coverage"]["repositories_missing"] == 1
    assert report["workspace_gaps"] == ["fixture-pr"]
    assert report["traces"] == []


def test_resolution_index_scopes_mount_prefixes_to_imported_router_modules(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "server/first.py",
        "from fastapi import APIRouter\nrouter = APIRouter(prefix='/first')\n"
        "@router.get('/items')\ndef items(): return []\n",
    )
    _write(
        tmp_path,
        "server/second.py",
        "from fastapi import APIRouter\nrouter = APIRouter(prefix='/second')\n"
        "@router.get('/items')\ndef items(): return []\n",
    )
    _write(
        tmp_path,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "from server.first import router as first_router\n"
        "from server.second import router as second_router\n"
        "app = FastAPI()\n"
        "app.include_router(first_router, prefix='/v1')\n"
        "app.include_router(second_router, prefix='/v2')\n",
    )

    index = build_resolution_index(tmp_path)

    assert {(route.method, route.path, route.source) for route in index.routes} == {
        ("GET", "/v1/first/items", "server/first.py"),
        ("GET", "/v2/second/items", "server/second.py"),
    }


def test_resolution_index_deduplicates_mounts_and_excludes_test_routes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "server/app.py",
        "from fastapi import APIRouter, FastAPI\n"
        "app = FastAPI()\nrouter = APIRouter(prefix='/api')\n"
        "@router.get('/items')\ndef items(): return []\n"
        "app.include_router(router)\napp.include_router(router)\n",
    )
    _write(
        tmp_path,
        "tests/test_app.py",
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/fixture-only')\ndef fixture_only(): return []\n",
    )

    index = build_resolution_index(tmp_path)

    assert [(route.method, route.path, route.source) for route in index.routes] == [
        ("GET", "/api/items", "server/app.py")
    ]
