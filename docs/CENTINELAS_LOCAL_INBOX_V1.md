# Centinelas local-envelope ingestion — TheHub v1

## Exact topology

```text
TheHub #246  audit/federation-freedom-v1
└── TheHub #260  remediate/local-authority-v1
    └── this consumer branch  consume/centinelas-local-inbox-v1

TheHub #247  audit/completion-gate-v3-20260904
└── independent completion-contract audit; not a stack parent

Centinelas #125  remediate/local-authority-v1
└── exact producer snapshot bound by this consumer manifest
```

The earlier labels “#247 implementation parent” and “Centinelas #126 producer
migration” are **SUPERSEDED** by live repository identity. PR identity is the
repository, number, head ref, and head SHA together; number-only matching is not
identity evidence.

## Authority boundary

TheHub accepts only a complete canonical `prii.artifact-message.v1` envelope
whose independent bindings all agree:

- source: `centinelas-pr`
- target: `thehub-pr`
- kind: `centinelas-signal`
- filename: `<message_id>.json`
- payload SHA-256: equal to the canonical payload bytes
- message ID: equal to the canonical identity document

The payload is not parsed before the complete envelope and route bindings pass.
The accepted record preserves the validated whole envelope. This PR does not
project the payload into a domain corpus, infer entity identity, or create a
cross-repository match.

## Restartable commit order

```text
validate exact bytes
→ deliver exact envelope to inbox/thehub-pr
→ commit immutable whole-envelope ACCEPTED record
→ commit immutable PROCESSED receipt
→ write transport acknowledgement
```

A failure after a durable step is safe to replay. Exact replay is `DUPLICATE`.
Different bytes under an existing message or intake-record identity fail closed.
Invalid files and unexpected directory residue receive immutable `REJECTED`
records. Local write, collision, or transport faults receive separate immutable
`FAILED` records rather than being mislabeled as invalid input. Batch arithmetic
must satisfy:

```text
discovered = PROCESSED + DUPLICATE + VALIDATED + REJECTED + FAILED
```

## CLI

```bash
hub-local-inbox \
  --exchange-root .federation/exchange \
  --source-dir .federation/exchange/outbox/thehub-pr \
  --state-root data/local_inbox \
  --source centinelas-pr \
  --kind centinelas-signal \
  --json
```

Use `--dry-run` to validate and classify without writing inbox records,
acceptance records, processing receipts, transport acknowledgements, or
rejection/failure dispositions.

## Packaging boundary

The consumer loads the exact `prii_export_utils` implementation already
carried by TheHub #260. Before import, it verifies the complete four-member Python
source set and each member's Git blob identity:

```text
__init__.py            8e22ab3332d266259e211b55b5fb3a6bd55c8d7d
artifact_mirror.py     25d36d61fa393ac1236a1f2d46499b96aeb8dc13
artifact_transport.py  45043023bbcd34e214256a4f71b28b0765cc74ab
helpers.py             1f15f759fd30b7443d1281d47ebf75f757f1c0c4
```

A complete source checkout is authoritative and cannot be shadowed by an
unrelated installed package. A packaged deployment may use a separately
installed distribution only when those same four source members and identities
are present. Missing, extra, symlinked, or byte-different members fail closed.

The root Hub distribution is not widened with a Python 3.10+ package, so
unrelated Hub commands retain the existing Python 3.9 compatibility floor.
Local-envelope execution itself requires Python 3.10+.

This four-source-member binding is not whole-wheel identity, retained dependency-
byte completeness, or proof of a disconnected rebuild.

## Gate crosswalk

PR #246 retains ten policy gates. Federation execution reporting uses eight
composite dynamic gates without weakening that denominator: the first composite
gate contains policy gates 1–3, and gates 2–8 correspond to policy gates 4–10.
All ten policy requirements must therefore pass before the eight composite gates
can all close.

## Certification boundary

This ingestion change proves only bounded local envelope validation, delivery,
record conservation, rejection classification, replay behavior, and receipt
binding. It does not prove service independence, a self-contained release, or an
offline reproducible build. Certification remains `PROVISIONAL`, with `0/8`
composite dynamic gates closed.
