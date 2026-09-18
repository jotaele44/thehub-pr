"""Certification-gated MoneySweep leaderboard consumer for TheHub.

TheHub is a consumer only. It never recomputes MoneySweep rankings and never
upgrades producer evidence. A package becomes readable only when its embedded
producer contract is PASS, its production scope and provenance are exact, and
its receipt/release/scope/package hashes are explicitly trusted by runtime
configuration.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = REPO_ROOT / "data" / "aggregate" / "moneysweep" / "leaderboard_package.json"
EXPECTED_SCHEMA = "moneysweep.leaderboard-export-package/v1"
EXPECTED_RANKING = "moneysweep.leaderboard/v1.1"
EXPECTED_ONTOLOGY = "moneysweep.financial-category-ontology/v1.1"
EXPECTED_SCOPE = "moneysweep.leaderboard.production-v1"
EXPECTED_CATEGORY = "debt_issuance"
EXPECTED_METRIC = "DEBT_ISSUED_PAR"
EXPECTED_CERT_RUNTIME = "moneysweep.leaderboard-certification-runtime/v1"

router = APIRouter(prefix="/api/moneysweep/leaderboards", tags=["moneysweep-leaderboards"])


def _trusted_hashes(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _is_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _is_sha1(value: object) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(ch in "0123456789abcdef" for ch in text)


def _canonical_sha256(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
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
        if require_bytes and (not isinstance(item.get("bytes"), int) or item.get("bytes", -1) < 0):
            errors.append(f"{prefix}.fileBytes")
    return errors


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
        expected_runtime_hash = certification.get("certificationRuntimeSha256")
        if _is_sha256(expected_runtime_hash) and _canonical_sha256(cert_runtime) != expected_runtime_hash:
            errors.append("certificationRuntimeManifest.sha256")

    categories = document.get("categories")
    if not isinstance(categories, list) or len(categories) != 1:
        errors.append("categories.scopeCardinality")
        categories = categories if isinstance(categories, list) else []
    seen: set[str] = set()
    for category in categories:
        category_id = str(category.get("categoryId") or "")
        if not category_id or category_id in seen:
            errors.append("categories.uniqueCategoryId")
        seen.add(category_id)
        prefix = f"categories.{category_id}"
        if category_id != EXPECTED_CATEGORY:
            errors.append(f"{prefix}.scopeCategory")
        if category.get("metricType") != EXPECTED_METRIC:
            errors.append(f"{prefix}.metricType")
        if not str(category.get("snapshotId") or ""):
            errors.append(f"{prefix}.snapshotId")
        if not _is_sha256(category.get("snapshotSha256")):
            errors.append(f"{prefix}.snapshotSha256")
        if not str(category.get("capturedAt") or ""):
            errors.append(f"{prefix}.capturedAt")

        accounting = category.get("accounting")
        if not isinstance(accounting, dict):
            errors.append(f"{prefix}.accounting")
        else:
            if accounting.get("arithmeticClosed") is not True:
                errors.append(f"{prefix}.arithmeticClosed")
            if accounting.get("unresolvedRecords") != 0:
                errors.append(f"{prefix}.unresolvedRecords")
            if accounting.get("excludedRecords") != 0:
                errors.append(f"{prefix}.excludedRecords")

        source_version = category.get("sourceVersion")
        if not isinstance(source_version, dict):
            errors.append(f"{prefix}.sourceVersion")
        else:
            if source_version.get("type") != "GIT_COMMIT":
                errors.append(f"{prefix}.sourceVersionType")
            if not _is_sha1(source_version.get("commit")):
                errors.append(f"{prefix}.sourceVersionCommit")
            if not str(source_version.get("committedAt") or ""):
                errors.append(f"{prefix}.sourceVersionCommittedAt")
            if source_version.get("economicActivityInference") is not False:
                errors.append(f"{prefix}.economicActivityInference")

        source_manifestations = category.get("sourceManifestations")
        errors.extend(
            _validate_file_manifest(
                source_manifestations,
                prefix=f"{prefix}.sourceManifestations",
                require_bytes=False,
            )
        )
        if isinstance(source_version, dict) and isinstance(source_manifestations, list):
            source_commit = source_version.get("commit")
            for item in source_manifestations:
                if isinstance(item, dict) and item.get("sourceCommit") not in {None, "", source_commit}:
                    errors.append(f"{prefix}.sourceCommitMismatch")
                    break

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
        if not isinstance(rows, list) or not rows:
            errors.append(f"{prefix}.rows")
            continue
        if category.get("candidateCount") != len(rows):
            errors.append(f"{prefix}.candidateCount")
        prior_value: float | None = None
        prior_rank: int | None = None
        seen_entities: set[tuple[str, str]] = set()
        for position, row in enumerate(rows, start=1):
            entity_id = str(row.get("entityId") or "")
            display = str(row.get("entityDisplayName") or "")
            currency = str(row.get("currency") or "")
            key = (entity_id, currency)
            if not entity_id or key in seen_entities:
                errors.append(f"{prefix}.entityUniqueness")
            seen_entities.add(key)
            if not display:
                errors.append(f"{prefix}.entityDisplayName")
            if currency != "USD":
                errors.append(f"{prefix}.currency")
            identity_state = str(row.get("entityResolutionState") or "")
            if identity_state != "CANONICAL_V1_ENTITY_ID":
                errors.append(f"{prefix}.identityState")
            try:
                value = float(row["metricValue"])
                rank = int(row["rank"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"{prefix}.rankShape")
                continue
            if rank < 1:
                errors.append(f"{prefix}.rankMinimum")
            if prior_value is not None and value > prior_value:
                errors.append(f"{prefix}.valueOrder")
            expected_rank = 1 if prior_value is None else (prior_rank if value == prior_value else position)
            if rank != expected_rank:
                errors.append(f"{prefix}.competitionRank")
            prior_rank, prior_value = rank, value
    return sorted(set(errors))


def _load_package(path: Path = DEFAULT_PACKAGE) -> dict[str, Any]:
    if not path.exists():
        raise HTTPException(
            409,
            detail={
                "state": "BLOCKED",
                "reason": "certified MoneySweep leaderboard package is not mounted",
                "path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
            },
        )
    raw = path.read_bytes()
    package_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(409, detail={"state": "FAIL", "reason": "invalid package JSON"}) from exc
    errors = _validate_package(document)
    if errors:
        raise HTTPException(409, detail={"state": "FAIL", "reason": "producer package contract failed", "errors": errors})

    certification = document["certification"]
    trust_specs = (
        ("receiptSha256", "PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256"),
        ("releaseManifestSha256", "PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256"),
        ("scopeSha256", "PRII_MONEYSWEEP_LEADERBOARD_SCOPE_SHA256"),
    )
    trust_state: dict[str, bool] = {}
    for field, env_name in trust_specs:
        digest = certification[field]
        trust_state[field] = digest in _trusted_hashes(env_name)
    package_trusted = package_sha256 in _trusted_hashes("PRII_MONEYSWEEP_LEADERBOARD_PACKAGE_SHA256")
    if not all(trust_state.values()) or not package_trusted:
        raise HTTPException(
            409,
            detail={
                "state": "BLOCKED",
                "reason": "producer package hashes are not trusted by TheHub runtime",
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
    return {
        "state": "PASS",
        "producerCommit": package["producerCommit"],
        "rankingContractVersion": package["rankingContractVersion"],
        "ontologyContractVersion": package["ontologyContractVersion"],
        "scopeId": package["scopeId"],
        "categoryCount": len(package.get("categories") or []),
        "consumerPackageSha256": package["consumerPackageSha256"],
    }


@router.get("/top")
def top(category: str, limit: int = Query(25, ge=1, le=25)):
    package = _load_package()
    match = next((item for item in package.get("categories") or [] if item.get("categoryId") == category), None)
    if match is None:
        raise HTTPException(404, f"category not present in certified MoneySweep package: {category}")
    rows = match.get("rows") or []
    cutoff_rank = rows[min(limit, len(rows)) - 1]["rank"]
    return {
        **match,
        "rows": [row for row in rows if row["rank"] <= cutoff_rank],
        "consumerState": "PASS",
        "producerCommit": package["producerCommit"],
        "scopeId": package["scopeId"],
        "consumerPackageSha256": package["consumerPackageSha256"],
    }
