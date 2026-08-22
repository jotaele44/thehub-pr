# PRII Federation Ontology

This directory is the governed semantic control surface for the seven-repository PRII federation.

## Normative inputs

- `CHARTER.md` — scope, authority, ownership, lifecycle, and breaking-change rules.
- `NAMESPACES.yaml` — stable compact identifiers and namespace IRIs.
- `repository-pins.json` — immutable source snapshot used for the current concordance.
- `schemas/` — term, raw-observation, and competency-question contracts.
- `core/` — minimal federation core.
- `modules/` — bounded repository modules.
- `resolutions/` — adjudicated priority term families.
- `mappings/` — legacy and projection mappings.
- `competency/` — executable semantic questions and fixtures.

## Generated outputs

`generated/` is produced by the read-only extractor and analyzer:

- `raw-term-ledger.jsonl`
- `coverage.json`
- `deduplicated-observations.jsonl`
- `synonym-candidates.json`
- `homonym-conflicts.json`
- `scale-conflicts.json`
- `identity-conflicts.json`
- `cardinality-conflicts.json`
- `lifecycle-conflicts.json`
- `authority-conflicts.json`
- `priority-resolution-status.json`
- `summary.json`

Generated outputs are deterministic for the same seven commit pins and extractor version. Discovery never performs semantic merging.

## Commands

```bash
python tools/ontology/extract_terms.py \
  --workspace ../federation-pins \
  --pins federation/ontology/repository-pins.json \
  --out federation/ontology/generated

python tools/ontology/analyze_terms.py \
  --ledger federation/ontology/generated/raw-term-ledger.jsonl \
  --resolutions federation/ontology/resolutions/priority-term-families.yaml \
  --out federation/ontology/generated

python tools/ontology/validate_canon.py --root . --require-generated
```

The pull-request gate may open only after all seven repositories report 100% eligible-file coverage and every high-severity priority conflict has an owner and disposition.
