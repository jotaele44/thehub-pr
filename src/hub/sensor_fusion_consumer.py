"""Consumer pipeline for Skywatcher sensor-fusion analytics exports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "skywatcher_sensor_fusion_analytics.schema.json"


@dataclass(frozen=True)
class SensorFusionConsumerResult:
    valid: bool
    producer: str
    export_contract: str
    anomaly_count: int
    dashboard: str
    guardrails: dict[str, Any]
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "producer": self.producer,
            "export_contract": self.export_contract,
            "anomaly_count": self.anomaly_count,
            "dashboard": self.dashboard,
            "guardrails": self.guardrails,
            "errors": self.errors,
        }


def load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_sensor_fusion_export(payload: Mapping[str, Any], schema_path: Path | str = SCHEMA_PATH) -> list[str]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(payload), key=lambda err: list(err.path))]


def consume_sensor_fusion_export(payload: Mapping[str, Any]) -> SensorFusionConsumerResult:
    errors = validate_sensor_fusion_export(payload)
    guardrails = dict(payload.get("guardrails", {})) if isinstance(payload.get("guardrails", {}), Mapping) else {}
    return SensorFusionConsumerResult(
        valid=not errors,
        producer=str(payload.get("producer", "")),
        export_contract=str(payload.get("export_contract", "")),
        anomaly_count=int(payload.get("anomaly_count", 0)),
        dashboard=str(payload.get("dashboard", "sensor_fusion_context")),
        guardrails=guardrails,
        errors=errors,
    )


def build_dashboard_surface(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a TheHub dashboard surface from a valid Skywatcher export."""

    result = consume_sensor_fusion_export(payload)
    return {
        "surface_id": "skywatcher_sensor_fusion",
        "producer": result.producer,
        "contract": result.export_contract,
        "valid": result.valid,
        "live_tracking": False,
        "operational_cueing": False,
        "operator_action": "review_context_only",
        "metrics": dict(payload.get("metrics", {})) if isinstance(payload.get("metrics", {}), Mapping) else {},
        "review_bands": dict(payload.get("review_bands", {})) if isinstance(payload.get("review_bands", {}), Mapping) else {},
        "anomaly_count": result.anomaly_count,
        "errors": result.errors,
    }


def write_dashboard_surface(input_path: Path | str, output_path: Path | str) -> dict[str, Any]:
    payload = load_json(input_path)
    surface = build_dashboard_surface(payload)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return surface
