# Phase 1 Security Contract Design

> Design documents only — no implementation, no code movement. Grounded in `SECURITY_MODEL.json`,
> `03_SECURITY_AND_POLICY.md`, and `PREFLIGHT_REPORT.json`. Maps to T036–T039, T043.

## Principles (fixed)

Auth required outside development · deny by default · **source content is untrusted** · policy parity
across retrieval surfaces · secrets never logged · the ACTIVE snapshot is immutable.

## 1. Upload quarantine (T036)

Untrusted uploads are written to an isolated quarantine store and remain `QUARANTINED`
(access_classification) until cleared. No quarantined artifact enters a snapshot, retrieval result, or
model context. Clearing requires passing archive-safety limits (§2) and validation, transitioning the
evidence record `QUARANTINED → INGESTING` (evidence_lifecycle).

## 2. Archive-safety limits (T037)

Enforced on every ingested archive **before** extraction:

| Control | Rule | Preflight evidence |
|---|---|---|
| Path traversal | reject any entry whose normalized path escapes the root | 0 traversal names observed |
| Symlinks | reject symlink entries | 0 symlinks observed |
| Decompression ratio | reject above a fixed ratio ceiling | observed ratio 3.51 (below any sane cap) |
| Duplicate filenames | reject / disambiguate | flagged in ADVERSARIAL_TEST_SPEC |
| Page limits | cap pages per document (OCR/PDF) | OCR component ledger requires page limits |

Malformed brace-expansion paths (5 seen in preflight) and pytest-cache entries (8) are excluded at
intake. These map to adversarial tests "malicious archive paths" and "decompression bombs".

## 3. Outbound fetch allowlist (T038)

All outbound fetches (geocoder, source acquisition) go through an allowlist of permitted destinations;
every request is logged. Non-allowlisted hosts are denied by default. No fetch is triggered by document
content (prevents SSRF via injected URLs).

## 4. Secret redaction (T039)

Credentials, API keys, and tokens never appear in logs, audit receipts, run receipts, or error
messages. A redaction filter runs before any write to the audit ledger or logs. This directly closes
the preflight blockers "fixed database passwords" (8 occurrences) and "optional API-key posture" — no
secret is embedded in config; secrets come from the environment/secret manager only
(`config.py` = REWRITE: "no embedded secrets or provider/model defaults").

## 5. Access-policy parity (T043)

The single `PolicyDecider.decide()` (see `INTERFACES_DESIGN.md` §3) governs **search, map, export,
document viewer, and model context** identically. Access-class filters apply **before retrieval** and
**before model context**. Target: `citation_access_policy_violations_max == 0`,
`unauthorized_result_leakage_max == 0`.

## 6. Prompt-injection isolation

Source content is data, never instructions. Retrieved `SourceArtifact` / `TextChunk` text placed in a
prompt is fenced as untrusted evidence; hidden OCR instructions and in-document injections
(ADVERSARIAL_TEST_SPEC) must not alter system behavior or exfiltrate restricted evidence.

## Rejected donor (security-relevant)

`docker-compose.yml` = **REJECTED** (development credentials, exposed DB port, coupled services).
`backend/middleware/security.py` = ADAPT only **after** auth, CORS allowlist, access classification,
secret redaction, quarantine, and policy parity are added — the Control Plane owns authorization.
