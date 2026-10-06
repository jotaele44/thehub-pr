"""Certification-gated ASG MoneySweep leaderboard consumer for TheHub.

This module is intentionally separate from the existing debt leaderboard
consumer. TheHub verifies and renders exact producer rows; it never recomputes
ASG rankings, resolves name-only vendors, or widens the certified scope.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = (
    REPO_ROOT
    / "data"
    / "aggregate"
    / "moneysweep"
    / "asg_emergency_source_native_package.json"
)
DEFAULT_TRUST = (
    REPO_ROOT
    / "data"
    / "aggregate"
    / "moneysweep"
    / "asg_emergency_source_native_trust.json"
)

EXPECTED_SCHEMA = "moneysweep.leaderboard-export-package/v1"
EXPECTED_RANKING = "moneysweep.leaderboard/v1.1"
EXPECTED_ONTOLOGY = "moneysweep.financial-category-ontology/v1.1"
EXPECTED_SCOPE = "moneysweep.leaderboard.asg-emergency-source-native-v1"
EXPECTED_CATEGORY = "asg_emergency_purchase_source_native"
EXPECTED_METRIC = "ASG_EMERGENCY_PURCHASE_COST"
EXPECTED_CERT_RUNTIME = "moneysweep.leaderboard-certification-runtime/v1"
EXPECTED_SOURCE_ID = "asg_emergency_purchases"
EXPECTED_SOURCE_ORDERING = "-numerocontrol"
EXPECTED_INPUT = 1431
EXPECTED_OUT_OF_SCOPE = 1410
EXPECTED_RETAINED = 21
EXPECTED_CANDIDATES = 10
EXPECTED_TOTAL = 4423664.82

router = APIRouter(
    prefix="/api/moneysweep/asg-leaderboards",
    tags=["moneysweep-asg-leaderboards"],
)

_TRUST_FIELDS = {
    "PRII_MONEYSWEEP_ASG_LEADERBOARD_RECEIPT_SHA256": "receiptSha256",
    "PRII_MONEYSWEEP_ASG_LEADERBOARD_RELEASE_SHA256": "releaseManifestSha256",
    "PRII_MONEYSWEEP_ASG_LEADERBOARD_SCOPE_SHA256": "scopeSha256",
    "PRII_MONEYSWEEP_ASG_LEADERBOARD_PACKAGE_SHA256": "packageSha256",
}


def _is_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _is_sha1(value: object) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(ch in "0123456789abcdef" for ch in text)


def _canonical_sha256(value: Any) -> str:
    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _validate_file_manifest(
    files: object,
    *,
    prefix: str,
    require_bytes: bool,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(files, list) or not files:
        return [f"{prefix}.files"]
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            errors.append(f"{prefix}.fileShape")
            continue
        path = str(item.get("path") or "")
        if not path or path in seen:
            errors.append(f"{prefix}.filePath")
        seen.add(path)
        if not _is_sha256(item.get("sha256")):
            errors.append(f"{prefix}.fileSha256")
        if require_bytes and (
            not isinstance(item.get("bytes"), int) or item.get("bytes", -1) < 0
        ):
            errors.append(f"{prefix}.fileBytes")
    return errors


def _manifest_trusted_hashes(name: str) -> set[str]:
    field = _TRUST_FIELDS.get(name)
    if field is None or not DEFAULT_TRUST.exists():
        return set()
    try:
        document = json.loads(DEFAULT_TRUST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if document.get("schemaVersion") != "thehub.moneysweep-asg-leaderboard-trust/v1":
        return set()
    if document.get("state") != "FROZEN":
        return set()
    if document.get("producer") != "moneysweep-pr":
        return set()
    if document.get("scopeId") != EXPECTED_SCOPE:
        return set()
    digest = str(document.get(field) or "").lower()
    return {digest} if _is_sha256(digest) else set()


def _trusted_hashes(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    trusted = {item.strip().lower() for item in raw.split(",") if item.strip()}
    trusted.update(_manifest_trusted_hashes(name))
    return trusted


def _validate_package(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("schemaVersion") != EXPECTED_SCHEMA:
        errors.append("schemaVersion")
    if document.get("producer") != "moneysweep-pr":
        errors.append("producer")
    if document.get("rankingContractVersion") != EXPECTED_RANKING:
        errors.append("rankingContractVersion")
    if document.get("ontologyContractVersion") != EXPECTED_ONTOLOGY:
        errors.append("ontologyContractVersion")
    if document.get("scopeId") != EXPECTED_SCOPE:
        errors.append("scopeId")

    producer_commit = str(document.get("producerCommit") or "")
    if not _is_sha1(producer_commit):
        errors.append("producerCommit")

    certification = document.get("certification") or {}
    if certification.get("state") != "PASS":
        errors.append("certification.state")
    for key in (
        "receiptSha256",
        "releaseManifestSha256",
        "scopeSha256",
        "certificationRuntimeSha256",
    ):
        if not _is_sha256(certification.get(key)):
            errors.append(f"certification.{key}")

    cert_runtime = document.get("certificationRuntimeManifest")
    if not isinstance(cert_runtime, dict):
        errors.append("certificationRuntimeManifest")
    else:
        if cert_runtime.get("schemaVersion") != EXPECTED_CERT_RUNTIME:
            errors.append("certificationRuntimeManifest.schemaVersion")
        if cert_runtime.get("state") != "FROZEN":
            errors.append("certificationRuntimeManifest.state")
        errors.extend(
            _validate_file_manifest(
                cert_runtime.get("files"),
                prefix="certificationRuntimeManifest",
                require_bytes=True,
            )
        )
        expected_hash = certification.get("certificationRuntimeSha256")
        if _is_sha256(expected_hash) and _canonical_sha256(cert_runtime) != expected_hash:
            errors.append("certificationRuntimeManifest.sha256")

    categories = document.get("categories")
    if not isinstance(categories, list) or len(categories) != 1:
        errors.append("categories.scopeCardinality")
        categories = categories if isinstance(categories, list) else []

    for category in categories:
        category_id = str(category.get("categoryId") or "")
        prefix = f"categories.{category_id}"
        if category_id != EXPECTED_CATEGORY:
            errors.append(f"{prefix}.scopeCategory")
        if category.get("metricType") != EXPECTED_METRIC:
            errors.append(f"{prefix}.metricType")
        if category.get("candidateCount") != EXPECTED_CANDIDATES:
            errors.append(f"{prefix}.candidateCount")
        if not str(category.get("snapshotId") or ""):
            errors.append(f"{prefix}.snapshotId")
        if not _is_sha256(category.get("snapshotSha256")):
            errors.append(f"{prefix}.snapshotSha256")

        accounting = category.get("accounting")
        if not isinstance(accounting, dict):
            errors.append(f"{prefix}.accounting")
        else:
            expected_accounting = {
                "inputRecords": EXPECTED_INPUT,
                "outOfScopeRecords": EXPECTED_OUT_OF_SCOPE,
                "retainedRecords": EXPECTED_RETAINED,
                "excludedRecords": 0,
                "unresolvedRecords": 0,
                "inScopeRecords": EXPECTED_RETAINED,
                "arithmeticClosed": True,
            }
            for key, expected in expected_accounting.items():
                if accounting.get(key) != expected:
                    errors.append(f"{prefix}.accounting.{key}")

        source_version = category.get("sourceVersion")
        if not isinstance(source_version, dict):
            errors.append(f"{prefix}.sourceVersion")
        else:
            if source_version.get("type") != "LIVE_PORTAL_MATERIALIZATION":
                errors.append(f"{prefix}.sourceVersionType")
            if source_version.get("sourceId") != EXPECTED_SOURCE_ID:
                errors.append(f"{prefix}.sourceId")
            if source_version.get("authoritativeUniverseTotal") != EXPECTED_INPUT:
                errors.append(f"{prefix}.authoritativeUniverseTotal")
            if source_version.get("ordering") != EXPECTED_SOURCE_ORDERING:
                errors.append(f"{prefix}.ordering")
            if source_version.get("economicActivityInference") is not False:
                errors.append(f"{prefix}.economicActivityInference")
            if not _is_sha256(source_version.get("sourceSha256")):
                errors.append(f"{prefix}.sourceSha256")
            if not _is_sha256(source_version.get("rawBundleSha256")):
                errors.append(f"{prefix}.rawBundleSha256")

        source_manifestations = category.get("sourceManifestations")
        errors.extend(
            _validate_file_manifest(
                source_manifestations,
                prefix=f"{prefix}.sourceManifestations",
                require_bytes=False,
            )
        )

        runtime_manifest = category.get("runtimeManifest")
        if not isinstance(runtime_manifest, dict):
            errors.append(f"{prefix}.runtimeManifest")
        else:
            if runtime_manifest.get("state") != "FROZEN":
                errors.append(f"{prefix}.runtimeState")
            if runtime_manifest.get("producerCommit") != producer_commit:
                errors.append(f"{prefix}.runtimeProducerCommit")
            errors.extend(
                _validate_file_manifest(
                    runtime_manifest.get("files"),
                    prefix=f"{prefix}.runtimeManifest",
                    require_bytes=True,
                )
            )

        snapshot_cert = category.get("snapshotCertification")
        if not isinstance(snapshot_cert, dict):
            errors.append(f"{prefix}.snapshotCertification")
        else:
            if snapshot_cert.get("state") != "PASS":
                errors.append(f"{prefix}.snapshotCertificationState")
            if snapshot_cert.get("scopeId") != EXPECTED_SCOPE:
                errors.append(f"{prefix}.snapshotCertificationScope")
            if snapshot_cert.get("zeroMaterialUnresolvedResidue") is not True:
                errors.append(f"{prefix}.snapshotCertificationResidue")
            if not _is_sha256(snapshot_cert.get("sourceSnapshotSha256")):
                errors.append(f"{prefix}.sourceSnapshotSha256")

        rows = category.get("rows")
        if not isinstance(rows, list) or len(rows) != EXPECTED_CANDIDATES:
            errors.append(f"{prefix}.rows")
            continue

        seen_entities: set[str] = set()
        seen_controls: set[str] = set()
        total_value = 0.0
        total_records = 0
        prior_value: float | None = None
        prior_rank: int | None = None

        for position, row in enumerate(rows, start=1):
            entity_id = str(row.get("entityId") or "")
            if (
                not entity_id.startswith("asg_licitador_id:")
                or not entity_id.removeprefix("asg_licitador_id:").isdigit()
                or entity_id in seen_entities
            ):
                errors.append(f"{prefix}.entityIdentity")
            seen_entities.add(entity_id)

            if row.get("canonicalEntityId") is not None:
                errors.append(f"{prefix}.canonicalEntityId")
            if row.get("entityResolutionState") != "SOURCE_NATIVE_ASG_LICITADOR_ID":
                errors.append(f"{prefix}.identityState")
            if row.get("currency") != "USD":
                errors.append(f"{prefix}.currency")
            if row.get("metricType") != EXPECTED_METRIC:
                errors.append(f"{prefix}.rowMetricType")

            controls = row.get("controlNumbers")
            if not isinstance(controls, list) or not controls:
                errors.append(f"{prefix}.controlNumbers")
                controls = []
            for control in controls:
                text = str(control or "")
                if not text or text in seen_controls:
                    errors.append(f"{prefix}.controlUniqueness")
                seen_controls.add(text)

            try:
                record_count = int(row.get("recordCount"))
                value = float(row.get("metricValue"))
                rank = int(row.get("rank"))
            except (TypeError, ValueError):
                errors.append(f"{prefix}.rankShape")
                continue
            if record_count != len(controls) or record_count < 1:
                errors.append(f"{prefix}.recordCount")
            total_records += record_count
            total_value += value

            if prior_value is not None and value > prior_value:
                errors.append(f"{prefix}.valueOrder")
            expected_rank = (
                1
                if prior_value is None
                else (prior_rank if value == prior_value else position)
            )
            if rank != expected_rank:
                errors.append(f"{prefix}.competitionRank")
            prior_rank, prior_value = rank, value

        if total_records != EXPECTED_RETAINED:
            errors.append(f"{prefix}.retainedControlArithmetic")
        if len(seen_controls) != EXPECTED_RETAINED:
            errors.append(f"{prefix}.controlCardinality")
        if round(total_value, 2) != EXPECTED_TOTAL:
            errors.append(f"{prefix}.metricTotal")

    return sorted(set(errors))


def _load_package(path: Path = DEFAULT_PACKAGE) -> dict[str, Any]:
    if not path.exists():
        raise HTTPException(
            409,
            detail={
                "state": "BLOCKED",
                "reason": "certified ASG MoneySweep leaderboard package is not mounted",
            },
        )
    raw = path.read_bytes()
    package_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            409,
            detail={"state": "FAIL", "reason": "invalid ASG package JSON"},
        ) from exc

    errors = _validate_package(document)
    if errors:
        raise HTTPException(
            409,
            detail={
                "state": "FAIL",
                "reason": "ASG producer package contract failed",
                "errors": errors,
            },
        )

    certification = document["certification"]
    trust_specs = (
        ("receiptSha256", "PRII_MONEYSWEEP_ASG_LEADERBOARD_RECEIPT_SHA256"),
        ("releaseManifestSha256", "PRII_MONEYSWEEP_ASG_LEADERBOARD_RELEASE_SHA256"),
        ("scopeSha256", "PRII_MONEYSWEEP_ASG_LEADERBOARD_SCOPE_SHA256"),
    )
    trust_state: dict[str, bool] = {}
    for field, env_name in trust_specs:
        digest = certification[field]
        trust_state[field] = digest in _trusted_hashes(env_name)
    package_trusted = (
        package_sha256
        in _trusted_hashes("PRII_MONEYSWEEP_ASG_LEADERBOARD_PACKAGE_SHA256")
    )
    if not all(trust_state.values()) or not package_trusted:
        raise HTTPException(
            409,
            detail={
                "state": "BLOCKED",
                "reason": "ASG producer package hashes are not trusted by TheHub",
                "receiptTrusted": trust_state["receiptSha256"],
                "releaseTrusted": trust_state["releaseManifestSha256"],
                "scopeTrusted": trust_state["scopeSha256"],
                "packageTrusted": package_trusted,
            },
        )

    document["consumerPackageSha256"] = package_sha256
    return document


@router.get("/status")
def status():
    try:
        package = _load_package()
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"reason": str(exc.detail)}
        return {"state": detail.get("state", "BLOCKED"), **detail}
    category = package["categories"][0]
    return {
        "state": "PASS",
        "producerCommit": package["producerCommit"],
        "scopeId": package["scopeId"],
        "categoryId": category["categoryId"],
        "candidateCount": category["candidateCount"],
        "inputRecords": category["accounting"]["inputRecords"],
        "outOfScopeRecords": category["accounting"]["outOfScopeRecords"],
        "retainedRecords": category["accounting"]["retainedRecords"],
        "consumerPackageSha256": package["consumerPackageSha256"],
    }


@router.get("/top")
def top(limit: int = Query(25, ge=1, le=25)):
    package = _load_package()
    category = package["categories"][0]
    rows = category["rows"]
    cutoff_rank = rows[min(limit, len(rows)) - 1]["rank"]
    return {
        **category,
        "rows": [row for row in rows if row["rank"] <= cutoff_rank],
        "consumerState": "PASS",
        "producerCommit": package["producerCommit"],
        "scopeId": package["scopeId"],
        "consumerPackageSha256": package["consumerPackageSha256"],
        "scopeBoundary": (
            "Ranks only ASG emergency-purchase rows with explicit source-native "
            "ASG Licitador IDs. It does not represent all ASG emergency purchases."
        ),
    }
