#!/usr/bin/env python3
"""Compute the affected repository set for a federation-visible spatial change.

A repository may not merge, release or certify a federation-visible change until
the control plane has determined the complete affected repository set and every
affected repository has either advanced with the change or demonstrated
compatibility under the resulting contract generation. This script produces that
determination as an artifact rather than leaving it as an assertion.

A repository is affected when it consumes any contract in the generation. It
then carries one of two dispositions:

``ADVANCED``
    The repository changed in this generation.
``ATTESTED``
    The repository did not change but has demonstrated compatibility, recorded in
    its own ``governance/federation_compatibility.json`` receipt.

Any affected repository in neither state blocks the generation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATION_PATH = REPO_ROOT / "registry/spatial/contract_generation.json"

HUB = "thehub-pr"
GEOMETRY_AUTHORITY = "spiderweb-pr"
PRODUCERS = (
    "spiderweb-pr",
    "aguayluz-pr",
    "skywatcher-pr",
    "centinelas-pr",
    "moneysweep-pr",
    "ovnis-pr",
)

GENERATION = "federation-spatial-index/1"
CONTRACTS = {
    "federation_cell_index@1": (
        "Canonical 98,304-cell Cell_ID address space and its geographic geometry, "
        "published solely by the geometry authority."
    ),
    "cell_domain_summary@1": (
        "Tiny per-repository per-cell aggregate the Hub reads to compose a "
        "cross-domain view. Counts and identifiers only."
    ),
    "record_cell_binding@1": (
        "Binding of a domain record to one or more Cell_IDs, with a spatial role. "
        "Membership is computed once by the authority and stored by the producer."
    ),
    "cell_profile@1": (
        "GET /cells/{Cell_ID}/profile envelope. Same shape everywhere, "
        "domain-specific payload, geometry never included."
    ),
}


def compatibility_receipt(repo: str, workspace: Path) -> dict[str, Any] | None:
    path = workspace / repo / "governance/federation_compatibility.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def determine(workspace: Path) -> dict[str, Any]:
    repositories: list[dict[str, Any]] = []
    blocking: list[str] = []

    for repo in PRODUCERS:
        receipt = compatibility_receipt(repo, workspace)
        declared = set(receipt.get("contracts", [])) if receipt else set()
        covered = declared & set(CONTRACTS)

        if repo == GEOMETRY_AUTHORITY:
            disposition = "ADVANCED"
            role = "GEOMETRY_AUTHORITY"
        else:
            disposition = "ATTESTED" if covered == set(CONTRACTS) else "UNRESOLVED"
            role = "DOMAIN_BINDING_AUTHORITY"

        if disposition == "UNRESOLVED":
            blocking.append(repo)

        repositories.append(
            {
                "repository": repo,
                "role": role,
                "disposition": disposition,
                "receipt_present": receipt is not None,
                "contracts_declared": sorted(covered),
                "missing_contracts": sorted(set(CONTRACTS) - covered),
            }
        )

    return {
        "schema_version": "prii_federation_contract_generation_v1",
        "generation": GENERATION,
        "control_plane": HUB,
        "geometry_authority": GEOMETRY_AUTHORITY,
        "contracts": CONTRACTS,
        "affected_repositories": repositories,
        "affected_count": len(repositories),
        "blocking_repositories": blocking,
        "generation_state": "OPEN" if blocking else "CLOSED",
        "rule": (
            "No affected repository may merge, release or certify this "
            "federation-visible change while generation_state is OPEN."
        ),
        "notes": [
            "Only the geometry authority may publish canonical geometry; every other "
            "repository consumes Cell_IDs and never becomes a second geometry producer.",
            "A Cell_ID is a spatial address, not an identity claim. Co-location in a "
            "cell never establishes that two records are the same entity.",
            "The grid transform is PROVISIONAL in this generation, so consumers must "
            "not present a Cell_ID as a certified ground location.",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--workspace",
        type=Path,
        default=REPO_ROOT.parent,
        help="directory holding the federation repository checkouts",
    )
    parser.add_argument("--write", action="store_true", help="persist the generation record")
    parser.add_argument("--check", action="store_true", help="exit non-zero while blocked")
    args = parser.parse_args(argv)

    generation = determine(args.workspace)
    for entry in generation["affected_repositories"]:
        marker = {"ADVANCED": "++", "ATTESTED": " =", "UNRESOLVED": " !"}[entry["disposition"]]
        print(f"{marker} {entry['repository']:<16} {entry['disposition']}")
    print(f"\naffected={generation['affected_count']} state={generation['generation_state']}")
    if generation["blocking_repositories"]:
        print("blocking: " + ", ".join(generation["blocking_repositories"]))

    if args.write:
        GENERATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        GENERATION_PATH.write_text(
            json.dumps(generation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {GENERATION_PATH.relative_to(REPO_ROOT)}")

    if args.check and generation["generation_state"] != "CLOSED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
