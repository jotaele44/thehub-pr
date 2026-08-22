#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python -m federation_audit.cli validate-manifest "$ROOT/manifests/federation.json" --schema "$ROOT/contracts/repository-audit-manifest.schema.json"
python -m federation_audit.cli fixture-audit --output "$ROOT/evidence/first-controlled-audit.json"
pytest "$ROOT/tests"
