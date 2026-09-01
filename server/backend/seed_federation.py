"""Seed the three federation control-plane collections from committed readiness.

`Gates`, `Integrations` and `Manifest` are real pages over real vocabularies, and
until now all three rendered empty because nothing in `ingest.py` projects them
(see the note at src/hub/ingest.py:178-181). The data they want does exist — it
is what `hub validate-federation` measures — but that validator only works in a
workspace holding all six producer checkouts, which a deployed hub does not have.

So the measurement is taken at build time and committed to
``data/federation_status.json`` (see scripts/build_federation_status.py), and this
module projects that snapshot into the three collections at server startup.

Two deliberate choices worth knowing before changing this:

*Seed-once, not sync.* All three collections are operator-editable through
``EntityLedger`` — the pages have create and update forms. Re-projecting on every
boot would silently overwrite an operator's review notes with the snapshot's.
So this uses the same ``INSERT OR IGNORE``-after-existence-check semantics as
``_seed_programs``: it fills empty collections and then leaves them alone. To pick
up a regenerated snapshot, delete the seeded rows first.

*Only gates with distinct evidence.* ``GATE_NAMES`` has ten entries; the snapshot
carries independent truth for three of them. Seeding the other seven as
"NotStarted" would fill the page with 42 rows asserting something the repo cannot
back — it would read as measurement rather than absence. They stay unseeded.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

log = logging.getLogger("hub.backend")

#: The contract every producer's federation.json is pinned to — a `const` in
#: schemas/repo_federation_manifest.schema.json. Used when a snapshot predates
#: manifest_schema_version, and in registry-only mode where no manifest was read.
_REPO_MANIFEST_SCHEMA = "repo_federation_manifest_v1"

# ── Vocabularies (must match the UI selects, which are closed) ─────────────────
# server/frontend/src/pages/Integrations.jsx:14
_INTEGRATION_STATUS = {
    "ready": "Connected",
    "declared_not_live": "Blocked",
    "missing_checkout": "NotConnected",
    "missing_manifest": "NotConnected",
    "missing_export_package": "NotConnected",
    "invalid_manifest": "Error",
    "invalid_export_package": "Error",
}

_NEXT_ACTION = {
    "ready": "None — producer is live-ready.",
    "declared_not_live": (
        "Clear the producer's blocking_conditions, then set "
        "federation_readiness_gate.ready_for_hub_live_execution in federation.json."
    ),
    "missing_checkout": "Clone the producer repository into the hub workspace.",
    "missing_manifest": "Add federation.json to the producer repository root.",
    "invalid_manifest": (
        "Fix federation.json against schemas/repo_federation_manifest.schema.json."
    ),
    "missing_export_package": (
        "Run the producer's export_canonical command and commit the resulting "
        "canonical package."
    ),
    "invalid_export_package": (
        "Fix the export package's schema errors, then re-run validation."
    ),
}

_BLOCKING_REASON = {
    "ready": "",
    "declared_not_live": "Producer has not declared live-execution readiness.",
    "missing_checkout": "No producer checkout found in the workspace.",
    "missing_manifest": "federation.json is absent from the producer repository.",
    "invalid_manifest": "federation.json fails the repo manifest schema.",
    "missing_export_package": "No canonical export package has been committed.",
    "invalid_export_package": "The canonical export package fails validation.",
}

# The three gates the snapshot carries independent evidence for. Each maps to a
# distinct boolean — deliberately not four, because SchemaValidation would be the
# same `manifest_valid` signal that ManifestValidation already reports.
_GATE_REQUIREMENTS = {
    "ManifestValidation": (
        "federation.json must be present and validate against "
        "schemas/repo_federation_manifest.schema.json."
    ),
    "ExportPackageValidation": (
        "The producer's canonical export package must be present and pass "
        "hub.validate.validate_package."
    ),
    "LiveExecutionReadiness": (
        "federation.json must declare "
        "federation_readiness_gate.ready_for_hub_live_execution."
    ),
}


def _check_status(*, checkout_present: bool, present: bool, valid: bool) -> str:
    """Map a present/valid pair onto the Gates.jsx status vocabulary."""
    if not checkout_present:
        return "NotStarted"          # never measured — no checkout to measure
    if not present:
        return "Blocked"             # precondition absent, the check cannot run
    return "Passed" if valid else "Failed"


def _exists(conn: sqlite3.Connection, entity_type: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM entities WHERE entity_type=? LIMIT 1", (entity_type,)
    ).fetchone()
    return row is not None


def _insert(
    conn: sqlite3.Connection, entity_type: str, rows: Iterable[dict[str, Any]], ts: str
) -> int:
    count = 0
    for row in rows:
        conn.execute(
            "INSERT OR IGNORE INTO entities (entity_type, entity_id, data, updated_at) "
            "VALUES (?,?,?,?)",
            (entity_type, row["id"], json.dumps(row), ts),
        )
        count += 1
    return count


def _load_snapshot(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("federation status snapshot at %s is unreadable: %s", path, exc)
        return None


def _from_registry(registry_path: Path) -> Optional[dict[str, Any]]:
    """Fallback shape when no snapshot is committed.

    A checkout without the snapshot should still render honest topology rather
    than an empty page, so the registry alone drives FederationManifest and
    IntegrationStatus. It carries no evidence about manifests or export packages,
    so ValidationGates stays empty in this mode — that absence is the honest
    answer, not a gap to paper over.
    """
    if not registry_path.exists():
        return None
    try:
        registry = yaml.safe_load(registry_path.read_text()) or {}
    except (OSError, yaml.YAMLError) as exc:
        log.warning("registry at %s is unreadable: %s", registry_path, exc)
        return None

    producers = []
    for producer in registry.get("producers", []):
        declared = producer.get("status", "")
        producers.append({
            "program_id": producer["program_id"],
            "declared_status": declared,
            "checkout_present": False,
            "manifest_present": False, "manifest_valid": False,
            "package_present": False, "package_valid": False,
            "live_execution_ready": declared == "ready_for_live",
            "blocker_class": (
                "ready" if declared == "ready_for_live" else "declared_not_live"
            ),
            "errors": [],
            "last_package_timestamp": None,
        })
    return {
        "hub": registry.get("hub", "thehub-pr"),
        "schema_version": registry.get("schema_version", "hub_registry_v1"),
        "producers": producers,
        "generated_at": None,
        "_registry_only": True,
    }


def _manifest_rows(snapshot: dict[str, Any], ts: str) -> list[dict[str, Any]]:
    # Two different contracts are in play. The hub is described by the registry
    # (`hub_registry_v1`); each producer is described by its own federation.json,
    # which schemas/repo_federation_manifest.schema.json pins to
    # `repo_federation_manifest_v1`. Reporting the registry's version on a child
    # row would contradict the same row's note that federation.json validated.
    hub_schema_version = snapshot.get("schema_version", "hub_registry_v1")
    rows = []

    hub_id = snapshot.get("hub", "thehub-pr")
    # The hub itself is the ParentControlPlane — the only thing that role in the
    # Manifest.jsx enum can describe. Note it has no Programs row (the registry
    # lists producers only), so this row renders in the table but the edit form's
    # program select will not have a matching option.
    rows.append({
        "id": f"mf-{hub_id}", "manifest_id": f"mf-{hub_id}",
        "program_id": hub_id,
        "module_role": "ParentControlPlane",
        "schema_version": hub_schema_version,
        "status": "Stable",
        "notes": "Federation control plane. Registry owner and aggregation host.",
        "created_date": ts, "updated_date": ts,
    })

    for producer in snapshot["producers"]:
        pid = producer["program_id"]
        if producer.get("manifest_valid"):
            status, note = "Stable", "federation.json validates against the repo manifest schema."
        elif producer.get("manifest_present"):
            status, note = "Reviewing", "federation.json is present but fails schema validation."
        else:
            status, note = "Draft", "No validated federation.json captured in the snapshot."
        rows.append({
            "id": f"mf-{pid}", "manifest_id": f"mf-{pid}",
            "program_id": pid,
            "module_role": "ChildModule",
            # What the producer actually declares, when the snapshot captured it;
            # otherwise the contract that governs the file either way.
            "schema_version": (
                producer.get("manifest_schema_version") or _REPO_MANIFEST_SCHEMA
            ),
            "status": status,
            "notes": note,
            "created_date": ts, "updated_date": ts,
        })
    return rows


def _integration_rows(
    snapshot: dict[str, Any],
    ts: str,
    checked: str,
    sync_gate: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    # Without a snapshot, "ready" means the producer *declares* readiness in the
    # registry — nothing has verified an export package. That is "Ready", not
    # "Connected"; claiming the latter on registry data alone would assert a
    # working integration the hub has never observed.
    registry_only = bool(snapshot.get("_registry_only"))

    rows = []
    for producer in snapshot["producers"]:
        pid = producer["program_id"]
        blocker = producer.get("blocker_class", "missing_checkout")
        errors = producer.get("errors") or []
        status = _INTEGRATION_STATUS.get(blocker, "NotConnected")
        if registry_only and status == "Connected":
            status = "Ready"
        rows.append({
            "id": f"int-{pid}-federation",
            "integration_id": f"int-{pid}-federation",
            "program_id": pid,
            "integration_name": "Federation",
            "status": status,
            "last_checked": checked,
            "blocking_reason": errors[0] if errors else _BLOCKING_REASON.get(blocker, ""),
            "next_action": _NEXT_ACTION.get(blocker, ""),
            "created_date": ts, "updated_date": ts,
        })

    # The hub-level rollup of the GitHubSyncApproval gate below, projected onto
    # the Integrations vocabulary. Absent whenever that gate itself is absent
    # (registry-only mode) — no live GitHub check is ever made here, this is
    # purely the same evidence read a second way.
    if sync_gate is not None:
        gate_status = sync_gate["status"]
        status = (
            "Connected" if gate_status == "Passed"
            else "Error" if gate_status == "Failed"
            else "Blocked"
        )
        rows.append({
            "id": "int-prog-control-github",
            "integration_id": "int-prog-control-github",
            "program_id": "prog-control",
            "integration_name": "GitHub",
            "status": status,
            "last_checked": checked,
            "blocking_reason": "" if status == "Connected" else sync_gate["review_notes"],
            "next_action": (
                "" if status == "Connected"
                else "Resolve the outstanding ValidationGates listed above, then "
                     "re-run `make federation-status`."
            ),
            "created_date": ts, "updated_date": ts,
        })
    return rows


# Worst-first severity for rolling many gate statuses into one. Absence of
# evidence (NotStarted) is deliberately not as bad as a measured failure.
_GATE_SEVERITY = {"Passed": 0, "NotStarted": 1, "Blocked": 2, "Failed": 3}


def _gate_rows(snapshot: dict[str, Any], ts: str, reviewed: str) -> list[dict[str, Any]]:
    """One row per (producer, evidenced gate), plus one hub-level rollup gate.

    Empty in registry-only mode — including the rollup, since there is no
    evidence to roll up.
    """
    if snapshot.get("_registry_only"):
        return []

    rows = []
    worst_status = "Passed"
    blocking_producers: list[str] = []
    for producer in snapshot["producers"]:
        pid = producer["program_id"]
        checkout = bool(producer.get("checkout_present"))
        errors = producer.get("errors") or []
        note = "; ".join(errors[:3]) if errors else ""

        measured = {
            "ManifestValidation": _check_status(
                checkout_present=checkout,
                present=bool(producer.get("manifest_present")),
                valid=bool(producer.get("manifest_valid")),
            ),
            "ExportPackageValidation": _check_status(
                checkout_present=checkout,
                present=bool(producer.get("package_present")),
                valid=bool(producer.get("package_valid")),
            ),
            # Not a pass/fail check but a producer-side declaration: unset means
            # the producer has not claimed readiness, which is Blocked, not Failed.
            "LiveExecutionReadiness": (
                "NotStarted" if not checkout
                else "Passed" if producer.get("live_execution_ready")
                else "Blocked"
            ),
        }

        for gate_name, status in measured.items():
            gate_id = f"gate-{pid}-{gate_name}"
            rows.append({
                "id": gate_id, "gate_id": gate_id,
                "program_id": pid,
                "gate_name": gate_name,
                "status": status,
                # A real boolean: Gates.jsx:40 coerces the form's string back to
                # one, and Dashboard.jsx:29 tests truthiness directly.
                "blocking": True,
                "requirement": _GATE_REQUIREMENTS[gate_name],
                "review_notes": note,
                "reviewed_at": reviewed,
                "created_date": ts, "updated_date": ts,
            })
            if _GATE_SEVERITY[status] > _GATE_SEVERITY[worst_status]:
                worst_status = status

        if any(status != "Passed" for status in measured.values()):
            blocking_producers.append(pid)

    # GitHubSyncApproval is one of GATE_NAMES's ten entries but carries no
    # independent evidence of its own — it is the rollup of the three gates
    # just measured above, one row per federation rather than per producer.
    rows.append({
        "id": "gate-prog-control-GitHubSyncApproval",
        "gate_id": "gate-prog-control-GitHubSyncApproval",
        "program_id": "prog-control",
        "gate_name": "GitHubSyncApproval",
        "status": worst_status,
        "blocking": True,
        "requirement": (
            "Every federation producer must clear ManifestValidation, "
            "ExportPackageValidation and LiveExecutionReadiness before GitHub "
            "sync is approved for the federation."
        ),
        "review_notes": (
            "All producers cleared their gates." if not blocking_producers
            else f"Blocking producers: {', '.join(blocking_producers)}."
        ),
        "reviewed_at": reviewed,
        "created_date": ts, "updated_date": ts,
    })
    return rows


def _seed_control_program(
    conn: sqlite3.Connection,
    ts: str,
    snapshot: dict[str, Any],
    sync_gate: Optional[dict[str, Any]],
) -> bool:
    """Insert the hub's own Programs row once, if absent.

    Programs is a different collection from the trio above — it is already
    seeded (non-empty) by `_seed_programs` in main.py by the time this runs, so
    the whole-collection `_exists` check the trio uses would always skip a hub
    row here. Insert by id instead, the same per-row idempotency
    `_seed_programs` already uses for producer rows.
    """
    exists = conn.execute(
        "SELECT 1 FROM entities WHERE entity_type='Programs' AND entity_id='prog-control'"
    ).fetchone()
    if exists:
        return False

    hub_id = snapshot.get("hub", "thehub-pr")
    if sync_gate is None:
        parity_status = "Unmeasured"
        transition_status = "Unmeasured"
        github_sync_status = "NotConnected"
    else:
        passed = sync_gate["status"] == "Passed"
        parity_status = "Ready" if passed else sync_gate["status"]
        transition_status = "Complete" if passed else "InProgress"
        github_sync_status = (
            "Connected" if passed
            else "Error" if sync_gate["status"] == "Failed"
            else "Blocked"
        )

    row = {
        "id": "prog-control",
        "program_id": "prog-control",
        "name": "INTSYS-PR",
        "repo_name": hub_id,
        "source_repo": hub_id,
        "domain": "ControlPlane",
        "status": "Active",
        "lead_vector": "control_plane",
        "description": f"Federation operational transition layer for {hub_id}.",
        "transition_status": transition_status,
        "parity_status": parity_status,
        "github_sync_status": github_sync_status,
        "created_date": ts, "updated_date": ts,
    }
    conn.execute(
        "INSERT OR IGNORE INTO entities (entity_type, entity_id, data, updated_at) VALUES (?,?,?,?)",
        ("Programs", "prog-control", json.dumps(row), ts),
    )
    return True


def seed_federation_collections(
    conn: sqlite3.Connection,
    ts: str,
    *,
    status_path: Path,
    registry_path: Path,
) -> dict[str, int]:
    """Fill FederationManifest / IntegrationStatus / ValidationGates if empty,
    and seed the hub's own Programs row if absent.

    Returns the per-collection row counts written (absent keys were skipped
    because the collection already held rows).
    """
    snapshot = _load_snapshot(status_path)
    if snapshot is None:
        snapshot = _from_registry(registry_path)
        if snapshot is None:
            log.warning(
                "no federation status snapshot at %s and no readable registry at %s "
                "— control-plane collections stay empty", status_path, registry_path
            )
            return {}
        log.info(
            "no federation status snapshot at %s — seeding control-plane collections "
            "from the registry alone; ValidationGates needs `make federation-status`",
            status_path,
        )

    generated = snapshot.get("generated_at") or ts
    day = generated[:10]  # the UI fields are date inputs, not timestamps

    gate_rows = _gate_rows(snapshot, ts, day)
    sync_gate = next(
        (g for g in gate_rows if g["gate_name"] == "GitHubSyncApproval"), None
    )

    written: dict[str, int] = {}
    for entity_type, rows in (
        ("FederationManifest", _manifest_rows(snapshot, ts)),
        ("IntegrationStatus", _integration_rows(snapshot, ts, day, sync_gate)),
        ("ValidationGates", gate_rows),
    ):
        if not rows or _exists(conn, entity_type):
            continue
        written[entity_type] = _insert(conn, entity_type, rows, ts)

    if _seed_control_program(conn, ts, snapshot, sync_gate):
        written["Programs"] = 1

    conn.commit()
    if written:
        log.info("seeded federation control-plane collections: %s", written)
    return written
