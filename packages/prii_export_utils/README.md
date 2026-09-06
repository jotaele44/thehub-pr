# prii-export-utils

Shared deterministic export and local artifact-transport helpers for the PRII
Federation. The package has no runtime dependency outside the Python standard
library and performs no network access.

## Export identity helpers

`fid(prefix, *parts)`, `norm(name)`, and `sha256(path)` were extracted from the
near-identical helpers duplicated across `aguayluz-pr`, `spiderweb-pr`,
`ovnis-pr`, `skywatcher-pr`, and `centinelas-pr`.

Everything else in each producer's `federation_export.py` remains local.
`_lineage` has incompatible call signatures across repositories and
`write_package` has material per-repository differences, so neither is
artificially normalized here.

Existing producers may retain their private aliases:

```python
from prii_export_utils import fid as _fid, norm as _norm, sha256 as _sha256
```

`moneysweep-pr`'s `federation_export.py` remains a distinct bridge around
`moneysweep.federation.canonical_v1_bridge` with its own serialization
contract.

## Local artifact transport

`artifact_transport.py` supplies the provider-independent Federation transport
primitive. It does not call GitHub, a hosted queue, a database, or a cloud
service.

The authoritative directory contract is:

```text
<exchange-root>/
  outbox/<target>/<message-id>.json
  inbox/<target>/<message-id>.json
  receipts/<target>/<message-id>.json
```

A producer calls `emit_message()`. A local operator, removable-media process,
filesystem synchronizer, or optional hosted bridge calls `deliver_message()`.
The consumer reads whole validated records with `iter_inbox()` and writes an
immutable receipt with `acknowledge_message()` only after committing its own
result.

```python
from prii_export_utils import (
    acknowledge_message,
    deliver_message,
    emit_message,
    iter_inbox,
)

emitted = emit_message(
    "/srv/federation-exchange",
    source="centinelas-pr",
    target="moneysweep-pr",
    kind="signal",
    idempotency_key="source-event-17",
    payload={"records": [{"id": "17"}]},
)

deliver_message("/srv/federation-exchange", emitted.path)

for path, envelope in iter_inbox("/srv/federation-exchange", "moneysweep-pr"):
    # Commit the payload to the consumer's local authority first.
    acknowledge_message(
        "/srv/federation-exchange",
        target="moneysweep-pr",
        message_id=envelope["message_id"],
        consumer="moneysweep-pr",
    )
```

### Transport invariants

- Message IDs derive from canonical source, target, kind, idempotency key, and
  payload SHA-256; timestamps and filenames do not establish identity.
- JSON is serialized canonically with non-finite numbers rejected.
- Writes use a same-directory temporary file, `fsync`, and atomic `os.replace`.
- Duplicate emissions, deliveries, and acknowledgements are deterministic.
- A reused message ID bound to conflicting content fails closed.
- Unknown envelope fields, invalid path components, and payload tampering fail
  validation.
- Messages remain whole records; the transport does not aggregate payload rows.
- GitHub `repository_dispatch` may wrap this protocol, but cannot replace the
  local outbox/inbox as authoritative transport.

## Optional exact-byte mirrors

`artifact_mirror.py` wraps one committed canonical outbox file for optional
hosted delivery. It embeds the complete envelope bytes as base64 and binds them
to independent byte-size and SHA-256 observations.

```python
from prii_export_utils import build_mirror_payload, verify_mirror_payload

mirror = build_mirror_payload(emitted.path)
envelope, exact_bytes = verify_mirror_payload(mirror)
```

The wrapper fails closed on malformed base64, byte-size or hash drift,
duplicate JSON keys, noncanonical serialization, and any mismatch between its
source, target, kind, or message identity and the embedded envelope.

A hosted bridge must be downstream of `emit_message()`. A hosted delivery ID,
HTTP status, or workflow run is not authoritative identity and cannot replace a
local receipt. The receiver must verify the wrapper before reconstructing the
exact envelope file.

Cross-language contracts are published at:

- `schemas/contracts/federation_artifact_message.v1.schema.json`
- `schemas/contracts/federation_artifact_receipt.v1.schema.json`
- `schemas/contracts/federation_artifact_mirror.v1.schema.json`

## Installing from an immutable source

```bash
pip install "prii-export-utils @ git+https://github.com/jotaele44/thehub-pr.git@<reviewed-commit>#subdirectory=packages/prii_export_utils"
```

The Federation's older `f2b8176...` pins predate the local transport and mirror
APIs. Downstream repositories must pin an exact reviewed implementation commit.
For disconnected builds, retaining only a Git SHA is insufficient: the source
archive or wheel bytes, SHA-256, license material, and manifest must also be
stored locally.

## Pinning policy

Pin to an exact reviewed commit SHA or package release, never to `main`.
Dependency-byte retention is separate from source identity: a stable Git name
or commit does not by itself make a disconnected rebuild possible.

The pin lives in each producer's primary install manifest. Hosted package
retrieval is an acquisition convenience, not runtime or transport authority.
