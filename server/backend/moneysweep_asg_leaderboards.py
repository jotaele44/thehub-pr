"""Fail-closed TheHub consumer for the bounded MoneySweep ASG source-native leaderboard.

This is intentionally separate from the certified debt-production consumer.
It accepts only the ASG source-native certification scope and never recomputes
MoneySweep totals, identity, rank, or source accounting.
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
    / "asg_source_native_leaderboard_package.json"
)
DEFAULT_TRUST = (
    REPO_ROOT
    / "data"
    / "aggregate"
    / "moneysweep"
    / "asg_source_native_leaderboard_trust.json"
)

EXPECTED_SCHEMA = "moneysweep.leaderboard-export-package/v1"
EXPECTED_RANKING = "moneysweep.leaderboard/v1.1"
EXPECTED_ONTOLOGY = "moneysweep.financial-category-ontology/v1.2"
EXPECTED_SCOPE = "moneysweep.leaderboard.asg-source-native-v1"
EXPECTED_CATEGORY = "asg_emergency_purchase_source_native"
EXPECTED_METRIC = "ASG_EMERGENCY_PURCHASE_COST"
EXPECTED_IDENTITY = "SOURCE_NATIVE_ASG_LICITADOR_ID"
EXPECTED_CERT_RUNTIME = "moneysweep.leaderboard-certification-runtime/v1"
EXPECTED_INPUT = 1431
EXPECTED_OUT_OF_SCOPE = 1410
EXPECTED_RETAINED = 21
EXPECTED_CANDIDATES = 10
EXPECTED_SOURCE_ID = "asg_emergency_purchases"
EXPECTED_SOURCE_ORDERING = "numerocontrol"

_TRUST_FIELDS = {
    "PRII_MONEYSWEEP_ASG_LEADERBOARD_RECEIPT_SHA256": "receiptSha256",
    "PRII_MONEYSWEEP_ASG_LEADERBOARD_RELEASE_SHA256": "releaseManifestSha256",
    "PRII_MONEYSWEEP_ASG_LEADERBOARD_SCOPE_SHA256": "scopeSha256",
    "PRII_MONEYSWEEP_ASG_LEADERBOARD_PACKAGE_SHA256": "packageSha256",
}

router = APIRouter(
    prefix="/api/moneysweep/leaderboards/asg-source-native",
    tags=["moneysweep-asg-source-native-leaderboard"],
)


def _is_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _is_sha1(value: object) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(ch in "0123456789abcdef" for ch in text)


def _canonical_sha256(value: Any) -> str:
    rendered = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


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


def _validate_file_manifest(
    files: object, *, prefix: str, require_bytes: bool
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


def _validate_accounting(value: object, prefix: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix}.accounting"]
    expected = {
        "inputRecords": EXPECTED_INPUT,
        "outOfScopeRecords": EXPECTED_OUT_OF_SCOPE,
        "retainedRecords": EXPECTED_RETAINED,
        "excludedRecords": 0,
        "unresolvedRecords": 0,
        "inScopeRecords": EXPECTED_RETAINED,
        "arithmeticClosed": True,
    }
    return [
        f"{prefix}.accounting.{key}"
        for key, target in expected.items()
        if value.get(key) != target
    ]


def _validate_source_version(value: object, prefix: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix}.sourceVersion"]
    errors: list[str] = []
    if value.get("type") != "LIVE_PORTAL_MATERIALIZATION":
        errors.append(f"{prefix}.sourceVersionType")
    if value.get("sourceId") != EXPECTED_SOURCE_ID:
        errors.append(f"{prefix}.sourceVersionSourceId")
    if value.get("ordering") != EXPECTED_SOURCE_ORDERING:
        errors.append(f"{prefix}.sourceVersionOrdering")
    if value.get("authoritativeUniverseTotal") != EXPECTED_INPUT:
        errors.append(f"{prefix}.sourceVersionUniverse")
    if not str(value.get("capturedAt") or ""):
        errors.append(f"{prefix}.sourceVersionCapturedAt")
    if not _is_sha256(value.get("sourceSha256")):
        errors.append(f"{prefix}.sourceVersionSourceSha256")
    if not _is_sha256(value.get("rawBundleSha256")):
        errors.append(f"{prefix}.sourceVersionRawBundleSha256")
    if value.get("economicActivityInference") is not False:
        errors.append(f"{prefix}.economicActivityInference")
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

    certification = document.get("certification")
    if not isinstance(certification, dict):
        errors.append("certification")
        certification = {}
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
        expected = certification.get("certificationRuntimeSha256")
        if _is_sha256(expected) and _canonical_sha256(cert_runtime) != expected:
            errors.append("certificationRuntimeManifest.sha256")

    categories = document.get("categories")
    if not isinstance(categories, list) or len(categories) != 1:
        errors.append("categories.scopeCardinality")
        categories = categories if isinstance(categories, list) else []

    for category in categories:
        category_id = str(category.get("categoryId") or "")
        prefix = f"categories.{category_id or 'missing'}"
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
        if not str(category.get("capturedAt") or ""):
            errors.append(f"{prefix}.capturedAt")

        errors.extend(_validate_accounting(category.get("accounting"), prefix))
        errors.extend(_validate_source_version(category.get("sourceVersion"), prefix))

        manifestations = category.get("sourceManifestations")
        errors.extend(
            _validate_file_manifest(
                manifestations,
                prefix=f"{prefix}.sourceManifestations",
                require_bytes=True,
            )
        )
        if isinstance(manifestations, list):
            types = {
                str(item.get("manifestationType") or "")
                for item in manifestations
                if isinstance(item, dict)
            }
            required_types = {
                "FLOOT_OBJECT_STORAGE_AUTHORITATIVE_CORPUS",
                "FLOOT_OBJECT_STORAGE_PAGE_MANIFEST",
                "FLOOT_OBJECT_STORAGE_SUPPLIER_ID_VERIFICATION",
            }
            if not required_types.issubset(types):
                errors.append(f"{prefix}.sourceManifestationTypes")

        runtime = category.get("runtimeManifest")
        if not isinstance(runtime, dict):
            errors.append(f"{prefix}.runtimeManifest")
        else:
            if runtime.get("state") != "FROZEN":
                errors.append(f"{prefix}.runtimeState")
            if runtime.get("producerCommit") != producer_commit:
                errors.append(f"{prefix}.runtimeProducerCommit")
            errors.extend(
                _validate_file_manifest(
                    runtime.get("files"),
                    prefix=f"{prefix}.runtimeManifest",
                    require_bytes=True,
                )
            )

        snap_cert = category.get("snapshotCertification")
        if not isinstance(snap_cert, dict):
            errors.append(f"{prefix}.snapshotCertification")
        else:
            if snap_cert.get("state") != "PASS":
                errors.append(f"{prefix}.snapshotCertificationState")
            if snap_cert.get("scopeId") != EXPECTED_SCOPE:
                errors.append(f"{prefix}.snapshotCertificationScope")
            if snap_cert.get("zeroMaterialUnresolvedResidue") is not True:
                errors.append(f"{prefix}.snapshotCertificationResidue")
            if not _is_sha256(snap_cert.get("sourceSnapshotSha256")):
                errors.append(f"{prefix}.sourceSnapshotSha256")

        rows = category.get("rows")
        if not isinstance(rows, list) or len(rows) != EXPECTED_CANDIDATES:
            errors.append(f"{prefix}.rows")
            continue

        prior_value: float | None = None
        prior_rank: int | None = None
        seen: set[tuple[str, str]] = set()
        record_count = 0
        for position, row in enumerate(rows, start=1):
            entity_id = str(row.get("entityId") or "")
            currency = str(row.get("currency") or "")
            key = (entity_id, currency)
            if (
                not entity_id.startswith("asg_licitador_id:")
                or key in seen
            ):
                errors.append(f"{prefix}.entityUniqueness")
            seen.add(key)
            if not str(row.get("entityDisplayName") or ""):
                errors.append(f"{prefix}.entityDisplayName")
            if row.get("canonicalEntityId") is not None:
                errors.append(f"{prefix}.canonicalEntityPromotion")
            if row.get("entityResolutionState") != EXPECTED_IDENTITY:
                errors.append(f"{prefix}.identityState")
            if row.get("metricType") != EXPECTED_METRIC:
                errors.append(f"{prefix}.rowMetricType")
            if currency != "USD":
                errors.append(f"{prefix}.currency")
            try:
                value = float(row["metricValue"])
                rank = int(row["rank"])
                count = int(row["recordCount"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"{prefix}.rankShape")
                continue
            if count <= 0:
                errors.append(f"{prefix}.recordCount")
            else:
                record_count += count
            if prior_value is not None and value > prior_value:
                errors.append(f"{prefix}.valueOrder")
            expected_rank = (
                1
                if prior_value is None
                else (prior_rank if value == prior_value else position)
            )
            if rank != expected_rank:
                errors.append(f"{prefix}.competitionRank")
            prior_value, prior_rank = value, rank

        if record_count != EXPECTED_RETAINED:
            errors.append(f"{prefix}.recordCountConservation")

    return sorted(set(errors))


def _load_package(path: Path = DEFAULT_PACKAGE) -> dict[str, Any]:
    if not path.exists():
        raise HTTPException(
            409,
            detail={
                "state": "BLOCKED",
                "reason": "certified MoneySweep ASG package is not mounted",
                "path": str(path.relative_to(REPO_ROOT))
                if path.is_relative_to(REPO_ROOT)
                else str(path),
            },
        )
    raw = path.read_bytes()
    package_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            409, detail={"state": "FAIL", "reason": "invalid package JSON"}
        ) from exc

    errors = _validate_package(document)
    if errors:
        raise HTTPException(
            409,
            detail={
                "state": "FAIL",
                "reason": "producer ASG package contract failed",
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
        trust_state[field] = certification[field] in _trusted_hashes(env_name)
    package_trusted = package_sha256 in _trusted_hashes(
        "PRII_MONEYSWEEP_ASG_LEADERBOARD_PACKAGE_SHA256"
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
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"reason": str(exc.detail)}
        )
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
    }
