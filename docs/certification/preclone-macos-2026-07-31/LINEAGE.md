# Pre-Clone macOS Certification Lineage - 2026-07-31

This directory preserves historical certification evidence from the earlier
pre-clone macOS certification line. The files are evidence artifacts only; they
are not active workflow inputs and do not supersede the current v3 certification
candidate.

## Preserved Evidence

- `SHA256SUMS`: hashes for the original certification evidence bundle.
- `evidence.json`: original evidence payload from the clean macOS run.
- `macos_certification.json`: original certification receipt.

## Archived Head Registries

Historical registry snapshots are archived under
`registry/certification-history/`:

- `preclone-certification-heads-v0-2026-07-31.json`
- `preclone-certification-heads-v1-2026-07-31.json`
- `preclone-certification-heads-v2-2026-07-31.json`

The active August 3 certification candidate remains
`registry/preclone-certification-heads-v3.json`.

## Closure Rationale

PRs #149, #154, and #155 were predecessors of the August 3 v3 certification
candidate. Their reusable lineage is preserved here without reactivating their
older workflow or trigger files.
