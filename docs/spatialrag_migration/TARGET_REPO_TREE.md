# Target Repo Tree — proposed post-migration layout

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

This is a design target, not a change made now. **No file listed below is created in this phase.**
Each entry is annotated with the phase that introduces it, per [`PHASED_BACKLOG.md`](PHASED_BACKLOG.md).

```
thehub-pr/
├── src/
│   ├── hub/                          # unchanged — existing structured federation pipeline
│   │   ├── registry.py, manifest.py, validate.py, fetch.py,
│   │   │   aggregate.py, correlate.py, ingest.py, bridge.py, cli.py, ...
│   │   └── mcp_runtime/
│   │       ├── policy.py             # unchanged — Control Plane permissions base (adopted, not modified in Phase 0-1)
│   │       ├── auth.py               # unchanged — Control Plane credential base (adopted, not modified in Phase 0-1)
│   │       └── adapters/documents.py # unchanged — flagged in DUPLICATION_REGISTER.md as a Phase 5+ candidate
│   │
│   ├── control_plane/                # NEW — Phase 2 (skeleton), Phase 3+ (full)
│   │   ├── registry.py               #   producer/engine registry extension
│   │   ├── orchestration.py          #   job orchestration for Evidence Engine ingest runs
│   │   ├── snapshot_gate.py          #   compute_snapshot_gate() — see SNAPSHOT_STATE_MACHINE.md
│   │   ├── policy.py                 #   extends src/hub/mcp_runtime/policy.py::PolicyEngine
│   │   ├── access.py                 #   access-classification enforcement — see SECURITY_MODEL.md
│   │   └── audit.py                  #   audit ledger
│   │
│   ├── evidence_engine/              # NEW — Phase 2
│   │   ├── ingestion/                #   chunker, embedder, ocr (ADAPT per COMPONENT_MIGRATION_MATRIX.md)
│   │   ├── tiering.py                #   provisional evidence-tier classifier — DATA_CONTRACTS.md §2
│   │   ├── spatial/                  #   coordinate extraction + uncertainty geometry
│   │   ├── temporal/                 #   temporal field extraction — DATA_CONTRACTS.md §8
│   │   ├── entity_resolution/        #   contradiction-preserving resolution — DATA_CONTRACTS.md §5
│   │   └── snapshot_build.py         #   certified snapshot construction
│   │
│   └── intelligence_engine/          # NEW — Phase 2
│       ├── retrieval/                #   lexical/vector/spatial/temporal/graph retrieval
│       ├── profiles.py               #   RetrievalProfile registry — DATA_CONTRACTS.md §4
│       ├── hyde.py                   #   HyDE, hyde_enabled=false by default
│       ├── reranker.py               #   rebuilt MMR (COMPONENT_MIGRATION_MATRIX.md row 8 — current version is dead code)
│       ├── claim_ledger.py           #   Claim construction — DATA_CONTRACTS.md §3
│       ├── contradiction.py          #   ContradictionSet assembly
│       └── abstention.py             #   AbstainResponse — DATA_CONTRACTS.md §9
│
├── schemas/                          # existing frozen-schema mechanism, extended — Phase 1
│   ├── federation_evidence_item.schema.json      # NEW — Phase 1
│   ├── federation_claim.schema.json              # NEW — Phase 1
│   ├── federation_snapshot.schema.json           # NEW — Phase 1
│   ├── federation_retrieval_profile.schema.json  # NEW — Phase 1
│   ├── federation_entity_identity_decision.schema.json  # NEW — Phase 1
│   └── FROZEN.sha256                             # regenerated deliberately (--update) when the above land
│
├── benchmarks/                       # NEW — Phase 1 (spec + skeleton dirs only), Phase 2 (populated)
│   ├── corpus/                       #   labeled queries — see EVALUATION_CORPUS_SPEC.md
│   └── harness/                      #   runnable evaluation harness
│
├── docs/
│   ├── adr/0003-evidence-intelligence-control-plane.md   # THIS deliverable — Phase 0
│   └── spatialrag_migration/                             # THIS deliverable — Phase 0
│
├── server/backend/                   # unchanged in Phase 0-1; gains Control Plane / Intelligence
│   │                                  # Engine routes in Phase 2+ per API_CONTRACT.md
│
└── server/frontend/                  # unchanged until Phase 4 (UI parity) — new evidence/claim
                                       # views built in React/Vite, not ported from spatial-rag's Next.js
```

## Dependency extras implied (spec only — `pyproject.toml` is not edited in this phase)

thehub-pr's `pyproject.toml` already has a `[project.optional-dependencies]` block with `dev` and
`server` extras (confirmed verbatim):

```toml
[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff>=0.4", "mypy>=1.10", "types-PyYAML"]
server = ["fastapi>=0.100", "uvicorn[standard]>=0.22"]
```

Following that precedent, spatial-rag's monolithic `backend/requirements.txt` (fastapi, sqlalchemy,
anthropic, sentence-transformers, torch, transformers, spacy, pdfplumber, pytesseract, ocrmypdf,
Pillow, geopy, pytest, ...) splits into new extras — named, not yet added:

| Extra | Rough contents (from spatial-rag's requirements.txt, regrouped) |
|---|---|
| `rag` | fastapi/sqlalchemy/asyncpg/psycopg2/alembic runtime pieces needed by the Evidence/Intelligence Engines |
| `intelligence` | anthropic (or other `LLMProvider` backend), sentence-transformers, torch, transformers |
| `spatial` | geopy, PostGIS client bindings |
| `ocr` | pdfplumber, pytesseract, ocrmypdf, Pillow |

`dev`/`server` stay as-is. This table is the Phase 1 starting point for editing `pyproject.toml` —
not an instruction executed now.

## Worker/service split implied (spec only — `docker-compose.yml`/`Dockerfile` not edited in this phase)

Per the mission's dependency-and-deployment-target requirement, the eventual service split is:
lightweight API, ingestion/OCR worker, embedding worker, intelligence service, frontend — as distinct
`docker-compose.yml` services, mirroring spatial-rag's existing three-service split (`db`, `backend`,
`frontend`) but decomposed further to isolate the heavy OCR/ML dependency footprint from the
lightweight API surface. Full compose file design is a Phase 2 task once `evidence_engine`/
`intelligence_engine` module boundaries are implemented, not specified module-by-module here.
