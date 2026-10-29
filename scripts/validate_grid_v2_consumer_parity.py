"""Read-only, fail-closed Federation V2 consumer-pin parity checker."""
import argparse
import json
from pathlib import Path

EXPECTED = {
    "aguayluz-pr": "L1",
    "skywatcher-pr": "L2",
    "ovnis-pr": "L1",
    "moneysweep-pr": "L1",
    "centinelas-pr": "L0",
    "thehub-pr": "L1",
}
FIELDS = ("grid_id", "grid_version", "crs", "grid_manifest_sha256",
          "cell_schema_sha256", "binding_schema_sha256", "mask_schema_sha256",
          "authority_commit", "authority_repository")


def validate(pins):
    errors = []
    if set(pins) != set(EXPECTED):
        errors.append("consumer denominator mismatch")
    if not pins:
        return errors
    reference = next(iter(pins.values()))
    for repo, pin in pins.items():
        for field in FIELDS:
            if not pin.get(field) or pin.get(field) != reference.get(field):
                errors.append(f"{repo}: {field} differs or is absent")
        if pin.get("consumer") != repo:
            errors.append(f"{repo}: consumer identity mismatch")
        if pin.get("default_level") != EXPECTED.get(repo):
            errors.append(f"{repo}: unsupported default level")
        if pin.get("default_level") not in pin.get("allowed_levels", []):
            errors.append(f"{repo}: default not allowed")
        if pin.get("geometry_mode") != "REFERENCE_ONLY" or pin.get("local_geometry_copy") is not False:
            errors.append(f"{repo}: geometry authority violation")
        if pin.get("compatibility_policy") != "FAIL_CLOSED":
            errors.append(f"{repo}: fail-closed policy missing")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Directory containing one <repo>.pin.json per consumer")
    args = parser.parse_args()
    pins = {}
    for name in EXPECTED:
        path = args.root / f"{name}.pin.json"
        if path.is_file():
            pins[name] = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(pins)
    print(json.dumps({"status": "FAIL" if errors else "PASS", "consumer_count": len(pins), "errors": errors}, indent=2))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
