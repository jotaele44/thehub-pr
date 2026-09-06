# Federation optional mirror contract v1

## State

- **Authority:** local artifact outbox
- **Hosted bridge:** optional transport manifestation
- **Certification:** `PROVISIONAL`
- **Parent policy:** draft PR #246, `FEDERATION_FREEDOM_CONTRACT_v1`

This contract does not certify any repository and does not authorize replacing a
local outbox with GitHub, another hosted queue, or an account-gated service.

## Required order of operations

A producer using an optional hosted bridge must execute this order:

1. construct the application payload;
2. emit and commit the canonical local artifact envelope;
3. derive the mirror wrapper from the exact committed envelope file;
4. transmit the wrapper only when the hosted bridge is explicitly enabled;
5. retain local success even if hosted transmission is unavailable;
6. require the receiver to decode and verify the embedded envelope bytes before
   application processing;
7. write a local consumer receipt only after the consumer commits its result.

A hosted response code, run identifier, delivery identifier, or acknowledgement
cannot mint or replace `message_id`.

## Exact-byte wrapper

`prii.artifact-mirror.v1` contains:

- canonical message identity;
- source, target, and kind bindings;
- byte length of the complete local envelope file;
- SHA-256 of those bytes;
- base64 representation of those exact bytes.

The receiver fails closed when:

- wrapper fields are missing or extra;
- base64 is malformed;
- size or SHA-256 does not match;
- the decoded envelope is not canonical UTF-8 JSON with one trailing LF;
- duplicate JSON keys are present;
- the embedded envelope fails its own payload and identity checks;
- source, target, kind, or message identity differs between wrapper and envelope.

## Identity boundaries

These are separate manifestations:

```text
LOCAL_ENVELOPE_BYTES
HOSTED_MIRROR_WRAPPER
HOSTED_DELIVERY_RECORD
CONSUMER_INBOX_BYTES
CONSUMER_RECEIPT
```

Only the local envelope content establishes the logical message identity. Exact
wrapper verification can prove that the hosted bridge carried the same envelope
bytes. It cannot prove that the hosted service is independent, durable, complete,
or available without an account.

## Failure behavior

| Observation | Producer result | Hosted result | Certification effect |
|---|---|---|---|
| Local emit succeeds; mirror disabled | Local message committed | Not attempted | No downgrade; still `PROVISIONAL` |
| Local emit succeeds; mirror succeeds | Local message committed | Optional manifestation recorded | No promotion |
| Local emit succeeds; mirror fails | Local message committed | Failure preserved | No loss of local authority |
| Local emit fails | No authoritative message | Mirror must not run | Operation fails closed |
| Receiver wrapper verification fails | Producer envelope unchanged | Hosted manifestation rejected | Consumer must not process |

## Initial adoption sequence

Centinelas is the first producer because it currently originates multiple
cross-repository dispatch paths. Its migration must keep the deterministic local
classifier and local artifact write available without credentials. Anthropic and
GitHub remain optional adapters and cannot be required for the core path.

Downstream consumers are migrated only after the Centinelas producer contract and
negative regressions pass. Existing raw source acquisitions and mature scientific
or geospatial libraries are outside this transport change.

## Remaining dynamic gates

This mirror contract closes no Federation freedom gate by itself. The following
remain required on exact producer and consumer heads:

1. clean-cache install;
2. denied-network startup;
3. connector-only allowlist execution;
4. no-secret startup and core operation;
5. packaged-release egress capture;
6. postinstall/native binary and extension capture;
7. offline browse, map, analyze, report, and export;
8. rebuild from frozen source plus locally retained dependency bytes.
