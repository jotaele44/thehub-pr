# THEHUB Dual-Engine Architecture — Overview

A plain-language + diagram companion to the handoff specs (`01_ARCHITECTURE_SPEC.md`,
`SNAPSHOT_STATE_MACHINE.json`, `SECURITY_MODEL.json`) and the Phase-1 contract drafts
(`../phase1-design/`). Design/documentation only — no code.

## The one-line model

**A build (write) side and a read-only query side, separated by an immutable certified-snapshot
boundary that a control plane governs.** It reads as "two-sided," but it is formally **three layers** —
the Control Plane is the referee that owns certification, promotion, and access policy across both sides.

| Side | Layer(s) | Owns | Direction |
|---|---|---|---|
| Build / analysis-execution | **Evidence Engine** (orchestrated by **Control Plane**) | acquisition, validation, normalization, provenance, reversible identity, spatial/temporal, deterministic correlation, **certification** | writes evidence |
| Query / fetch | **Intelligence Engine** | retrieval, comparison, citation, claims, contradictions, abstention, visualization | **read-only** |

## Diagram 1 — three-layer / two-sided model with the snapshot boundary

```mermaid
flowchart LR
    subgraph BUILD["BUILD / WRITE SIDE"]
        direction TB
        P["Producers x6<br/>(federation.json + export packages)"]
        EE["Evidence Engine<br/>acquire - validate - normalize<br/>provenance - identity - spatial/temporal<br/>deterministic correlation - certify"]
        P --> EE
    end

    subgraph CP["CONTROL PLANE (governs both sides)"]
        direction TB
        REG["Registry - orchestration - readiness"]
        POL["PolicyDecider (deny-by-default)<br/>one decision for all surfaces"]
        PROM["Atomic snapshot promotion / rollback"]
        AUD["Append-only audit ledger"]
    end

    SNAP{{"CERTIFIED SNAPSHOT<br/>immutable - hashed manifest<br/>ONLY the ACTIVE snapshot answers queries"}}

    subgraph READ["READ / QUERY SIDE"]
        direction TB
        IE["Intelligence Engine (READ-ONLY)<br/>exact-ID / structured / lexical / vector<br/>spatial / temporal / graph retrieval"]
        CL["Claim ledger + abstention"]
        UI["Surfaces: search - map - export<br/>document viewer - model context"]
        IE --> CL --> UI
    end

    EE -->|certify| SNAP
    PROM -.->|"activate / rollback"| SNAP
    SNAP -->|ACTIVE only| IE
    POL -.->|"access-class filter before retrieval and model context"| IE
    POL -.->|policy parity| UI
    AUD -.->|receipts| EE
    AUD -.->|receipts| IE

    classDef build fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;
    classDef ctrl fill:#fff3e0,stroke:#e65100,color:#e65100;
    classDef read fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef snap fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c;
    class P,EE build;
    class REG,POL,PROM,AUD ctrl;
    class IE,CL,UI read;
    class SNAP snap;
```

**Invariants shown (from `SNAPSHOT_STATE_MACHINE.json` / `SECURITY_MODEL.json`):**
- The snapshot is the **sole integration boundary**; the two sides never touch directly.
- Only an **`ACTIVE`** snapshot answers normal queries; a failed evidence/index build (`INDEX_FAILED`)
  never mutates the current `ACTIVE` snapshot (atomic promote/rollback).
- The Intelligence Engine is **read-only** — no mutation surface against canonical evidence.
- One `PolicyDecider.decide()` governs **search, map, export, viewer, and model context** identically
  (access-policy parity); classification filters run **before** retrieval and **before** model context.
- Every lifecycle transition and policy decision emits an immutable audit receipt.

## Diagram 2 — mapping the Spatial-RAG donor onto the split

The donor (`spatialragv2.zip`) is *two-sided in its own code* but **fused** (ingestion routes and query
routes share one Postgres DB). The migration **splits** it into the Evidence vs Intelligence engines with
the snapshot + policy inserted between. Dispositions are from `APPROVED_COMPONENT_LEDGER.csv` — every row
is `code_movement_authorized = NO` (design targets, not extractions).

```mermaid
flowchart TB
    subgraph DONOR["Spatial-RAG donor (FUSED — capability donor, NOT a merge unit)"]
        direction LR
        DIng["ingestion/: chunker, embedder, ocr, pipeline, quality"]
        DRet["retrieval/: engine, reranker, query_expansion(HyDE)"]
        DCit["citation/engine.py"]
        DApi["api/routes.py (ingest + query mixed)"]
        DDb[("shared Postgres/PostGIS/pgvector<br/>migrations 001/002 = REFERENCE_ONLY")]
        DIng --- DDb
        DRet --- DDb
        DCit --- DDb
        DApi --- DDb
    end

    subgraph TARGET["Target split (Phase 1 design)"]
        direction LR
        subgraph T_EE["Evidence Engine (build)"]
            EEc["chunker/quality: ADAPT (add page offsets, deterministic ids)"]
            EEo["ocr: ADAPT (quarantine, page limits, bbox, confidence)"]
            EEp["pipeline: REWRITE (snapshot builder)"]
            EEs["spatial enricher: ADAPT (uncertainty, precision class)"]
        end
        SNAP2{{"CERTIFIED SNAPSHOT<br/>(SQLite authoritative; vector index rebuildable, non-authoritative)"}}
        subgraph T_IE["Intelligence Engine (read-only query)"]
            IEr["retrieval: ADAPT (logged profiles, no fixed weights)"]
            IErr["reranker: BENCHMARK-ONLY"]
            IEc["citation: REWRITE (claim ledger + tier provenance)"]
            IEq["query_expansion / HyDE: DEFERRED (off by default)"]
        end
    end

    DIng -->|"ADAPT / REWRITE"| T_EE
    DRet -->|ADAPT| T_IE
    DCit -->|REWRITE| IEc
    DApi -->|split build vs read routes| T_IE
    T_EE -->|certify| SNAP2
    SNAP2 -->|ACTIVE only| T_IE

    DRet -.->|"correlation.py = REJECTED_AS_AUTHORITY: Hub correlation stays authoritative"| T_IE

    classDef donor fill:#fdecea,stroke:#b71c1c,color:#7f0000;
    classDef ee fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;
    classDef ie fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef snap fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c;
    class DIng,DRet,DCit,DApi,DDb donor;
    class EEc,EEo,EEp,EEs ee;
    class IEr,IErr,IEc,IEq ie;
    class SNAP2 snap;
```

## How this maps to the certified baseline

- The Hub today already owns the **build side** in miniature: 6 producers → `hub fetch` → `hub aggregate`
  → deterministic `hub correlate` → `hub ingest` into **SQLite `data/hub.db`** (authoritative), across
  **8 canonical streams** (sources, entities, relationships, funding_awards, transactions, observations,
  alerts, correlations). See `../phase0/BASELINE_COUNTS.json`.
- **SQLite stays authoritative**; the Spatial-RAG PostgreSQL/PostGIS/pgvector schema is **reference-only**
  and is never applied to the Hub (`../phase0/SPATIAL_RAG_REPRODUCTION_LEDGER.md`).
- The read-only boundary, no-LLM structured query, snapshot lifecycle, and claim/abstention contracts are
  drafted in `../phase1-design/` (schemas + `INTERFACES_DESIGN.md`).

## What is deliberately NOT in the picture (retained HOLD)

No direct ZIP merge · no Spatial SQL applied to the Hub · HyDE off by default · no automatic entity
merges · the existing Hub deterministic correlation remains the sole cross-producer authority ·
Phase-1 *implementation* is not started.
