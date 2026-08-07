from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .strict_scan import strict_scan_federation

POSITIVE = "EXECUTABLE_BY_CONTRACT"


def _write_fixture(root: Path) -> dict[str, str]:
    repo = root / "calibration"
    (repo / "api").mkdir(parents=True)
    (repo / "web").mkdir()
    (repo / ".github" / "workflows").mkdir(parents=True)

    (repo / "api" / "app.py").write_text(
        "from fastapi import APIRouter, FastAPI\n"
        "app = FastAPI()\n"
        "router = APIRouter(prefix='/assets')\n"
        "@router.post('/export')\n"
        "def export_asset(): return {'accepted': True}\n"
        "app.include_router(router, prefix='/api/v1')\n",
        encoding="utf-8",
    )
    (repo / "web" / "handlers.js").write_text(
        "export function importedExport() { fetch('/api/v1/assets/export', {method: 'POST'}); }\n",
        encoding="utf-8",
    )
    (repo / "web" / "unrelated.js").write_text(
        "export function duplicateName() { return 'unreachable'; }\n",
        encoding="utf-8",
    )
    (repo / "web" / "other.js").write_text(
        "export function duplicateName() { return 'also-unreachable'; }\n",
        encoding="utf-8",
    )
    (repo / "web" / "App.jsx").write_text(
        "import { importedExport } from './handlers.js';\n"
        "export function App() {\n"
        " const localExport = () => { fetch('/api/v1/assets/export', {method: 'POST'}); };\n"
        " const wrongMethod = () => { fetch('/api/v1/assets/export', {method: 'GET'}); };\n"
        " const dynamicUrl = '/api/v1/assets/export';\n"
        " const dynamic = () => { fetch(dynamicUrl, {method: 'POST'}); };\n"
        " return <div>\n"
        "  <button onClick={localExport}>Local Positive</button>\n"
        "  <button onClick={importedExport}>Imported Positive</button>\n"
        "  <button onClick={wrongMethod}>Wrong Method</button>\n"
        "  <button onClick={dynamic}>Dynamic URL</button>\n"
        "  <button onClick={duplicateName}>Duplicate Unimported</button>\n"
        " </div>;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo / "package.json").write_text(
        '{"scripts":{"phantom":"binary-that-does-not-exist --flag"}}\n', encoding="utf-8"
    )
    (repo / ".github" / "workflows" / "ci.yml").write_text(
        "name: calibration\non: push\njobs:\n  declared:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo declared\n",
        encoding="utf-8",
    )
    return {
        "Local Positive": POSITIVE,
        "Imported Positive": POSITIVE,
        "Wrong Method": "CONTRACT_MISMATCH",
        "Dynamic URL": "PARTIALLY_WIRED",
        "Duplicate Unimported": "TARGET_MISSING",
    }


def run_calibration() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="federation-audit-calibration-") as temp:
        root = Path(temp)
        expected = _write_fixture(root)
        manifest = {
            "repositories": [
                {
                    "id": "calibration",
                    "repository": "fixture/calibration",
                    "commit": "a" * 40,
                    "workspace_directory": "calibration",
                }
            ]
        }
        result = strict_scan_federation(root, manifest)
        by_label = {
            item["surface"]["label"]: item["classification"]
            for item in result["traces"]
            if item["surface"]["kind"] == "gui-control"
        }
        tp = fp = fn = tn = 0
        cases: list[dict[str, str | bool]] = []
        for label, expected_class in expected.items():
            actual = by_label.get(label, "MISSING_FROM_SCAN")
            expected_positive = expected_class == POSITIVE
            actual_positive = actual == POSITIVE
            if expected_positive and actual_positive:
                tp += 1
            elif not expected_positive and actual_positive:
                fp += 1
            elif expected_positive and not actual_positive:
                fn += 1
            else:
                tn += 1
            cases.append(
                {
                    "label": label,
                    "expected": expected_class,
                    "actual": actual,
                    "passed": actual == expected_class,
                }
            )

        # Bare declarations are explicit negative controls.
        declaration_violations = [
            item
            for item in result["traces"]
            if item["surface"]["kind"] in {"route", "command", "workflow-stage"}
            and item["classification"] == POSITIVE
        ]
        fp += len(declaration_violations)

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        passed = all(bool(case["passed"]) for case in cases) and not declaration_violations and fp == 0 and fn == 0
        return {
            "true_positive": tp,
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "cases": cases,
            "declaration_promotion_violations": len(declaration_violations),
            "passed": passed,
        }
