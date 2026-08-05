# ADR 0006 — Skywatcher AI and Imagery Extraction, Centralization and Retirement

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** PRII federation maintainers
- **Scope:** `thehub-pr` and `skywatcher-pr`
- **Authoritative record:** `thehub-pr/docs/adr/0006-skywatcher-ai-imagery-centralization.md`
- **Extends:** ADR 0003 — Evidence Engine, Intelligence Engine and Control Plane; ADR 0004 — Native Federation Manager
- **Supersedes:** Informal references to a Skywatcher “RAG/EarthGPT” runtime
- **Implementation authority:** Architecture and contract decomposition only. Runtime implementation requires the atomic PR sequence in this package.

## Context

Skywatcher current `main` contains a satellite-imagery MCP package, an Anthropic-based FR24 screenshot extraction script, an RLSM ingestion adapter, SATIM imagery analysis and aviation-specific computer-vision logic.

It does not contain a complete retrieval-augmented-generation system. It has no embeddings, vector database, semantic retrieval engine, claim-ledgered answer generation, citation engine or conversational RAG interface.

The implementation nevertheless creates duplicated control surfaces: standalone network acquisition, producer-local credentials, mutable local satellite artifacts, direct external model transmission, incomplete field provenance and operations outside TheHub’s Control Plane and certified-snapshot boundary.

TheHub is the single supported product surface. Its Evidence Engine owns acquisition, validation, provenance and snapshot construction; its Intelligence Engine reads only certified `ACTIVE` snapshots; and its Control Plane owns policy, authorization, credentials, audit, approvals and promotion.

## Decision

Skywatcher remains an artifact-producing aviation-domain engine.

### Skywatcher owns

- Aviation extraction schemas.
- FR24 and RLSM normalization.
- Screenshot-to-record matching.
- Aircraft identity and FAA registry cross-validation.
- SATIM imagery analysis.
- Track-vector extraction.
- Aviation-specific quality and review rules.
- Deterministic producer-package construction.

### TheHub owns

- Satellite-provider network access.
- Credential brokering and no-readback injection.
- Provider and model allowlists.
- Model routing.
- Prompt, policy and extraction-task versioning.
- Content-addressed source-artifact storage.
- Acquisition, tool and model-run receipts.
- Access-classification and egress-policy enforcement.
- Snapshot intake, certification and promotion.
- Retrieval, claims, contradictions and citations.
- Assistant and operator GUI workflows.

Skywatcher will not host semantic RAG, a chatbot, an independent vector store or an independently deployed production model service.

## Integration boundary

```text
TheHub-authorized acquisition or model run
        ↓
content-addressed source artifact + immutable receipt
        ↓
isolated Skywatcher bounded producer worker
        ↓
aviation-domain extraction and provisional analysis
        ↓
versioned Skywatcher producer package
        ↓
TheHub Evidence Engine validation and certification
        ↓
ACTIVE evidence snapshot
        ↓
TheHub Intelligence Engine and Federation Assistant
```

TheHub may start a bounded producer job through an approved worker contract, but it may not query Skywatcher databases through live RPC. Skywatcher may not directly query TheHub’s evidence database.

### Bounded worker contract

A Skywatcher worker:

- Executes in an isolated ephemeral workspace.
- Receives immutable input-artifact references and a signed job specification.
- Writes only to its designated output-package directory.
- Receives no direct Evidence Engine database access.
- Receives no persistent shared-database mount.
- Receives no unrestricted shell or Control Plane secret readback.
- Has outbound network denied by default.
- May receive network access only for a separately approved producer operation; normal AI and imagery-provider access remains outside the worker.
- Produces complete input, exclusion, failure and output accounting.

## Query-triggered acquisition certification gate

A user query may initiate an authorized acquisition job. Newly acquired material may not support a grounded answer, analytical claim, contradiction assessment or citation until it has completed content-addressed storage, Skywatcher bounded processing when applicable, Evidence Engine validation, certification and `ACTIVE` promotion.

Before certification, the assistant may report only operational job status and clearly labeled provisional metadata. It may not present the acquired content as certified evidence.

## Access classification and model egress

Every source artifact receives an access classification before external model execution. External transmission requires an affirmative egress decision based on classification, workspace policy, provider allowlist, provider residency, permitted use, task purpose, data minimization and approval state.

`RESTRICTED`, `SENSITIVE_LOCATION`, `LEGAL_HOLD` and `QUARANTINED` artifacts may not be sent externally unless an explicit policy permits that exact provider, task and classification. When external egress is denied, the task must use an approved local/private provider or fail closed.

## Retained components

