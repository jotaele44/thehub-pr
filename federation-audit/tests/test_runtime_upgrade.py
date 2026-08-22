from pathlib import Path

from federation_audit.calibration import run_calibration
from federation_audit.classifier import classify_observations
from federation_audit.runtime_cert import Probe, validate_topology


def test_static_declaration_cannot_self_promote():
    classification, _, _, _ = classify_observations(
        {
            "handler_bound": True,
            "handler_resolved": True,
            "intent_observed": True,
            "boundary_reached": True,
            "contract_matched": True,
        }
    )
    assert classification.value == "PARTIALLY_WIRED"


def test_contract_promotion_requires_resolver_receipt():
    classification, _, _, _ = classify_observations(
        {
            "handler_bound": True,
            "handler_resolved": True,
            "intent_observed": True,
            "boundary_reached": True,
            "contract_matched": True,
            "target_resolution_evidence": True,
        }
    )
    assert classification.value == "EXECUTABLE_BY_CONTRACT"


def test_runtime_confirmation_requires_isolation_and_t2():
    classification, _, _, _ = classify_observations(
        {
            "terminal_observed": True,
            "side_effect_intercepted": True,
            "runtime_isolated": True,
            "t2_receipt": True,
        }
    )
    assert classification.value == "EXECUTABLE_CONFIRMED"


def test_adversarial_calibration_has_no_known_fp_or_fn():
    result = run_calibration()
    assert result["passed"] is True, result
    assert result["true_positive"] >= 2
    assert result["true_negative"] >= 3
    assert result["false_positive"] == 0
    assert result["false_negative"] == 0
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0


def test_topology_must_bind_to_declared_command():
    manifest = {
        "repositories": [
            {
                "workspace_directory": "repo",
                "entry_points": [{"kind": "cli", "path": "cli.py", "command": "tool"}],
            }
        ]
    }
    valid = Probe.from_dict(
        {
            "probe_id": "valid",
            "repository": "repo",
            "surface_kind": "cli",
            "entry_point": "cli.py",
            "command": ["tool", "--help"],
            "mode": "command",
            "minimum_gate": "G4",
        }
    )
    assert validate_topology(manifest, [valid]) == []

    invalid = Probe.from_dict(
        {
            "probe_id": "invalid",
            "repository": "repo",
            "surface_kind": "cli",
            "entry_point": "cli.py",
            "command": ["python", "-c", "print('fake')"],
            "mode": "command",
        }
    )
    failures = validate_topology(manifest, [invalid])
    assert "probe-command-not-declared-prefix:invalid" in failures
