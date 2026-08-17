"""Tests for project_signs: per-project consolidation signs from an aggregate."""
from __future__ import annotations

import json
from pathlib import Path

from hub.cli import main
from hub.project_signs import (
    _money,
    build_project_signs,
    render_sign_html,
    write_project_signs,
)

_TS = "2026-01-01T00:00:00Z"
_LINEAGE = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}
SRC = "src_0123456789abcdef0123456789abcdef"

RECIPIENT = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0001"  # the works project
SENADO = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0002"     # funding agency
SENADOR = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0003"     # second funding agency
PRES = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0004"        # official (person)
AWD_1 = "awd_" + "1" * 32
AWD_2 = "awd_" + "2" * 32
REL_1 = "rel_" + "1" * 32


def _write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def _entity(eid, name, etype, *, synthetic=True):
    return {
        "entity_id": eid, "source_id": SRC, "name": name, "normalized_name": name.upper(),
        "entity_type": etype, "jurisdiction": "PR", "confidence": 0.9,
        "lineage": _LINEAGE, "synthetic": synthetic, "created_at": _TS, "extracted_at": _TS,
    }


def _award(award_id, agency_id, amount, *, synthetic=True):
    return {
        "award_id": award_id, "source_id": SRC, "recipient_entity_id": RECIPIENT,
        "funding_agency_entity_id": agency_id, "amount": amount, "currency": "USD",
        "fiscal_year": 2026, "award_type": "Pavimentación", "award_date": "2026-01-01",
        "confidence": 0.9, "location": {"municipality": "Urb. Encantada",
        "municipality_name": "Trujillo Alto"}, "lineage": _LINEAGE, "synthetic": synthetic,
        "created_at": _TS, "extracted_at": _TS,
    }


def _relationship(rid, src_eid, tgt_eid, explanation):
    return {
        "relationship_id": rid, "source_id": SRC,
        "source_entity_id": src_eid, "target_entity_id": tgt_eid,
        "relationship_type": "official_of", "evidence_source_id": SRC,
        "explanation": explanation, "confidence": 0.9, "lineage": _LINEAGE,
        "synthetic": True, "created_at": _TS, "extracted_at": _TS,
    }


def _build_aggregate(tmp_path, *, synthetic=True) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_jsonl(tmp_path / "entities.jsonl", [
        _entity(RECIPIENT, "Urb. Encantada", "project", synthetic=synthetic),
        _entity(SENADO, "Senado de Puerto Rico", "organization", synthetic=synthetic),
        _entity(SENADOR, "Senador de Distrito", "organization", synthetic=synthetic),
        _entity(PRES, "Thomas Rivera Schatz", "person", synthetic=synthetic),
    ])
    _write_jsonl(tmp_path / "funding_awards.jsonl", [
        _award(AWD_1, SENADO, 800000.0, synthetic=synthetic),
        _award(AWD_2, SENADOR, 375000.0, synthetic=synthetic),
    ])
    _write_jsonl(tmp_path / "relationships.jsonl", [
        _relationship(REL_1, PRES, SENADO, "Presidente"),
    ])
    return tmp_path


def test_awards_group_into_one_sign_with_two_contributions(tmp_path):
    _build_aggregate(tmp_path)
    signs = build_project_signs(tmp_path)
    assert len(signs) == 1
    sign = signs[0]
    assert sign["title"] == "Pavimentación"
    assert "Trujillo Alto" in sign["location"]
    assert len(sign["contributions"]) == 2
    # Sorted amount-desc: Senado ($800k) first.
    assert sign["contributions"][0]["agency_name"] == "Senado de Puerto Rico"
    assert sign["contributions"][0]["amount"] == 800000.0


def test_total_amount_sums_awards(tmp_path):
    _build_aggregate(tmp_path)
    sign = build_project_signs(tmp_path)[0]
    assert sign["total_amount"] == 1175000.0


def test_money_formatting():
    assert _money(800000.0) == "$800,000.00"
    assert _money(375000.0, "USD") == "$375,000.00"
    assert _money(None) == "$0.00"


def test_officials_resolve_onto_their_agency(tmp_path):
    _build_aggregate(tmp_path)
    sign = build_project_signs(tmp_path)[0]
    senado = next(c for c in sign["contributions"] if c["agency_name"] == "Senado de Puerto Rico")
    assert {"name": "Thomas Rivera Schatz", "role": "Presidente"} in senado["officials"]
    senador = next(c for c in sign["contributions"] if c["agency_name"] == "Senador de Distrito")
    assert senador["officials"] == []


def test_render_html_contains_fields_and_footer(tmp_path):
    _build_aggregate(tmp_path)
    html = render_sign_html(build_project_signs(tmp_path)[0])
    assert "Pavimentación" in html
    assert "Trujillo Alto" in html
    assert "Senado de Puerto Rico" in html
    assert "$800,000.00" in html
    assert "Thomas Rivera Schatz" in html
    assert "no es un aviso oficial" in html


