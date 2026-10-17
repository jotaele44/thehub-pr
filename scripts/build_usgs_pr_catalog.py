"""Rebuild the catalog from frozen XLSX bytes without spreadsheet dependencies."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hub.usgs_catalog import validate_catalog  # noqa: E402

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_frozen_xlsx(path):
    result = {}
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(e.itertext()) for e in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        wb = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = {e.attrib["Id"]: e.attrib["Target"] for e in
                ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        for sheet in wb.find("s:sheets", NS):
            target = rels[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
            member = target.lstrip("/") if target.startswith("/") else "xl/" + target
            rows = []
            for row in ET.fromstring(archive.read(member)).findall("s:sheetData/s:row", NS):
                cells = {}
                for cell in row:
                    if cell.find("s:f", NS) is not None:
                        raise ValueError("Formula cells require explicit adjudication")
                    col = re.match(r"([A-Z]+)", cell.attrib["r"])[1]
                    index = 0
                    for char in col:
                        index = index * 26 + ord(char) - 64
                    value = cell.find("s:v", NS)
                    if cell.attrib.get("t") == "inlineStr":
                        value = "".join(e.text or "" for e in cell.findall("s:is//s:t", NS))
                    elif value is None:
                        value = None
                    elif cell.attrib.get("t") == "s":
                        value = strings[int(value.text)]
                    elif cell.attrib.get("t") in ("str", "e"):
                        value = value.text
                    else:
                        value = float(value.text)
                        if value.is_integer():
                            value = int(value)
                    cells[index - 1] = value
                rows.append((int(row.attrib["r"]), cells))
            result[sheet.attrib["name"]] = rows
    return result


def build():
    path = ROOT / "data/usgs/source/usgs_data_releases_puerto_rico.xlsx"
    sheets = read_frozen_xlsx(path)
    expected = ["Category", "Title", "Year", "ScienceBase URL", "DOI", "How PR was identified", "Notes"]
    first = sheets["PR datasets"][0]
    if first[0] != 1 or [first[1].get(i) for i in range(7)] != expected:
        raise ValueError("Unexpected preamble/header/schema")
    producers = yaml.safe_load((ROOT / "registry/producers.yaml").read_text())["producers"]
    repos = [{"program_id": p["program_id"], "repo": p["repo"], "role": p["role"]} for p in producers]
    by_id = {p["program_id"]: p["repo"] for p in producers}
    # Broad discovery rules produce consumer candidates, never authoritative assignments.
    water = re.compile(r"water|hydrolog|rain|precipitation|stream|aquifer|flood|watershed|sediment|lago|reef|fish|frog|forest|land cover|bat |bee|species|habitat|coral|turtle|mangrove|climate|temperature|ecolog", re.I)
    money = re.compile(r"water.use|withdrawal|bottling|federal real property|damages|losses|road network", re.I)
    releases = []
    for row_number, cells in sheets["PR datasets"][1:]:
        raw = {name: cells.get(i) for i, name in enumerate(expected)}
        source_id = raw["ScienceBase URL"].rsplit("/", 1)[-1]
        if not re.fullmatch(r"[a-f0-9]{24}", source_id):
            raise ValueError("Invalid ScienceBase stable ID")
        targets = [("spiderweb-pr", "Spatial/context discovery; asset semantics require review")]
        if water.search(raw["Title"]):
            targets.append(("aguayluz-pr", "Water/environment discovery rule; scope requires review"))
        if money.search(raw["Title"]):
            targets.append(("moneysweep-pr", "Infrastructure/resource-use context only; no financial inference"))
        releases.append({"sciencebase_id": source_id, "workbook_row": row_number, "raw": raw,
                         "catalog_owner": "jotaele44/thehub-pr", "payload_verified": False,
                         "activation_state": "BLOCKED", "spatial_state": "UNRESOLVED",
                         "consumer_candidates": [{"program_id": p, "repository": by_id[p],
                                                  "state": "CANDIDATE_NOT_IDENTITY", "basis": basis}
                                                 for p, basis in targets],
                         "open_gates": ["asset_enumeration", "payload_hash", "schema_count_closure",
                                        "pr_coverage", "version_lineage", "usage_constraints",
                                        "consumer_review", "format_adapter", "producer_export_contract"]})
    excluded_rows = sheets["Excluded"]
    excluded_header = [excluded_rows[0][1].get(i) for i in range(5)]
    if excluded_header != ["Reason class", "Title", "Year", "ScienceBase URL", "Why excluded"]:
        raise ValueError("Unexpected excluded schema")
    excluded = [{"workbook_row": n, "sciencebase_id": cells[3].rsplit("/", 1)[-1],
                 "raw": {h: cells.get(i) for i, h in enumerate(excluded_header)},
                 "state": "AUDIT_ONLY"} for n, cells in excluded_rows[1:]]
    method = [{"key": cells.get(0), "value": cells.get(1)} for _, cells in sheets["Method"]]
    catalog = {"contract": "prii.usgs-pr-catalog/v1", "source": {
        "path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "schema": expected, "sheet_counts": {s: len(rows) for s, rows in sheets.items()},
        "method_raw": method, "retrieval_claim_state": "WORKBOOK_REPORTED_NOT_INDEPENDENTLY_VERIFIED"},
        "counts": {"included": len(releases), "excluded": len(excluded),
                   "reviewed_rows": len(releases) + len(excluded),
                   "categories": dict(Counter(r["raw"]["Category"] for r in releases)),
                   "missing_doi": sum(not r["raw"]["DOI"] for r in releases)},
        "repositories": repos, "releases": releases, "excluded": excluded,
        "issues": [{"state": "OPEN", "kind": "COUNT", "detail":
                    "186 reported keyword hits versus 197 included/excluded rows; supplementary sweep attribution not provided"},
                   {"state": "OPEN", "kind": "SCOPE", "detail":
                    "Direct-child collection discovery only; national/global coverage and actual PR rows require verification"},
                   {"state": "OPEN", "kind": "GEOMETRY", "detail":
                    "Workbook flags global extent and swapped coordinates; preserve raw, verify independently before deriving geometry"}]}
    validate_catalog(catalog)
    output = ROOT / "registry/usgs/pr_releases.v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(catalog["counts"]))


if __name__ == "__main__":
    build()
