import pytest

from hub.mcp_runtime import MCPRequest, PolicyViolation, Router, RuntimeRegistry
from hub.mcp_runtime.adapters import (
    DocumentsAdapter,
    GeospatialAdapter,
    GithubBridgeAdapter,
    ProvenanceAdapter,
)


@pytest.fixture()
def registry():
    return RuntimeRegistry()


@pytest.fixture()
def router(registry):
    return Router(registry)


# --- provenance -----------------------------------------------------------

def test_provenance_list_sources(router, package_factory, tmp_path):
    package = package_factory(tmp_path / "pkg", producer="moneysweep-pr")
    router.register_adapter(ProvenanceAdapter())
    result = router.route(
        MCPRequest(
            project="moneysweep",
            capability="provenance",
            action="list_sources",
            params={"package": str(package)},
        )
    )
    assert result.data["count"] == 1
    assert result.data["sources"][0]["source_type"] == "federal_grants"
    assert result.provenance["package"] == str(package)
    assert result.provenance["version_pin"] == "1.0.0"


def test_provenance_get_source_found_and_missing(router, package_factory, tmp_path):
    package = package_factory(tmp_path / "pkg", producer="moneysweep-pr")
    router.register_adapter(ProvenanceAdapter())
    src_id = "src_0123456789abcdef0123456789abcdef"
    ok = router.route(
        MCPRequest(
            project="moneysweep", capability="provenance", action="get_source",
            params={"package": str(package), "source_id": src_id},
        )
    )
    assert ok.data["source"]["source_id"] == src_id
    with pytest.raises(LookupError, match="not found"):
        router.route(
            MCPRequest(
                project="moneysweep", capability="provenance", action="get_source",
                params={"package": str(package), "source_id": "src_missing"},
            )
        )


def test_provenance_stamp_is_deterministic(router):
    router.register_adapter(ProvenanceAdapter())

    def stamp():
        return router.route(
            MCPRequest(
                project="ovnis", capability="provenance", action="stamp",
                params={"prefix": "prov", "parts": ["a", "b", 1]},
            )
        ).data["provenance_id"]

    first = stamp()
    assert first == stamp()
    assert first.startswith("prov_")


# --- geospatial -----------------------------------------------------------

SAN_JUAN = [18.4655, -66.1057]
PONCE = [18.0111, -66.6141]


def test_geospatial_distance(router):
    router.register_adapter(GeospatialAdapter())
    result = router.route(
        MCPRequest(
            project="spiderweb", capability="geospatial", action="distance",
            params={"a": SAN_JUAN, "b": PONCE},
        )
    )
    # San Juan <-> Ponce is ~74 km; assert a generous PR-scale band.
    assert 60.0 < result.data["distance_km"] < 90.0
    assert result.provenance["method"] == "haversine/WGS84-sphere"


def test_geospatial_nearest(router):
    router.register_adapter(GeospatialAdapter())
    near_sj = [18.47, -66.11]
    result = router.route(
        MCPRequest(
            project="spiderweb", capability="geospatial", action="nearest",
            params={"point": SAN_JUAN, "candidates": [PONCE, near_sj]},
        )
    )
    assert result.data["index"] == 1
    assert result.data["candidate"] == near_sj


def test_geospatial_normalize_municipality(router):
    router.register_adapter(GeospatialAdapter())
    result = router.route(
        MCPRequest(
            project="spiderweb", capability="geospatial",
            action="normalize_municipality", params={"municipality": "  san juan "},
        )
    )
    assert result.data["municipality"] == "SAN JUAN"


def test_geospatial_rejects_bad_coordinate(router):
    router.register_adapter(GeospatialAdapter())
    with pytest.raises(ValueError, match="valid lat/lon"):
        router.route(
            MCPRequest(
                project="spiderweb", capability="geospatial", action="distance",
                params={"a": [200, 0], "b": PONCE},
            )
        )


# --- documents ------------------------------------------------------------

def test_documents_search_and_get(router, tmp_path):
    (tmp_path / "case_001.md").write_text("Report on the Arecibo sighting.\nSecond line.\n")
    (tmp_path / "notes.txt").write_text("nothing relevant here\n")
    router.register_adapter(DocumentsAdapter())

    hits = router.route(
        MCPRequest(
            project="ovnis", capability="documents", action="search",
            params={"root": str(tmp_path), "query": "arecibo"},
        )
    )
    assert hits.data["hits"] == [
        {"path": "case_001.md", "line_no": 1, "line": "Report on the Arecibo sighting."}
    ]
    assert hits.data["truncated"] is False

    got = router.route(
        MCPRequest(
            project="ovnis", capability="documents", action="get",
            params={"root": str(tmp_path), "path": "case_001.md"},
        )
    )
    assert "Arecibo" in got.data["text"]


def test_documents_get_rejects_traversal(router, tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    (root / "a.md").write_text("hi\n")
    (tmp_path / "secret.md").write_text("secret\n")
    router.register_adapter(DocumentsAdapter())
    with pytest.raises(ValueError, match="escapes document root"):
        router.route(
            MCPRequest(
                project="ovnis", capability="documents", action="get",
                params={"root": str(root), "path": "../secret.md"},
            )
        )


def test_documents_search_respects_max_hits(router, tmp_path):
    (tmp_path / "many.md").write_text("match\n" * 10)
    router.register_adapter(DocumentsAdapter())
    result = router.route(
        MCPRequest(
            project="ovnis", capability="documents", action="search",
            params={"root": str(tmp_path), "query": "match", "max_hits": 3},
        )
    )
    assert len(result.data["hits"]) == 3
    assert result.data["truncated"] is True


# --- github-bridge --------------------------------------------------------

def test_github_bridge_list_producers(router):
    router.register_adapter(GithubBridgeAdapter())
    result = router.route(
        MCPRequest(
            project="skywatcher", capability="github-bridge",
            action="list_producers",
        )
    )
    assert result.data["count"] == 6
    ids = {p["program_id"] for p in result.data["producers"]}
    assert "moneysweep-pr" in ids and "ovnis-pr" in ids


def test_github_bridge_resolve_repo(router):
    router.register_adapter(GithubBridgeAdapter())
    result = router.route(
        MCPRequest(
            project="skywatcher", capability="github-bridge",
            action="resolve_repo", params={"program_id": "spiderweb-pr"},
        )
    )
    assert result.data["repo"] == "jotaele44/spiderweb-pr"
    assert result.data["repo_name"] == "spiderweb-pr"
    assert result.data["clone_url"] == "https://github.com/jotaele44/spiderweb-pr.git"


def test_github_bridge_unknown_program_id(router):
    router.register_adapter(GithubBridgeAdapter())
    with pytest.raises(LookupError, match="no producer"):
        router.route(
            MCPRequest(
                project="skywatcher", capability="github-bridge",
                action="resolve_repo", params={"program_id": "nope-pr"},
            )
        )


# --- governance unchanged -------------------------------------------------

def test_core_capability_still_gated_by_manifest(router):
    # centinelas does not declare 'geospatial' -> policy blocks it even though
    # an adapter is registered.
    router.register_adapter(GeospatialAdapter())
    with pytest.raises(PolicyViolation, match="does not declare"):
        router.route(
            MCPRequest(
                project="centinelas", capability="geospatial", action="distance",
                params={"a": SAN_JUAN, "b": PONCE},
            )
        )