- RLSM screenshot inventory and evidence ledger.
- Vision-output ingestion into RLSM.
- SATIM imagery and calibration logic.
- Track-vector and route-analysis logic.
- Aviation extraction field definitions.
- Screenshot, aircraft and FAA registry correlation.
- Manual-review workflows.
- Deterministic producer-package generation.

Producer review and Evidence Engine certification remain distinct decisions. Skywatcher review may approve package inclusion; only TheHub certification may admit material into a certified snapshot.

## Migrated components

- GIBS, Sentinel Hub and CDSE network acquisition.
- Provider retry, timeout, host and network policy.
- Credential handling.
- Query-triggered imagery acquisition.
- Generic content cache.
- Model-provider execution.
- Model and prompt selection.
- Model/tool budgets.
- Audit-event creation.
- Snapshot intake and certification.
- Assistant-facing tool and GUI bindings.

## Rewritten components

1. Local imagery manifests become content-addressed `SourceArtifact` candidates with immutable `AcquisitionReceipt` records.
2. Vision extraction becomes a provider-neutral, schema-constrained model task.
3. Every model-derived field receives field-level provenance, validation and review state.
4. RLSM and canonical exports preserve the actual extraction engine.
5. Image-difference output becomes a versioned provisional SATIM signal, not an evidentiary conclusion.
6. Provider failures become typed, auditable outcomes.

### Required model-field provenance

Every model-derived field retains source-artifact ID and SHA-256; source region when available; model-run receipt; provider, model and immutable revision; prompt-template version and hash; policy version and access-context hash; extraction-schema version; value and confidence; validation outcome; review status and reviewer; creation time and supersession history.

Canonical export may transform representation but may not erase or replace extraction provenance.

A matching FAA registry record may corroborate a model-extracted registration, but it does not change the extraction method, erase model provenance or prove that the registration was visible in the screenshot.

## Object separation

- `AcquisitionReceipt` records execution and acquisition facts.
- `SourceArtifact` represents acquired content.
- Skywatcher provisional outputs represent domain extraction or analysis.
- `EvidenceItem` exists only after Evidence Engine validation and certification.

These objects may reference one another but may not be collapsed into one mutable manifest.

## Deprecated components

Deprecated immediately:

- “RAG/EarthGPT” terminology for current Skywatcher.
- Standalone SSE deployment of `imagery.server`.
- Direct MCP-client configuration as a supported product workflow.
- Direct production use of `ANTHROPIC_API_KEY` by Skywatcher.
- Hardcoded model defaults in producer code.
- Local satellite manifests as certified evidence.
- Default write behavior during imagery fetch.

Deprecation does not authorize deletion.

## Legacy artifact disposition

Before retirement, Skywatcher produces a disposition ledger covering local satellite manifests, imagery cache objects, vision CSVs, checkpoints, model-derived RLSM rows and logs.

Each object or logical record set is classified as `MIGRATED_VERIFIED`, `RETAINED_PRODUCER_LOCAL`, `QUARANTINED`, `SUPERSEDED` or `DELETED_AFTER_VERIFICATION`, with locator, SHA-256 where applicable, record count, classification, reason and replacement artifact or snapshot ID.

## Dual-run requirement

At least two reproducible dual runs are required. Each uses the same pinned source-artifact set, Skywatcher and TheHub revisions, schema revisions, provider/model revision, prompt template, policy version and worker profile.

Deterministic outputs must have identical normalized digests. Model outputs use a versioned field-level equivalence policy. Every run requires zero schema violations, zero missing required provenance and complete input, exclusion, failure and output accounting.

## Removal policy

Deprecated code is removed only after functional parity, provenance parity or improvement, two dual runs, successful rollback, GUI reachability, zero old-surface consumers, complete legacy disposition, static verification of no direct provider calls and runtime deny-network verification.

Retirement is incomplete until production dependencies contain no external model SDK; production code and configuration contain no retired credential loading, provider secrets or hardcoded model defaults; static tests reject prohibited calls; normal producer jobs pass deny-network tests; and TheHub tests prove all acquisition/model operations use approved Control Plane capabilities.

## Consequences

Skywatcher becomes smaller and domain-specific. TheHub assumes provider connectivity, model execution, artifact storage and certification behind one policy, audit and permission boundary.

Model output remains provisional until reviewed and certified. The migration is incremental, with shadow dual runs. No big-bang merge, live producer RPC or premature deletion is authorized.

## Verification

1. The authoritative ADR is committed to TheHub and Skywatcher contains only the reference note.
2. All schema deltas validate under JSON Schema Draft 2020-12.
3. Every decision clause maps to implementation PRs and tests.
4. The parity matrix has no unowned gate.
5. The retirement checklist includes static, runtime, GUI, rollback and data-disposition evidence.
