#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None, check: bool = True):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(cmd, cwd=cwd, env=merged, text=True, capture_output=True, check=check)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--centinelas", type=Path, required=True)
    parser.add_argument("--moneysweep", type=Path, required=True)
    parser.add_argument("--spiderweb", type=Path, required=True)
    parser.add_argument("--hub", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cent = args.centinelas.resolve()
    money = args.moneysweep.resolve()
    spider = args.spiderweb.resolve()
    hub = args.hub.resolve()
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    # Import exact Centinelas branch implementation.
    sys.path.insert(0, str(cent / "src"))
    from centinelas.classify.labels import DomainLabel, HUB_REPO
    from centinelas.models import ClassifiedItem
    from centinelas.project_leads import project_lead_id, qualifies_project_lead
    from centinelas.route.router import resolve_targets, route

    item = ClassifiedItem(
        item_id="los-rosales-observed-banner",
        source_url="https://example.com/los-rosales-observed-banner",
        source_name="Branch Canary",
        title="Programa de reparaciones y recuperación - Residencial Los Rosales",
        body_text="Contrato 2025-000139; FEMA 4339; PW 9663; inversion $56,432.84; Trujillo Alto, PR",
        published_at=datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc),
        captured_at=datetime(2026, 8, 17, 12, 1, tzinfo=timezone.utc),
        labels=[DomainLabel.FINANCIAL],
        confidence=0.95,
        classifier_reasoning="branch-isolated regression",
        municipalities=["Trujillo Alto"],
        recipients=["Residencial Los Rosales"],
        agencies=["Administracion de Vivienda Publica"],
        estimated_value=56432.84,
        signal_stage="announced",
        beat="housing_recovery",
    )
    assert qualifies_project_lead(item)
    assert resolve_targets(item) == ["moneysweep-pr", "spiderweb-pr"]
    payloads = route(item)
    lead_id = project_lead_id(item)
    for repo in ("moneysweep-pr", "spiderweb-pr", HUB_REPO):
        assert payloads[repo]["project_lead"]["lead_id"] == lead_id
        assert payloads[repo]["project_lead"]["identity_effect"] == "NONE"

    # MoneySweep: write exact routed payload and run its branch intake executable.
    money_intake = money / ".canary_intake"
    money_out = money / ".canary_out"
    money_intake.mkdir(exist_ok=True)
    (money_intake / "los-rosales-observed-banner.json").write_text(
        json.dumps(payloads["moneysweep-pr"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    money_proc = run(
        [sys.executable, "scripts/ingest_centinelas_signals.py", "--intake-dir", str(money_intake), "--output-dir", str(money_out)],
        cwd=money,
    )
    fiscal_path = money_out / "project_fiscal_assertions.jsonl"
    fiscals = read_jsonl(fiscal_path)
    fiscal = next(row for row in fiscals if row["lead_id"] == lead_id)
    assert fiscal["binding_state"] == "UNRESOLVED"
    assert fiscal["identity_effect"] == "NONE"
    assert fiscal["candidate_count"] == fiscal["unresolved_cardinality"]

    # Centinelas handoff adapter: conform to exact SpiderWeb contract.
    sys.path.insert(0, str(cent / "scripts"))
    emit = load_module("cent_project_emit", cent / "scripts" / "emit_project_lead_dispatches.py")
    handoff = emit.build_project_handoff(item.item_id, payloads["spiderweb-pr"])
    client_payload = handoff["client_payload"]
    assert handoff["event_type"] == "centinelas-handoff"
    assert client_payload["lead_id"] == lead_id

    # SpiderWeb: exact ingest, exact replay, fork rejection, then physical assertion export.
    receipt_dir = spider / "data" / "centinelas_handoffs"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    env = {
        "CENTINELAS_CLIENT_PAYLOAD": json.dumps(client_payload, sort_keys=True),
        "EXPECTED_TARGET": "spiderweb-pr",
    }
    first = run([sys.executable, "scripts/ingest_centinelas_handoff.py"], cwd=spider, env=env)
    receipt_key = hashlib.sha256(client_payload["idempotency_key"].encode()).hexdigest()
    receipt_path = receipt_dir / f"{receipt_key}.json"
    first_receipt_hash = sha256_file(receipt_path)

    replay = run([sys.executable, "scripts/ingest_centinelas_handoff.py"], cwd=spider, env=env)
    replay_receipt_hash = sha256_file(receipt_path)
    assert first_receipt_hash == replay_receipt_hash

    fork_payload = deepcopy(client_payload)
    fork_payload["signal"] = deepcopy(client_payload["signal"])
    fork_payload["signal"]["title"] = "CHANGED PAYLOAD UNDER SAME IDEMPOTENCY KEY"
    fork = run(
        [sys.executable, "scripts/ingest_centinelas_handoff.py"],
        cwd=spider,
        env={
            "CENTINELAS_CLIENT_PAYLOAD": json.dumps(fork_payload, sort_keys=True),
            "EXPECTED_TARGET": "spiderweb-pr",
        },
        check=False,
    )
    assert fork.returncode != 0
    collision_path = receipt_path.with_suffix(".collision.json")
    assert collision_path.exists()
    assert sha256_file(receipt_path) == first_receipt_hash

    physical_proc = run([sys.executable, "scripts/build_project_physical_assertions.py"], cwd=spider)
    physical_path = spider / "exports" / "federation" / "project_physical_assertions.jsonl"
    physicals = read_jsonl(physical_path)
    physical = next(row for row in physicals if row["lead_id"] == lead_id)
    assert physical["binding_state"] == "UNRESOLVED"
    assert physical["identity_effect"] == "NONE"
    assert physical["candidate_count"] == physical["unresolved_cardinality"]

    # TheHub: negative real fixture then independently authoritative positive control.
    sys.path.insert(0, str(hub / "src"))
    from hub.project_leads import adjudicate_project

    lead = payloads[HUB_REPO]["project_lead"]
    negative = adjudicate_project(lead, [fiscal], [physical])
    assert negative["state"] == "CROSS_DOMAIN_CANDIDATE"
    assert negative["identity_effect"] == "NONE"
    assert negative["banner"] is None

    binding = {
        "evidence_type": "stable_project_id",
        "value": "AUTH-LOS-ROSALES-2025-000139",
        "authoritative": True,
        "identity_effect": "BINDING",
    }
    fiscal_positive = deepcopy(fiscal)
    physical_positive = deepcopy(physical)
    fiscal_positive["independent_binding_evidence"] = [binding]
    physical_positive["independent_binding_evidence"] = [binding]
    positive = adjudicate_project(lead, [fiscal_positive], [physical_positive])
    assert positive["state"] == "BANNER_ELIGIBLE"
    assert positive["identity_effect"] == "BINDING"
    assert positive["banner"]["schema"] == "project_banner/v1"
    assert positive["banner"]["certification_state"] == "PASS"

    receipt = {
        "schema": "project_lead_branch_canary/v1",
        "certification": "PASS",
        "scope": "four_unmerged_feature_branches_only",
        "merge_or_production_promotion": False,
        "lead_id": lead_id,
        "branch_heads": {
            "centinelas-pr": git_head(cent),
            "moneysweep-pr": git_head(money),
            "spiderweb-pr": git_head(spider),
            "thehub-pr": git_head(hub),
        },
        "los_rosales": {
            "state": negative["state"],
            "identity_effect": negative["identity_effect"],
            "banner": negative["banner"],
            "fiscal_candidate_count": fiscal["candidate_count"],
            "physical_candidate_count": physical["candidate_count"],
        },
        "positive_control": {
            "state": positive["state"],
            "banner_schema": positive["banner"]["schema"],
            "banner_id": positive["banner"]["banner_id"],
            "binding": positive["banner"]["binding"],
        },
        "replay_fork": {
            "first_exit": first.returncode,
            "replay_exit": replay.returncode,
            "fork_exit": fork.returncode,
            "receipt_sha256_first": first_receipt_hash,
            "receipt_sha256_replay": replay_receipt_hash,
            "collision_sha256": sha256_file(collision_path),
        },
        "artifacts": {
            "moneysweep_fiscal_assertions_sha256": sha256_file(fiscal_path),
            "spiderweb_physical_assertions_sha256": sha256_file(physical_path),
            "spiderweb_receipt_sha256": sha256_file(receipt_path),
        },
        "subprocess_stdout": {
            "moneysweep": money_proc.stdout[-4000:],
            "spiderweb_first": first.stdout[-2000:],
            "spiderweb_replay": replay.stdout[-2000:],
            "spiderweb_physical": physical_proc.stdout[-2000:],
        },
    }
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
