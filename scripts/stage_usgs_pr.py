import argparse
import gzip
import json
import hashlib
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hub.usgs_assets import root_membership, adapt_native_geojson

parser = argparse.ArgumentParser(
    description="Build blocked reference intake packages from the frozen source artifact"
)
parser.add_argument("--archive", type=Path, required=True)
args = parser.parse_args()
archive_raw = args.archive.read_bytes()
if (
    hashlib.sha256(archive_raw).hexdigest()
    != "b8fed761b822c9287a6423e9ca9ad4df5d49453e57dffb727d40568873459b72"
):
    raise ValueError("Frozen evidence archive SHA-256 mismatch")
root = Path(__file__).resolve().parents[1]
inventory_raw = gzip.decompress(
    (root / "data/usgs/continuation_inventory.v1.json.gz").read_bytes()
)
with zipfile.ZipFile(args.archive) as source:
    if source.read("inventory.json") != inventory_raw:
        raise ValueError("Staging inventory differs from frozen source artifact")
inv = json.loads(inventory_raw)
cat = json.loads((root / "registry/usgs/pr_releases.v1.json").read_text())
membership = root_membership(
    [r["sciencebase_id"] for r in cat["releases"]], inv["child_edges"]
)
out = root / "data/usgs/staging"
out.mkdir(exist_ok=True)
review = []
for repo in cat["repositories"]:
    pid = repo["program_id"]
    wrapper = json.loads(
        (root / ("registry/usgs/producer_contracts/" + pid + ".json")).read_text()
    )
    manifest = wrapper["raw_manifest"]
    if (
        manifest["repository_full_name"].lower() != repo["repo"].lower()
        or manifest["federation_role"] != repo["role"]
    ):
        raise ValueError("Producer repository identity/role mismatch")
    candidates = [
        r
        for r in cat["releases"]
        if any(c["program_id"] == pid for c in r["consumer_candidates"])
    ]
    ids = {r["sciencebase_id"] for r in candidates}
    assets = [
        a
        for a in inv["assets"]
        if ids.intersection(membership.get(a["source_item_id"], []))
    ]
    d = {
        "contract": "prii.usgs-producer-intake-staging/v1",
        "program_id": pid,
        "repository": repo["repo"],
        "role": repo["role"],
        "repository_binding_state": "PASS",
        "consumer_fitness_state": "OPEN",
        "producer_contract_blob": wrapper["git_blob_sha"],
        "source_archive_sha256": "b8fed761b822c9287a6423e9ca9ad4df5d49453e57dffb727d40568873459b72",
        "release_ids": sorted(ids),
        "candidate_assets": [
            {
                "asset_id": a["asset_id"],
                "root_release_ids": membership[a["source_item_id"]],
                "payload_state": a["payload_state"],
            }
            for a in assets
        ],
        "payload_states": {
            s: sum(a["payload_state"] == s for a in assets)
            for s in ("PASS", "FAIL", "BLOCKED")
        },
        "upstream_readiness_raw": manifest.get("federation_readiness_gate"),
        "export_command_reference": manifest.get("hub_callable_commands", {}).get(
            "export_canonical"
        ),
        "stage": "REFERENCE_INTAKE_ONLY",
        "canonical_streams_emitted": False,
        "production_export_state": "BLOCKED",
        "activation_state": "BLOCKED",
        "open_gates": [
            "consumer_fitness",
            "schema_and_units",
            "PR_coverage",
            "geometry_CRS_Z_M",
            "version_lineage",
            "usage_constraints",
            "producer_adapter_and_contract_validation",
        ],
    }
    (out / (pid + ".intake.json")).write_text(json.dumps(d, indent=2) + "\n")
    review.append(
        {
            k: d[k]
            for k in (
                "program_id",
                "repository",
                "role",
                "repository_binding_state",
                "consumer_fitness_state",
                "payload_states",
                "production_export_state",
                "activation_state",
            )
        }
    )
(root / "registry/usgs/binding_review.v1.json").write_text(
    json.dumps(
        {
            "state": "PASS",
            "scope": "Repository identities and declared roles only; proposed dataset fitness remains OPEN",
            "bindings": review,
        },
        indent=2,
    )
    + "\n"
)
z = zipfile.ZipFile(args.archive)
keymap = {
    "6516c8f9d34e5f8ef156488e:1": "SiteID",
    "6516caf3d34e5f8ef1564898:1": "PolyID",
    "6516cbb8d34e5f8ef156489f:1": "FaultID",
}
for a in inv["assets"]:
    if a["asset_id"] not in keymap:
        continue
    raw = z.read("payloads/" + a["asset_id"].replace(":", "_") + ".bin")
    (out / (a["asset_id"].replace(":", "_") + ".geojson.gz")).write_bytes(
        gzip.compress(raw, mtime=0)
    )
    d = adapt_native_geojson(raw, a["raw_descriptor"], keymap[a["asset_id"]])
    d.update(
        asset_id=a["asset_id"],
        root_release_ids=membership[a["source_item_id"]],
        source_descriptor_raw=a["raw_descriptor"],
    )
    (out / (a["asset_id"].replace(":", "_") + ".native.json")).write_text(
        json.dumps(d, indent=2) + "\n"
    )
(out / "TERMINAL_READY.txt").write_text(
    "USGS reference intake staging. Production exports BLOCKED; activated=0.\nRun from repository root: PYTHONPATH=src python -m pytest tests/test_usgs_assets.py tests/test_usgs_continuation.py tests/test_usgs_catalog.py\nVerify: python scripts/verify_usgs_build.py\nNative GeoJSON retains source geometry and CRS without correction. Source keys are scoped to each asset.\nDo not load these reference envelopes as canonical producer streams. Consumer fitness, PR coverage, geometry, lineage and usage remain OPEN.\n"
)
