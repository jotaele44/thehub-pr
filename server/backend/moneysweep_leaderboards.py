"""Certification-gated MoneySweep leaderboard consumer for TheHub.

TheHub is a consumer only. It never recomputes MoneySweep rankings and never
upgrades producer evidence. A package becomes readable only when its embedded
producer contract is PASS and its receipt/release hashes are explicitly trusted
by the operator/runtime configuration.
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

router = APIRouter(prefix="/api/moneysweep/leaderboards", tags=["moneysweep-leaderboards"])


def _trusted_hashes(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _is_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


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
    commit = str(document.get("producerCommit") or "")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        errors.append("producerCommit")
    certification = document.get("certification") or {}
    if certification.get("state") != "PASS":
        errors.append("certification.state")
    for key in ("receiptSha256", "releaseManifestSha256"):
        if not _is_sha256(certification.get(key)):
            errors.append(f"certification.{key}")

    categories = document.get("categories")
    if not isinstance(categories, list) or not categories:
        errors.append("categories")
        categories = []
    seen: set[str] = set()
    for category in categories:
        category_id = str(category.get("categoryId") or "")
        if not category_id or category_id in seen:
            errors.append("categories.uniqueCategoryId")
        seen.add(category_id)
        if not str(category.get("metricType") or ""):
            errors.append(f"categories.{category_id}.metricType")
        if not str(category.get("snapshotId") or ""):
            errors.append(f"categories.{category_id}.snapshotId")
        if not _is_sha256(category.get("snapshotSha256")):
            errors.append(f"categories.{category_id}.snapshotSha256")
        rows = category.get("rows")
        if not isinstance(rows, list):
            errors.append(f"categories.{category_id}.rows")
            continue
        prior_value: float | None = None
        prior_rank: int | None = None
        seen_entities: set[tuple[str, str]] = set()
        for position, row in enumerate(rows, start=1):
            entity_id = str(row.get("entityId") or "")
            display = str(row.get("entityDisplayName") or "")
            currency = str(row.get("currency") or "")
            key = (entity_id, currency)
            if not entity_id or key in seen_entities:
                errors.append(f"categories.{category_id}.entityUniqueness")
            seen_entities.add(key)
            if not display:
                errors.append(f"categories.{category_id}.entityDisplayName")
            if not currency:
                errors.append(f"categories.{category_id}.currency")
            identity_state = str(row.get("entityResolutionState") or "")
            if not identity_state:
                errors.append(f"categories.{category_id}.entityResolutionState")
            if identity_state.startswith("NAME"):
                errors.append(f"categories.{category_id}.nameOnlyIdentity")
            try:
                value = float(row["metricValue"])
                rank = int(row["rank"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"categories.{category_id}.rankShape")
                continue
            if rank < 1:
                errors.append(f"categories.{category_id}.rankMinimum")
            if prior_value is not None and value > prior_value:
                errors.append(f"categories.{category_id}.valueOrder")
            expected_rank = 1 if prior_value is None else (prior_rank if value == prior_value else position)
            if rank != expected_rank:
                errors.append(f"categories.{category_id}.competitionRank")
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
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(409, detail={"state": "FAIL", "reason": "invalid package JSON"}) from exc
    errors = _validate_package(document)
    if errors:
        raise HTTPException(409, detail={"state": "FAIL", "reason": "producer package contract failed", "errors": errors})

    certification = document["certification"]
    trusted_receipts = _trusted_hashes("PRII_MONEYSWEEP_LEADERBOARD_RECEIPT_SHA256")
    trusted_releases = _trusted_hashes("PRII_MONEYSWEEP_LEADERBOARD_RELEASE_SHA256")
    receipt = certification["receiptSha256"]
    release = certification["releaseManifestSha256"]
    if receipt not in trusted_receipts or release not in trusted_releases:
        raise HTTPException(
            409,
            detail={
                "state": "BLOCKED",
                "reason": "producer package hashes are not trusted by TheHub runtime",
                "receiptTrusted": receipt in trusted_receipts,
                "releaseTrusted": release in trusted_releases,
            },
        )
    document["consumerPackageSha256"] = hashlib.sha256(raw).hexdigest()
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
    if not rows:
        return {**match, "rows": [], "consumerState": "PASS"}
    cutoff_rank = rows[min(limit, len(rows)) - 1]["rank"]
    return {
        **match,
        "rows": [row for row in rows if row["rank"] <= cutoff_rank],
        "consumerState": "PASS",
        "producerCommit": package["producerCommit"],
        "consumerPackageSha256": package["consumerPackageSha256"],
    }
