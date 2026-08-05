# ADR 0004: Native Federation Manager foundation

Status: Adopted for Phase 1 foundation
Date: 2026-07-26

TheHub remains the single supported product surface. A future constrained
native Federation Manager will perform local lifecycle operations; producer
dashboards remain read-only diagnostic surfaces.

This foundation implements only release-schema validation, the application
state model, OS path resolution, secret-provider interfaces, authenticated
loopback inventory APIs, and read-only App Center tiles.

It explicitly excludes downloads, installation, updates, uninstall, data
deletion, process launch, release mutation, and shell execution.

Security invariants:

1. Release manifests are declarative and reject command, shell, script,
   executable, and `hub_callable_commands` fields at every nesting level.
2. Manager APIs accept loopback clients only.
3. Sessions originate from a native bootstrap nonce, expire after five minutes,
   and are bound to an allow-listed origin.
4. Secrets use an interface that never exposes a read-value method.
5. Technical details recursively redact credential-bearing keys.
6. Install, configuration, data, federation, and production readiness remain
   independent.

The Phase 1 UI is deliberately non-mutating. It demonstrates the seven native
app names and identities while the lifecycle actions remain unavailable until
their security and rollback gates are implemented.
