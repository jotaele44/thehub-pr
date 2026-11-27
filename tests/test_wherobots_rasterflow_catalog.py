"""Guards the Wherobots RasterFlow capability catalog (ADR 0011).

The catalog is a non-authoritative reference: webinar claims recorded exactly as
presented, with the status the presenter gave each item. These tests keep it that
way. They pin the counts and the closed status vocabulary, keep the cautioned
entries cautioned, require the human-readable snapshot to agree with the registry
file row for row, and require the ADR to keep both authority-mapping options open.

Nothing here contacts the vendor or verifies any claim; that is gate 1 in the ADR.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "registry" / "external_services" / "wherobots_rasterflow_catalog.v1.json"
SNAPSHOT = ROOT / "docs" / "gis" / "WHEROBOTS_RASTERFLOW_CATALOG_2026-11-05.md"
ADR = ROOT / "docs" / "adr" / "0011-wherobots-rasterflow-evaluation.md"

SOURCE_SHA256 = "feaf45c04e6bf72a2798695650289860bcbb0ae2b0568a887eb9bac6dcdcbaa6"
LAST_TRANSCRIPT_TIMESTAMP = "42:39"

# (group id, entries) in catalog order; first and last IDs follow from the counts.
GROUP_COUNTS = [
    ("platform", 14),
    ("source_data", 14),
    ("models", 9),
    ("imagery", 15),
    ("inference", 21),
    ("analytics", 9),
    ("publish", 11),
    ("s3_security", 6),
    ("agent_api", 14),
    ("workflows", 10),
    ("ecosystem", 16),
    ("finops", 10),
    ("quality", 8),
]

# The tokens the source's own "Status interpretation" paragraph defines.
SOURCE_DEFINED_TOKENS = {
    "DEMO",
    "CLAIMED",
    "CASE_STUDY",
    "PLANNED",
    "PREVIEW_DEMO",
    "INFERRED_RISK",
}


def _load() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def _by_id(doc: dict) -> dict:
    return {entry["id"]: entry for entry in doc["entries"]}


def test_counts_and_group_ranges():
    doc = _load()
    entries = doc["entries"]
    assert len(entries) == 157
    assert [g["id"] for g in doc["groups"]] == [gid for gid, _ in GROUP_COUNTS]
    assert sum(n for _, n in GROUP_COUNTS) == 157

    assert [e["id"] for e in entries] == [f"RF-{i:03d}" for i in range(1, 158)]

    next_number = 1
    for group, (gid, count) in zip(doc["groups"], GROUP_COUNTS):
        assert group["count"] == count, gid
        assert group["first_id"] == f"RF-{next_number:03d}", gid
        assert group["last_id"] == f"RF-{next_number + count - 1:03d}", gid
        rows = [e for e in entries if e["group"] == gid]
        assert len(rows) == count, gid
        assert [e["id"] for e in rows] == [
            f"RF-{n:03d}" for n in range(next_number, next_number + count)
        ], gid
        next_number += count


def test_entry_fields_are_complete_and_timestamps_are_in_range():
    for entry in _load()["entries"]:
        assert set(entry) == {
            "id",
            "group",
            "name",
            "timestamp",
            "status",
            "status_tokens",
            "description",
        }, entry["id"]
        for key in ("name", "description"):
            assert entry[key] and entry[key] == entry[key].strip(), (entry["id"], key)
        assert re.fullmatch(r"\d{2}:\d{2}", entry["timestamp"]), entry["id"]
        # The transcript ends at 42:39; a later timestamp cannot come from it.
        assert entry["timestamp"] <= LAST_TRANSCRIPT_TIMESTAMP, entry["id"]
        assert entry["status_tokens"] == entry["status"].split("+"), entry["id"]


def test_status_vocabulary_is_closed_and_honest_about_who_defined_it():
    doc = _load()
    vocab = doc["status_vocabulary"]
    used = {tok for e in doc["entries"] for tok in e["status_tokens"]}
    assert used == set(vocab), (sorted(used - set(vocab)), sorted(set(vocab) - used))
    assert len(vocab) == 16
    for token, spec in vocab.items():
        assert spec["meaning"].strip(), token
        expected = "source" if token in SOURCE_DEFINED_TOKENS else "inferred_from_use"
        assert spec["defined_by"] == expected, token
    # No status may claim verification: the vocabulary has no such token.
    assert not [t for t in vocab if "VERIFIED" in t or "CERTIFIED" in t]


def test_source_and_decision_state_are_not_overstated():
    doc = _load()
    source = doc["source"]
    assert source["sha256"] == SOURCE_SHA256
    assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
    assert source["last_timestamp"] == LAST_TRANSCRIPT_TIMESTAMP
    assert source["chapters"] == 16
    assert source["evidence_tier"] == "T4"
    assert source["independently_verified"] is False
    assert doc["subject"]["release_state"] == "UNVERIFIED"
    assert doc["decision_state"] == {
        "adoption": "NOT_AUTHORIZED",
        "authority_mapping": "OPEN",
        "adr": "docs/adr/0011-wherobots-rasterflow-evaluation.md",
    }
    assert (ROOT / doc["decision_state"]["adr"]).is_file()


def test_cautioned_entries_stay_cautioned():
    entries = _by_id(_load())
    # Future or preview capabilities are never recorded as available.
    assert "PLANNED" in entries["RF-017"]["status_tokens"]
    assert "PLANNED" in entries["RF-103"]["status_tokens"]
    assert "PREVIEW_DEMO" in entries["RF-103"]["status_tokens"]
    for rid in ("RF-111", "RF-112"):
        assert "PLANNED" in entries[rid]["status_tokens"], rid
    # The internally inconsistent boat-count anecdote must not become a verified reduction.
    assert entries["RF-155"]["status"] == "TRANSCRIPT_ISSUE"
    assert "24 to 51" in entries["RF-155"]["description"]
    assert entries["RF-132"]["status"] == "TRANSCRIPT_UNCERTAIN"
    # Analytical cautions are the analyst's, not the speaker's.
    for rid in ("RF-154", "RF-156", "RF-157"):
        assert entries[rid]["status"] == "INFERRED_RISK", rid
    # Prices and engineering estimates are vendor-presented, never quotes.
    for rid in ("RF-146", "RF-147", "RF-148", "RF-149"):
        assert entries[rid]["status"] == "VENDOR_CLAIM", rid
    for rid in ("RF-144", "RF-145"):
        assert entries[rid]["status"] == "CASE_STUDY", rid
    assert "not current quote" in entries["RF-144"]["description"]
    # The change-monitoring item is a direction, not an implemented API.
    assert entries["RF-079"]["status"] == "DIRECTION"


def _snapshot_rows() -> dict:
    """(timestamp, status) per ID from the catalog tables of the snapshot.

    Only the catalog section is read: the data-quality table below it also has
    rows that start with an RF- ID but are commentary, not catalog entries.
    """
    text = SNAPSHOT.read_text(encoding="utf-8")
    start = text.index("## Catalog — 157 entries in 13 groups")
    end = text.index("## Data-quality flags")
    row = re.compile(r"^\| (RF-\d{3}) \| .+? \| (\d{2}:\d{2}) \| ([A-Z_+]+) \| .+ \|$")
    rows = {}
    for line in text[start:end].splitlines():
        match = row.match(line)
        if match:
            assert match.group(1) not in rows, f"duplicate row {match.group(1)}"
            rows[match.group(1)] = (match.group(2), match.group(3))
    return rows


def test_snapshot_matches_registry_row_for_row():
    rows = _snapshot_rows()
    expected = {e["id"]: (e["timestamp"], e["status"]) for e in _load()["entries"]}
    assert len(rows) == 157
    assert rows == expected


def test_snapshot_states_its_limits():
    text = SNAPSHOT.read_text(encoding="utf-8")
    assert SOURCE_SHA256 in text
    assert "T4" in text
    assert "unverified" in text.lower()
    assert "proposed and not adopted" in text
    assert "0011-wherobots-rasterflow-evaluation.md" in text


def test_adr_keeps_both_authority_options_open():
    text = ADR.read_text(encoding="utf-8")
    assert "- **Status:** Proposed" in text
    assert "Option A" in text and "Option B" in text
    assert "This ADR takes no position" in text
    # The accepted decisions the recommendation collides with stay named.
    assert "ADR 0006" in text
    assert "DUCKDB_SPATIAL.md" in text
    # All thirteen supplied gates are present in the D5 table.
    gate_rows = re.findall(r"^\| (\d{1,2}) \| ", text, flags=re.M)
    assert [int(n) for n in gate_rows] == list(range(1, 14))
