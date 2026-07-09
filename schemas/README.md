# Frozen contract schemas

These schemas are the **frozen engine/product boundary** ratified by
[ADR 0001](../docs/adr/0001-federated-engines-single-hub.md) (Phase 0): the six
producer repos export against them, and the Hub validates and aggregates
against them. Changing any file here is a **deliberate, versioned event**, not
a routine edit.

`FROZEN.sha256` records the SHA-256 of every schema in this directory, and
`tests/test_schema_freeze.py` fails if a schema no longer matches its recorded
hash (or is added/removed without updating the manifest).

To change a schema deliberately:

1. Make the schema change (bump its `schema_version` const if the change is
   breaking for producers).
2. Regenerate the manifest: `python tests/test_schema_freeze.py --update`.
3. Explain the contract change in the PR description and coordinate the
   producer-side rollout repo-by-repo (never big-bang).
