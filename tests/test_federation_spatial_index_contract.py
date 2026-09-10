"""Hub-side contracts for the federation spatial index generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hub import spatial
import scripts.federation_spatial_contract as contract

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATION = json.loads(
    (REPO_ROOT / "registry/spatial/contract_generation.json").read_text(encoding="utf-8")
)
TRANSFORM_SNAPSHOT = json.loads(
    (REPO_ROOT / "registry/spatial/pr_grid_transform_snapshot.json").read_text(encoding="utf-8")
)


# ------------------------------------------------------------- cell identity


@pytest.mark.parametrize("value", ["R0_C0", "R255_C383", "R123_C217"])
def test_canonical_cell_ids_validate(value: str) -> None:
    assert spatial.validate_cell_id(value) == []


@pytest.mark.parametrize("value", ["R000_C000", "R01_C2", "R256_C0", "R0_C384", "r0_c0", 17, None])
def test_non_canonical_cell_ids_are_rejected(value: object) -> None:
    assert spatial.validate_cell_id(value)


# ------------------------------------------------------- cell domain summary


def test_valid_domain_summary_passes() -> None:
    assert spatial.validate_cell_domain_summary(
        {
            "Cell_ID": "R73_C203",
            "Repository": "moneysweep-pr",
            "Domain": "financial_activity",
            "Record_Count": 81,
            "Has_Data": True,
            "Top_Record_IDs": ["contract-1", "contract-2"],
        }
    ) == []


def test_summary_rejects_raw_records_in_place_of_identifiers() -> None:
    """Top_Record_IDs carries identifiers; resolving them is the producer's job."""
    errors = spatial.validate_cell_domain_summary(
        {
            "Cell_ID": "R73_C203",
            "Repository": "moneysweep-pr",
            "Record_Count": 1,
            "Has_Data": True,
            "Top_Record_IDs": [{"id": "contract-1", "amount": 428_300_000}],
        }
    )
    assert any("identifiers only" in error for error in errors)


def test_summary_rejects_an_unbounded_top_n() -> None:
    errors = spatial.validate_cell_domain_summary(
        {
            "Cell_ID": "R73_C203",
            "Repository": "skywatcher-pr",
            "Record_Count": 1284,
            "Has_Data": True,
            "Top_Record_IDs": [f"flight-{index}" for index in range(200)],
        }
    )
    assert any("ceiling" in error for error in errors)


def test_summary_rejects_co_location_treated_as_identity() -> None:
    errors = spatial.validate_cell_domain_summary(
        {
            "Cell_ID": "R73_C203",
            "Repository": "ovnis-pr",
            "Record_Count": 17,
            "Has_Data": True,
            "Identity_Default": "RESOLVED_IDENTITY",
        }
    )
    assert any("never identity" in error for error in errors)


def test_summary_rejects_an_unknown_producer() -> None:
    assert spatial.validate_cell_domain_summary(
        {"Cell_ID": "R1_C1", "Repository": "some-other-repo", "Record_Count": 0, "Has_Data": False}
    )


# --------------------------------------------------------------- cell profile


def test_profile_envelope_is_uniform_across_repositories() -> None:
    for repo, kind in (
        ("aguayluz-pr", "water_hydrology"),
        ("skywatcher-pr", "flight_activity"),
        ("moneysweep-pr", "financial_activity"),
        ("ovnis-pr", "anomalous_cases"),
        ("centinelas-pr", "monitoring_state"),
    ):
        assert spatial.validate_cell_profile(
            {"cell_id": "R73_C203", "repository": repo, "profile_type": kind, "summary": {}}
        ) == []


@pytest.mark.parametrize("field", ["geometry", "coordinates", "bbox", "polygon"])
def test_profile_may_not_carry_geometry(field: str) -> None:
    """A producer shipping geometry would become a second geometry authority."""
    errors = spatial.validate_cell_profile(
        {
            "cell_id": "R73_C203",
            "repository": "aguayluz-pr",
            "profile_type": "water_hydrology",
            "summary": {},
            field: {"type": "Polygon"},
        }
    )
    assert any(spatial.GEOMETRY_AUTHORITY in error for error in errors)


# ------------------------------------------------------- contract generation


def test_generation_accounts_for_every_producer() -> None:
    assert GENERATION["affected_count"] == len(contract.PRODUCERS)
    assert {entry["repository"] for entry in GENERATION["affected_repositories"]} == set(
        contract.PRODUCERS
    )


def test_generation_is_closed_with_every_repo_advanced_or_attested() -> None:
    dispositions = {
        entry["repository"]: entry["disposition"] for entry in GENERATION["affected_repositories"]
    }
    assert dispositions["spiderweb-pr"] == "ADVANCED"
    assert all(value in {"ADVANCED", "ATTESTED"} for value in dispositions.values())
    assert GENERATION["blocking_repositories"] == []
    assert GENERATION["generation_state"] == "CLOSED"


def test_a_missing_attestation_reopens_the_generation(tmp_path) -> None:
    """The gate must actually block, not merely record."""
    for repo in contract.PRODUCERS:
        governance = tmp_path / repo / "governance"
        governance.mkdir(parents=True)
        contracts = [] if repo == "aguayluz-pr" else sorted(contract.CONTRACTS)
        (governance / "federation_compatibility.json").write_text(
            json.dumps({"repo": repo, "contracts": contracts}), encoding="utf-8"
        )
    generation = contract.determine(tmp_path)
    assert generation["generation_state"] == "OPEN"
    assert "aguayluz-pr" in generation["blocking_repositories"]


def test_geometry_authority_is_singular() -> None:
    assert GENERATION["geometry_authority"] == "spiderweb-pr"
    assert spatial.GEOMETRY_AUTHORITY == "spiderweb-pr"


def test_snapshot_reports_provisional_certification_honestly() -> None:
    assert TRANSFORM_SNAPSHOT["certification_state"] == "PROVISIONAL"
    assert TRANSFORM_SNAPSHOT["documented_bounds"]["status"] == "DOCUMENTED_UNVERIFIED"
    assert TRANSFORM_SNAPSHOT["parameter_provenance"] == "FITTED"


def test_hub_mirrors_manifests_but_not_geometry_bytes() -> None:
    manifest = json.loads(
        (REPO_ROOT / "registry/spatial/pr_grid_geometry_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["cell_count"] == 98_304
    assert manifest["mirrored_from"] == "spiderweb-pr"
    assert "not mirrored" in manifest["path"]