def test_synthetic_data_renders_ribbon(tmp_path):
    _build_aggregate(tmp_path, synthetic=True)
    html = render_sign_html(build_project_signs(tmp_path)[0])
    assert "SYNTHETIC" in html

    _build_aggregate(tmp_path, synthetic=False)
    html_real = render_sign_html(build_project_signs(tmp_path)[0])
    assert "SYNTHETIC" not in html_real


def test_write_project_signs_emits_files(tmp_path):
    agg = _build_aggregate(tmp_path / "agg")
    out = tmp_path / "signs"
    summary = write_project_signs(agg, out)
    assert summary["count"] == 1
    index = json.loads((out / "index.json").read_text())
    assert index["count"] == 1
    project_id = index["signs"][0]["project_id"]
    assert (out / f"{project_id}.html").exists()


def test_empty_aggregate_returns_no_signs(tmp_path):
    assert build_project_signs(tmp_path) == []


def test_cli_project_signs(tmp_path, capsys):
    agg = _build_aggregate(tmp_path / "agg")
    out = tmp_path / "signs"
    rc = main(["project-signs", "--in", str(agg), "--out", str(out), "--json"])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "wrote 1 project sign(s)" in captured
    assert (out / "index.json").exists()


def test_cli_project_signs_empty_dir_returns_nonzero(tmp_path, capsys):
    rc = main(["project-signs", "--in", str(tmp_path), "--out", str(tmp_path / "signs")])
    assert rc == 1
    assert "no project entities or funding awards" in capsys.readouterr().out


# ── project entities as signs (PPP concessions) ──────────────────────────────

PPP_PROJECT = "ent_bbbbbbbbbbbbbbbbbbbbbbbbbbbb0001"
OBS_1 = "obs_" + "1" * 32


def _ppp_aggregate(tmp_path, *, location=None, observations=None) -> Path:
    """An aggregate shaped like moneysweep-pr's: a project entity, no awards."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    project = _entity(PPP_PROJECT, "Luis Munoz Marin Airport", "project", synthetic=False)
    if location is not None:
        project["location"] = location
    _write_jsonl(tmp_path / "entities.jsonl", [project])
    if observations:
        _write_jsonl(tmp_path / "observations.jsonl", observations)
    return tmp_path


def _observation(target, location, confidence):
    return {
        "observation_id": OBS_1, "source_id": SRC, "entity_id": target,
        "observation_type": "ppp_asset_location", "observed_at": _TS,
        "location": location, "attributes": {"producer_entity_id": target},
        "confidence": confidence, "lineage": _LINEAGE, "synthetic": False,
        "created_at": _TS, "extracted_at": _TS,
    }


def test_project_entity_without_awards_still_gets_a_sign(tmp_path):
    """A PPP concession arrives as an entity, never as an award.

    Before this, such a project could not produce a sign no matter how complete
    its data was.
    """
    agg = _ppp_aggregate(tmp_path, location={"municipality": "Carolina"})
    signs = build_project_signs(agg)
    assert len(signs) == 1
    assert signs[0]["title"] == "Luis Munoz Marin Airport"
    assert signs[0]["location"] == "Carolina"
    assert signs[0]["contributions"] == []
    assert signs[0]["total_amount"] == 0.0


def test_project_entity_with_no_location_still_gets_a_sign(tmp_path):
    """Island-wide concessions federate no location; they are still projects."""
    agg = _ppp_aggregate(tmp_path)
    signs = build_project_signs(agg)
    assert len(signs) == 1
    assert signs[0]["location"] == ""


def test_resolved_geometry_outranks_the_producer_municipality(tmp_path):
    """A spatial producer's surveyed point wins over an administrative record."""
    agg = _ppp_aggregate(
        tmp_path,
        location={"municipality": "San Juan"},
        observations=[_observation(
            PPP_PROJECT, {"lat": 18.4394, "lon": -66.0018, "municipality": "Carolina"}, 0.95
        )],
    )
    signs = build_project_signs(agg)
    assert signs[0]["location"] == "Carolina"


def test_highest_confidence_observation_wins(tmp_path):
    low = _observation(PPP_PROJECT, {"lat": 18.0, "lon": -66.0, "municipality": "Ponce"}, 0.4)
    high = dict(_observation(
        PPP_PROJECT, {"lat": 18.4394, "lon": -66.0018, "municipality": "Carolina"}, 0.95
    ), observation_id="obs_" + "2" * 32)
    agg = _ppp_aggregate(tmp_path, location={"municipality": "San Juan"},
                         observations=[low, high])
    assert build_project_signs(agg)[0]["location"] == "Carolina"


def test_project_that_is_an_award_recipient_is_not_duplicated(tmp_path):
    """The award group already covers it; a second sign would double it."""
    agg = _build_aggregate(tmp_path / "agg")
    signs = build_project_signs(agg)
    assert len(signs) == 1
    assert len(signs[0]["contributions"]) == 2
