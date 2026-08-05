# Federation Manager foundation security review v0.3

## Implemented controls

- Loopback-only API enforcement
- Exact origin allow-list with no wildcard
- Opaque short-lived sessions bound to browser origin
- Native bootstrap nonce comparison using constant-time digest comparison
- Declarative JSON Schema validation
- Format-checked timestamps and artifact URIs
- Exactly-one native app identity and ID/display-name pairing
- Recursive rejection of executable manifest fields
- Recursive technical-details redaction
- Secret-provider interface without secret retrieval
- Read-only inventory routes

## Intentionally absent

- Artifact download or extraction
- Install, update, rollback, repair, or uninstall execution
- Data deletion
- Process launch
- Shell or arbitrary-command execution
- GitHub release writes
- Producer mutations

## Residual risks for later phases

- Native nonce delivery and storage require platform-specific implementation.
- OS credential providers require platform certification.
- Signed catalog verification is schema-defined but cryptographic verification
  is not part of this foundation.
- Local process supervision and atomic rollback require separate threat modeling.

No Phase 2 lifecycle operation should be enabled until the corresponding
release-blocking gates have executable tests.
