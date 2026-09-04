# Canon v1 post-merge human review

## Namespace Authority

**Finding:** The `prii.dev` IRIs in the baseline are provisional because domain control was not independently verified.

**Canon v1 rule:** CURIE identifiers (`prii:`, contract and repo prefixes) are canonical identity keys. Expanded `https://prii.dev/...` IRIs are serialization aliases until a domain-control attestation exists.

**Disposition:** `hardened`

## Exclusion Rules

**Finding:** Baseline 100% means 4,692/4,692 eligible tracked files; 580 tracked files were excluded by suffix, lock/generated policy, or size.

**Canon v1 rule:** Coverage MUST state eligible-file coverage separately from tracked-file coverage and preserve the exclusion ledger. Excluded files are not semantically inspected.

**Disposition:** `hardened`

## Parser Fallback

**Finding:** Two eligible files required lexical fallback and still counted as scanned.

**Canon v1 rule:** Fallback observations are inventory-only T2 evidence and cannot directly support canonicalization. Release verification reports fallback separately.

**Disposition:** `hardened`

## CI Permissions

Ontology CI uses least-privilege `contents: read` and commit-pinned actions. Canon v1 retains that boundary.

**Disposition:** `accepted`

## Generated Artifacts

Normative adjudication rules, expected counts/digests, scale and priority decisions, term-record digests, adapters and deprecations are committed. Raw ledgers and expanded homonym/synonym/authority mappings remain reproducible CI/release artifacts referenced by digest.

**Disposition:** `accepted`
