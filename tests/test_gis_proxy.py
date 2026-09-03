from __future__ import annotations

import io
import subprocess
import sys

import pytest
from fastapi import HTTPException

from server.backend import gis_proxy


class FakeHeaders(dict):
    def get_content_type(self):
        return self.get("Content-Type", "application/octet-stream").split(";", 1)[0]


class FakeUpstream:
    def __init__(self, url: str, body: bytes = b"{}", status: int = 200):
        self.status = status
        self._body = io.BytesIO(body)
        self.headers = FakeHeaders({"Content-Type": "application/json", "Content-Length": str(len(body))})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self._body.read(size)

    def close(self):
        self._body.close()


def test_allowlist_rejects_lookalike_host_and_path_escape():
    assert gis_proxy._target_allowed("pr-sige-represas", "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query")
    assert not gis_proxy._target_allowed("pr-sige-represas", "https://sige.pr.gov.evil.example/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query")
    assert not gis_proxy._target_allowed("pr-sige-represas", "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/17/query")
    assert not gis_proxy._target_allowed("unknown", "https://sige.pr.gov/")


def test_proxy_required_wfs_is_exact_source_bound():
    target = "http://geoserver2.pr.gov/geoserver/pr_geodata/ows?service=WFS&request=GetFeature"
    assert gis_proxy._target_allowed("pr-geodata-municipios-2015", target)
    assert gis_proxy._target_allowed("pr-geodata-barrios-2015", target)
    assert not gis_proxy._target_allowed("pr-sige-represas", target)
    assert not gis_proxy._target_allowed("pr-geodata-barrios-2015-simpl", target)


def test_range_is_bounded_to_one_mib():
    assert gis_proxy._validated_range("bytes=0-65535") == "bytes=0-65535"
    with pytest.raises(HTTPException):
        gis_proxy._validated_range("bytes=0-2000000")
    with pytest.raises(HTTPException):
        gis_proxy._validated_range("0-10")


def test_proxy_rejects_redirect_response(monkeypatch):
    requested = "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query?f=json"
    monkeypatch.setattr(gis_proxy, "_open_upstream", lambda *args, **kwargs: FakeUpstream(requested, status=302))
    with pytest.raises(HTTPException) as exc:
        gis_proxy.gis_proxy("pr-sige-represas", requested, None)
    assert exc.value.status_code == 502


def test_proxy_transport_connects_only_to_registered_host(monkeypatch):
    observed = {}

    class FakeConnection:
        def __init__(self, host, port=None, timeout=None):
            observed.update(host=host, port=port, timeout=timeout)

        def request(self, method, target, headers):
            observed.update(method=method, target=target, headers=headers)

        def getresponse(self):
            return FakeUpstream("unused")

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr(gis_proxy.http.client, "HTTPSConnection", FakeConnection)
    target = "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query?f=json"
    with gis_proxy._open_upstream("pr-sige-represas", target, {"Accept": "*/*"}, timeout=45):
        pass

    assert observed["host"] == "sige.pr.gov"
    assert observed["target"] == "/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query?f=json"
    assert observed["closed"] is True


def test_proxy_returns_allowed_upstream_bytes(monkeypatch):
    requested = "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query?f=json"
    monkeypatch.setattr(gis_proxy, "_open_upstream", lambda *args, **kwargs: FakeUpstream(requested, b'{"count":2}'))
    response = gis_proxy.gis_proxy("pr-sige-represas", requested, None)
    assert response.body == b'{"count":2}'
    assert response.headers["x-gis-source-id"] == "pr-sige-represas"


def test_spa_file_selection_never_constructs_a_path_from_request_text(tmp_path, monkeypatch):
    from server.backend import main_core

    index = tmp_path / "index.html"
    favicon = tmp_path / "favicon.ico"
    index.write_text("index", encoding="utf-8")
    favicon.write_bytes(b"icon")
    monkeypatch.setattr(main_core, "_SPA_INDEX", index)
    monkeypatch.setattr(main_core, "_SPA_ROOT_FILES", {"favicon.ico": favicon})

    assert main_core._spa_file("favicon.ico") == favicon
    assert main_core._spa_file("../../etc/passwd") == index
    assert main_core._spa_file("unknown.txt") == index


def test_main_entrypoint_preserves_core_namespace_and_fresh_runtime_mounts_proxy():
    from server.backend import main, main_core

    assert main is main_core
    assert hasattr(main, "_init_db")

    # Uvicorn resolves `server.backend.main:app` through importlib. Use that exact
    # importer rather than dotted-import package-attribute binding semantics.
    probe = (
        "import importlib; "
        "m=importlib.import_module('server.backend.main'); "
        "assert any(getattr(r, 'path', None) == '/api/gis/proxy' for r in m.app.routes)"
    )
    completed = subprocess.run([sys.executable, "-c", probe], check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
