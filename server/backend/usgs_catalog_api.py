"""Read-only catalog and acquisition receipts; never exposes payload activation."""
import gzip
import json
import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from hub.usgs_catalog import CATALOG, catalog_page, load_catalog
from hub.usgs_assets import read_metadata_archive, root_membership

EVIDENCE_ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(prefix="/api/usgs", tags=["usgs-catalog"])
SNAPSHOT = Path(__file__).resolve().parents[2] / "data/usgs/snapshots/20261011T013000Z/summary.json"
METADATA_ARCHIVE = Path(__file__).resolve().parents[2] / "data/usgs/snapshots/20261016_runner_metadata.zip"
METADATA_ARCHIVE_SHA256 = "47488d1d72a2a43b8c2a4d3b44b600d4852ceca99e6796aae334814f95e7f7c8"


@router.get("/catalog")
def usgs_catalog(query: str = Query("", max_length=200), program: str = Query(None),
                 offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    try:
        result = catalog_page(load_catalog(CATALOG), query, program, offset, limit)
        if METADATA_ARCHIVE is not None and METADATA_ARCHIVE.exists():
            snapshot, items = read_metadata_archive(METADATA_ARCHIVE, METADATA_ARCHIVE_SHA256)
            receipts = {r['source_item_id']: r for r in snapshot['receipts']}
            expected = {r['sciencebase_id'] for r in load_catalog(CATALOG)['releases']}
            if set(items) != expected or snapshot['source_workbook_sha256'] != result['source']['sha256']:
                raise ValueError('Frozen metadata/catalog identity mismatch')
            for row in result['records']:
                sid = row['sciencebase_id']
                row['acquisition'] = receipts[sid]
                row['asset_descriptors_raw'] = items[sid].get('files', [])
                row['metadata_summary_raw'] = items[sid].get('summary')
                row['binding_review'] = {'state':'OPEN', 'reason':'Metadata acquired; payload semantics and consumer fitness remain under review'}
            result['acquisition_summary'] = {k:v for k,v in snapshot.items() if k != 'receipts'}
            result['acquisition_summary']['root_file_descriptors'] = sum(len(i.get('files', [])) for i in items.values())
            result['acquisition_summary']['root_declared_bytes'] = sum(f.get('size') or 0 for i in items.values() for f in i.get('files', []))
            result['acquisition_summary']['archive_sha256'] = METADATA_ARCHIVE_SHA256
            result['acquisition_summary']['historical_snapshot'] = '20261011T013000Z: 174 HTTP 403 observations retained'
            evidence = json.loads((EVIDENCE_ROOT / 'registry/usgs/continuation_evidence.v1.json').read_text())
            packed = (EVIDENCE_ROOT / 'data/usgs/continuation_inventory.v1.json.gz').read_bytes()
            if hashlib.sha256(packed).hexdigest() != evidence['compressed_inventory_sha256']:
                raise ValueError('Continuation compressed evidence hash mismatch')
            raw = gzip.decompress(packed)
            if len(raw) != evidence['inventory_bytes'] or hashlib.sha256(raw).hexdigest() != evidence['inventory_sha256']:
                raise ValueError('Continuation inventory hash/size mismatch')
            inventory = json.loads(raw)
            if inventory['root_archive_sha256'] != METADATA_ARCHIVE_SHA256 or inventory['source_workbook_sha256'] != result['source']['sha256']:
                raise ValueError('Continuation source binding mismatch')
            membership = root_membership(expected, inventory['child_edges'])
            result['continuation_summary'] = {k:v for k,v in inventory.items() if k not in ('assets','child_edges')}
            for row in result['records']:
                assets = [a for a in inventory['assets'] if row['sciencebase_id'] in membership.get(a['source_item_id'], [])]
                row['recursive_asset_summary'] = {state:sum(a['payload_state'] == state for a in assets) for state in ('PASS','FAIL','BLOCKED')}
                row['quarantined_assets'] = [a for a in assets if a['payload_state'] == 'FAIL']

        elif SNAPSHOT.exists():
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
