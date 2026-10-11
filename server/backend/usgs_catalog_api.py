"""Read-only catalog and acquisition receipts; never exposes payload activation."""
import json
import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from hub.usgs_catalog import CATALOG, catalog_page, load_catalog

router = APIRouter(prefix="/api/usgs", tags=["usgs-catalog"])
SNAPSHOT = Path(__file__).resolve().parents[2] / "data/usgs/snapshots/20261011T013000Z/summary.json"


@router.get("/catalog")
def usgs_catalog(query: str = Query("", max_length=200), program: str = Query(None),
                 offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    try:
        result = catalog_page(load_catalog(CATALOG), query, program, offset, limit)
        if SNAPSHOT.exists():
            snapshot = json.loads(SNAPSHOT.read_text())
            if snapshot["source_workbook_sha256"] != result["source"]["sha256"]:
                raise ValueError("Snapshot/workbook source binding mismatch")
            receipts = {r["source_item_id"]: r for r in snapshot["receipts"]}
            if (len(receipts) != len(snapshot["receipts"]) or snapshot["attempted"] != len(receipts)
                    or set(receipts) != {r["sciencebase_id"] for r in load_catalog(CATALOG)["releases"]}):
                raise ValueError("Snapshot denominator does not close")
            for source_id, receipt in receipts.items():
                raw = (SNAPSHOT.parent / source_id / "response.bin").read_bytes()
                if hashlib.sha256(raw).hexdigest() != receipt["sha256"] or len(raw) != receipt["bytes"]:
                    raise ValueError("Frozen response evidence hash/size mismatch")
            for row in result["records"]:
                row["acquisition"] = receipts[row["sciencebase_id"]]
            result["acquisition_summary"] = {k: v for k, v in snapshot.items() if k != "receipts"}
        else:
            result["acquisition_summary"] = {"state": "OPEN", "reason": "No completed snapshot held"}
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Catalog evidence unavailable or invalid") from exc
