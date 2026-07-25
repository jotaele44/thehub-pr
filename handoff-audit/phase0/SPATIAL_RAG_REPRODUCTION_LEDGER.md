# Spatial-RAG DB / PostGIS / pgvector Reproduction Ledger (T009–T012)

**Result: REPRODUCED — the handoff's 4th critical blocker is CLOSED.**

Source package: `spatialragv2.zip`, SHA-256 `cd3b78f343be5b7c64099ca099854f27179992dccf8c31ae5e2b67a1f9b4140f`
(matches `08_MACHINE_CONTEXT.json` and `PREFLIGHT_REPORT.json`; the package was **not** mutated or
merged into the Hub — it was reproduced in isolation under the scratchpad).

## Environment (T009)

| Component | Compose spec (`docker-compose.yml`) | Reproduced here | Note |
|---|---|---|---|
| PostgreSQL | 15 (`pgvector/pgvector:pg15`) | **16.13** | Version delta — see caveats |
| PostGIS | 3.4 | **3.4.2** | apt `postgresql-16-postgis-3` |
| pgvector (server ext) | (in image) | **0.6.0** | apt `postgresql-16-pgvector` |
| pg_trgm / unaccent / pgcrypto | required by 001 | 1.6 / 1.1 / 1.3 | base install |
| App role | `spatial_rag` (image superuser) | `spatial_rag` **+ SUPERUSER** | required for `CREATE EXTENSION postgis` (not a trusted extension); faithful to the compose image where `POSTGRES_USER` is superuser |
| Databases | `spatial_rag` | `spatial_rag`, `spatial_rag_test` | test DB per `backend/tests/conftest.py` |

## Migrations applied TWICE (T010) — idempotent

`psql -v ON_ERROR_STOP=1 -f migrations/001_initial.sql` then `002_upgrades.sql`, run twice against a
clean `spatial_rag_test`:

- **Pass 1:** both files exit 0. Only benign `NOTICE: trigger ... does not exist, skipping` from
  defensive `DROP TRIGGER IF EXISTS`.
- **Pass 2:** both files exit 0. Only `NOTICE: ... already exists, skipping` — i.e. the migrations are
  **idempotent** (guarded by `IF NOT EXISTS` / `DO $$ ... EXCEPTION WHEN duplicate_object`).
- Final `schema_migrations` = `{001, 002}`.

Resulting schema: **15 base tables** (`answers`, `answer_feedback`, `chunks`, `citations`,
`corridor_segments`, `documents`, `entities`, `entity_edges`, `grid_cells`, `mentions`, `pages`,
`schema_migrations`, `search_logs`, `spatial_mentions`, plus PostGIS `spatial_ref_sys`) +
**1 materialized view** (`mv_entity_cooccurrence`). PostGIS geometry columns: 3; pgvector `vector`
columns: 1.

## Tests against the live DB (T011 + T012)

Venv: `backend/.venv-spatial` (Python 3.11.15, pytest 8.3.2). Env: `DATABASE_URL(_SYNC)` →
`spatial_rag_test`. Command: `pytest -q` (pytest.ini `asyncio_mode=auto`).

```
collected 149 items
tests/test_api.py .......................   (23)   ← API integration (T012)
tests/test_cache.py ............            (12)
tests/test_citation.py ...................  (25)
tests/test_ingestion.py ................    (16)
tests/test_middleware.py ................   (16)
tests/test_quality.py ...................   (19)
tests/test_reranker.py ...........          (11)
tests/test_retrieval.py ...............     (15)
tests/test_spatial.py ............          (12)
============ 149 passed in 1.35s ============
```

**149 passed, 0 failed, 0 skipped.** The API integration suite (`test_api.py`, 23 tests) exercises
the FastAPI app against the real PostGIS+pgvector test database. ML providers (embedder / reranker /
LLM) are injected as fakes by the test fixtures, so no model download is required and the run is fast
and hermetic apart from the database.

## Findings (recorded, non-blocking for reproduction)

1. **Three undeclared runtime dependencies** — imported by the code but **absent from
   `backend/requirements.txt`**; collection failed until each was installed:
   - `tenacity` (used in `app/spatial/enricher.py`)
   - `geoalchemy2` (used in `app/models/orm.py` for the `Geometry` type)
   - `pgvector` (Python client, used in `app/models/orm.py` for the `Vector` type)
   This corroborates the preflight's `single_mixed_requirements_file` concern with concrete gaps. If
   the Spatial-RAG package is ever adopted as a capability donor, its dependency manifest must be
   completed and pinned.
2. **PostgreSQL version delta:** reproduced on **pg16**, whereas the compose file pins **pg15**. All
   migrations and tests pass on pg16; a strict certification should also confirm pg15 parity.
3. **Superuser requirement:** `CREATE EXTENSION postgis` requires superuser. Fine for the
   single-container compose model, but a hardening item for any managed/production deployment (least
   privilege) — consistent with the readiness report's "insecure development defaults" blocker.

## Disposition

The specific critical blocker *"Spatial-RAG database/PostGIS/pgvector integration tests have not been
independently reproduced"* is **CLOSED**. This certifies the package's DB layer is reproducible; it
does **not** authorize any merge — the Spatial-RAG package remains a **capability donor, not a merge
unit**, and HOLD on code movement is retained.
