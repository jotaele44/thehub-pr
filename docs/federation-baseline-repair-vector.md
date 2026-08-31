# Federation baseline repair vector

This branch is intentionally separate from HTR v2 implementation. It must not change HTR frozen source artifacts, candidate arithmetic, identity semantics, connectivity semantics, or HTR consumer contracts.

Tracking issue: #226.

## Current bounded blockers

- TheHub federation snapshot governance: frozen producer SHAs differ from mutable `main` heads; repair must version/reconcile snapshot authority rather than silently rebinding frozen evidence.
- Skywatcher lint: `scripts/build_producer_package.py` SIM118 and `tests/test_fr24_source_drop_loader.py` I001/F401.
- Skywatcher launcher/template drift: `PRII-SKYWATCHER.command`, `PRII-SKYWATCHER.sh`.
- Spiderweb launcher/template drift: `PRII-SPIDERWEB.command`, `PRII-SPIDERWEB.sh`.

## Hard invariants

- HTR legacy 1,513 result remains `SUPERSEDED_NONREPRODUCIBLE`.
- HTR v2 arithmetic remains `5,569 = 3,831 UNSUPPORTED + 1,738 CANDIDATE_NOT_IDENTITY/UNRESOLVED`.
- No name/fuzzy/proximity/cluster promotion to identity or connectivity.
- No transitive context inheritance.
- Preserve enriched launcher behavior before deciding whether canonical templates or consuming launchers are authoritative.
- Keep before/after exact SHAs and workflow receipts.
- Do not merge HTR PRs through this vector.
