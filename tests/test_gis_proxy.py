from __future__ import annotations

import io

import pytest
from fastapi import HTTPException

from server.backend import gis_proxy


class FakeHeaders(dict):
    def get_content_type(self):
        return self.get("Content-Type", "application/octet-stream").split(";", 1)[0]


class FakeUpstream:
    status = 200

    def __init__(self, url: str, body: bytes = b"{}"):
        self._url = url
        self._body = io.BytesIO(body)
        self.headers = FakeHeaders({"Content-Type": "application/json", "Content-Length": str(len(body))})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self._body.read(size)

    def geturl(self):
        return self._url


def test_allowlist_rejects_lookalike_host_and_path_escape():
    assert gis_proxy._target_allowed("pr-sige-represas", "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query")
    assert not gis_proxy._target_allowed("pr-sige-represas", "https://sige.pr.gov.evil.example/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query")
    assert not gis_proxy._target_allowed("pr-sige-represas", "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/17/query")
    assert not gis_proxy._target_allowed("unknown", "https://sige.pr.gov/")


def test_proxy_required_wfs_is_exact_source_bound():
    target = "http://geoserver2.pr.gov/geoserver/pr_geodata/wfs?service=WFS&request=GetFeature"
    assert gis_proxy._target_allowed("pr-geodata-barrios-2015-simpl", target)
    assert not gis_proxy._target_allowed("pr-sige-represas", target)


def test_range_is_bounded_to_one_mib():
    assert gis_proxy._validated_range("bytes=0-65535") == "bytes=0-65535"
    with pytest.raises(HTTPException):
        gis_proxy._validated_range("bytes=0-2000000")
    with pytest.raises(HTTPException):
        gis_proxy._validated_range("0-10")


def test_proxy_revalidates_redirect_target(monkeypatch):
    requested = "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query?f=json"
    monkeypatch.setattr(gis_proxy.urllib.request, "urlopen", lambda *args, **kwargs: FakeUpstream("https://evil.example/data"))
    with pytest.raises(HTTPException) as exc:
        gis_proxy.gis_proxy("pr-sige-represas", requested, None)
    assert exc.value.status_code == 502


def test_proxy_returns_allowed_upstream_bytes(monkeypatch):
    requested = "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query?f=json"
    monkeypatch.setattr(gis_proxy.urllib.request, "urlopen", lambda *args, **kwargs: FakeUpstream(requested, b'{"count":2}'))
    response = gis_proxy.gis_proxy("pr-sige-represas", requested, None)
    assert response.body == b'{"count":2}'
    assert response.headers["x-gis-source-id"] == "pr-sige-represas"
