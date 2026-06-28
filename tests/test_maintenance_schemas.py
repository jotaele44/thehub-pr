"""Schema tests for the maintenance finding/report/rollup contracts."""
import jsonschema
import pytest

from hub._schemas import load_schema
from hub.maintenance.rollup import validate_report


def _finding_validator():
    return jsonschema.Draft7Validator(load_schema("maintenance_finding.schema.json"))


def _rollup_validator():
    return jsonschema.Draft7Validator(load_schema("maintenance_rollup.schema.json"))


VALID_FINDING = {
    "finding_id": "aguayluz-pr:manifest:0001",
    "repo": "aguayluz-pr",
    "category": "manifest",
    "severity": "warning",
    "action": "none",
    "confidence": 1.0,
}

VALID_REPORT = {
    "repo": "aguayluz-pr",
    "maintenance_version": "0.1.0",
    "mode": "audit",
    "generated_at": "2026-01-01T00:00:00Z",
    "findings_count": 1,
    "critical_count": 0,
    "promotion_blocked": False,
    "findings": [VALID_FINDING],
}


def test_valid_finding_passes():
    assert list(_finding_validator().iter_errors(VALID_FINDING)) == []


@pytest.mark.parametrize("field,bad", [
    ("category", "not_a_category"),
    ("severity", "fatal"),
    ("action", "deleted"),
])
def test_bad_enum_fails(field, bad):
    finding = {**VALID_FINDING, field: bad}
    assert list(_finding_validator().iter_errors(finding)), f"{field}={bad} should fail"


def test_confidence_out_of_range_fails():
    assert list(_finding_validator().iter_errors({**VALID_FINDING, "confidence": 1.5}))


def test_valid_report_passes():
    assert validate_report(VALID_REPORT) == []


def test_report_with_bad_nested_finding_fails():
    bad = {**VALID_REPORT, "findings": [{**VALID_FINDING, "severity": "fatal"}]}
    assert validate_report(bad)


def test_report_missing_required_field_fails():
    bad = {k: v for k, v in VALID_REPORT.items() if k != "promotion_blocked"}
    assert validate_report(bad)


def test_rollup_shape_validates():
    rollup = {
        "producer_count": 1,
        "reports_missing": 0,
        "promotion_blocked": False,
        "repo_status": {
            "aguayluz-pr": {"report_present": True, "report_valid": True}
        },
    }
    assert list(_rollup_validator().iter_errors(rollup)) == []
