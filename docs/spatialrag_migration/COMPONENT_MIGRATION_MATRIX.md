# Component Migration Matrix — spatial-rag → thehub-pr

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

This is the migration-by-extraction ledger required before any code moves. It replaces the
instinct to copy `spatial-rag/` wholesale into the Hub. Every component of the uploaded
`spatialragv2.zip` package (SHA-256 `cd3b78f343be5b7c64099ca099854f27179992dccf8c31ae5e2b67a1f9b4140f`)
is classified below. **No row in this table has been executed.** Classification precedes code
movement; it does not authorize it.

## Legend

Classifications are defined relative to *this* migration, not as generic dictionary terms:

| Classification | Meaning here |
|---|---|
| **ADOPT** | Reuse substantially unchanged. |
| **ADAPT** | Reuse the mechanism, but it must be rewired to satisfy a Hub-side contract (snapshot boundary, provider abstraction, provisional-tier model, etc.) before it lands. |
| **REWRITE** | The concept is worth keeping; the current implementation is not — its shape is incompatible with a target contract in [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md), [`DATABASE_BOUNDARIES.md`](DATABASE_BOUNDARIES.md), or [`SECURITY_MODEL.md`](SECURITY_MODEL.md). |
| **REJECT** | Unsafe, dead, or architecturally incompatible; not carried forward even as inspiration. |
| **DUPLICATE** | Worth having in thehub-pr, but as *documented reference* rather than imported code, because the target contract differs enough that porting the artifact directly would be misleading. |
| **DEFER** | Useful, but not Phase 1 — either because it depends on work that hasn't happened yet, or because it currently carries unmitigated risk. |

## Matrix

| # | Component | Source location | Classification | Target | Reasoning |
|---|---|---|---|---|---|
| 1 | Chunker | `backend/app/ingestion/chunker.py` | **ADAPT** | Evidence Engine | Deterministic sliding-window splitting (`max_tokens=512`, `overlap_tokens=64`) is domain-agnostic and reusable, but it must write the new `EvidenceItem`/`TextChunk` objects ([`DATA_CONTRACTS.md`](DATA_CONTRACTS.md)) instead of a flat `chunks` row with no provenance or geometry fields. |
| 2 | Embedder | `backend/app/ingestion/embedder.py` | **ADAPT** | Intelligence Engine | `all-MiniLM-L6-v2` via `sentence-transformers` is a reasonable default, but it must move behind an `EmbeddingProvider` abstraction ([`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §14) so the model identity is recorded per snapshot and swappable without silently altering historical answers. |
| 3 | OCR pipeline | `backend/app/ingestion/ocr.py` | **ADAPT** | Evidence Engine | `pdfplumber` + Tesseract fallback at a character-density threshold works, but produces no bounding boxes, no rendered-page hash, no source-file hash — all required by [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §13. Also belongs in its own `ocr` dependency extra given its weight (`ocrmypdf`, `pytesseract`, `Pillow`). |
| 4 | Quality scorer | `backend/app/ingestion/quality.py` | **ADAPT** | Evidence Engine | The additive-penalty quality score and near-duplicate/language detection are legitimate, reusable signals for `EvidenceItem` metadata; they are not the evidence-tier mechanism (see #5) and should not be conflated with it. |
| 5 | Evidence-tier scorer (`_assign_evidence_tier`) | `backend/app/citation/engine.py` | **REWRITE** | Evidence Engine | Currently a keyword-match against hardcoded word lists (survey/measurement/official → T1, etc.), and its output is written straight into `entities.evidence_tier`/`citations.evidence_tier` as if final. Rejected as a source of truth outright: the mechanism survives only as a `PROVISIONAL` machine-suggestion input to the tier model in [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §5, never a silently-accepted tier. |
| 6 | Retrieval engine / hybrid scoring | `backend/app/retrieval/engine.py` | **REWRITE** | Intelligence Engine | Weights (`bm25=0.4, vector=0.4, spatial=0.2`) are hardcoded independently in three places (`RetrievalParams`, `SearchRequest`, `config.py` — and the `config.py` constants aren't even wired to the scoring SQL). Replaced by the versioned `RetrievalProfile` object in [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §9. Must also stop querying live Postgres directly and query only the certified snapshot boundary per [`DATABASE_BOUNDARIES.md`](DATABASE_BOUNDARIES.md). |
| 7 | HyDE query expansion | `backend/app/retrieval/query_expansion.py` | **ADAPT** | Intelligence Engine | The mechanism (generate a hypothetical passage, embed it, retrieve against that) is legitimate recall-expansion technique; the *policy* is wrong. Every `RetrievalProfile` must default `hyde_enabled=false`, require explicit per-query opt-in, log the generated hypothesis, and never affect evidence tier or confidence — see [`SECURITY_MODEL.md`](SECURITY_MODEL.md) for the data-handling angle (forensic text sent to a third-party LLM by default). |
| 8 | MMR reranker | `backend/app/retrieval/reranker.py` | **REJECT as shipped / DEFER concept** | — | `mmr_rerank()` is a correct implementation, but its actual call site in `engine.py` passes `chunk_embeddings={}` — an empty dict — so the diversity term collapses to zero and MMR silently degrades to top-k-by-score. This is dead code presented as a working feature. Do not port as-is; if diversity reranking is still wanted, build it fresh against real embeddings and add a contract test that would have caught this. |
| 9 | Spatial enricher — regex coordinate extraction | `backend/app/spatial/enricher.py` | **ADAPT** | Evidence Engine | DMS/decimal coordinate regex extraction with per-pattern confidence is a legitimate deterministic primitive, reusable once it populates the geometry-uncertainty fields in #11. |
| 10 | Spatial enricher — `geocode_place()` (Nominatim) | `backend/app/spatial/enricher.py` | **DEFER** | Evidence Engine | Function exists but is never invoked by `enrich()`. Activating it means a live outbound call to a third-party geocoding service — needs the outbound-URL allowlist and a ToS/rate-limit review from [`SECURITY_MODEL.md`](SECURITY_MODEL.md) before it is ever wired in, not inherited silently as "already there." |
| 11 | Spatial enricher — uncertainty geometry | `backend/app/spatial/enricher.py`, migration `002_upgrades.sql` | **REWRITE** | Evidence Engine | `bbox_min/max_lat/lon` columns exist in the DB schema but nothing populates them, and there is no `geometry_source`/`geometry_method`/`precision_class`/`crs` model at all. Net-new design per [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §12 — a municipality mention must never be displayed as an exact facility coordinate. |
| 12 | Citation engine — sentence-level gating | `backend/app/citation/engine.py` | **REWRITE** | Evidence Engine | Sentence-level `[N]`-ref enforcement (drop any sentence lacking a citation) is architecturally incompatible with the claim-level ledger required by [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §6 — a rendered answer must be a presentation of a claim ledger, not the primary analytical record. Some output-formatting logic (sentence splitting, ref extraction) is salvageable; the citation *model* is not. |
| 13 | ORM / DB schema | `backend/app/models/orm.py`, `backend/migrations/001_initial.sql`, `002_upgrades.sql` | **REJECT as schema / DUPLICATE as reference** | Evidence Engine | Built for a live, directly-mutable database with no snapshot boundary — incompatible with [`DATABASE_BOUNDARIES.md`](DATABASE_BOUNDARIES.md) by construction. Individual column ideas (`evidence_tier`, `ocr_confidence`, `is_near_dup`/`near_dup_of`, generated `tsvec`) are worth preserving as documented reference in [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md), not imported as SQLAlchemy models or SQL files. Note the ORM file itself is already stale relative to the raw-SQL migrations (missing `quality_score`, `language_code`, `evidence_tier`, `is_near_dup` columns) — a second, independent hygiene defect. |
| 14 | Alembic migrations | `backend/migrations/001_initial.sql`, `002_upgrades.sql` | **REJECT** | — | Tied 1:1 to the rejected mutable schema (#13); fresh migrations are written against the new snapshot-bound schema from [`DATABASE_BOUNDARIES.md`](DATABASE_BOUNDARIES.md), not evolved from these. |
| 15 | API routes | `backend/app/api/routes.py` | **REWRITE** | Control Plane / Intelligence Engine | None of the target contracts exist today: no retrieval-object-type distinction, no abstention statuses, no access classification, no snapshot awareness. Designed fresh against [`API_CONTRACT.md`](API_CONTRACT.md). |
| 16 | Frontend components | `frontend/src/components/*.tsx` | **DEFER** | — | Next.js/MapLibre stack mismatches thehub-pr's React/Vite frontend, and no target API exists yet to build against. Explicitly a Phase 4 (UI parity) concern, not earlier — see [`PHASED_BACKLOG.md`](PHASED_BACKLOG.md). UI *patterns* (citation highlighting in `DocumentViewer.tsx`, evidence-tier badges in `ChatPanel.tsx`, per-signal score bars in `SourcesPanel.tsx`) are noted as **DUPLICATE** reference inspiration only, not ported components. |
| 17 | Security middleware / config | `backend/app/middleware/security.py`, `backend/app/config.py` | **REJECT** | Control Plane | Auth is opt-in (`API_KEY_ENABLED: bool = False`), CORS defaults are permissive with `allow_credentials=True`, and rate-limit settings (`RATE_LIMIT_SEARCH`/`INGEST`/`ANSWER`) are defined but never wired to a route decorator — dead config presented as a working control. Replaced wholesale by extending `src/hub/mcp_runtime/auth.py`'s fail-closed `CredentialProvider`/`redact()` and `src/hub/mcp_runtime/policy.py`'s `PolicyEngine`, both already stricter than anything in this file. See [`SECURITY_MODEL.md`](SECURITY_MODEL.md). |
| 18 | Tests — pure-function unit tests (~126) | `backend/tests/test_*.py` | **ADAPT** | — | Legitimate regression fixtures for isolated logic (chunk windowing, regex coordinate extraction, MMR math, quality scoring) that don't require a live database. Portable once the functions they test are ported under their new module homes. |
| 19 | Tests — DB-backed integration paths | `backend/tests/conftest.py` and any route/pipeline test routed through the `client`/`app` fixtures | **REWRITE** | — | `conftest.py` assumes a live `spatial_rag_test` Postgres+PostGIS+pgvector database with no skip markers. The README's "126 tests passing (all non-DB unit tests)" claim explicitly *excludes* this surface — there is no verified evidence of integration-level correctness today. Must be rebuilt against the new snapshot schema, not trusted as prior coverage. See [`PARITY_GATES.md`](PARITY_GATES.md). |
| 20 | `requirements.txt` (monolithic) | `backend/requirements.txt` | **REWRITE (planned)** | — | Mixes runtime, AI/LLM, NLP, OCR, spatial, and testing dependencies in one file. Split into `rag`/`intelligence`/`spatial`/`ocr` extras per [`TARGET_REPO_TREE.md`](TARGET_REPO_TREE.md) — **specified, not executed**, in this phase. |

## Explicitly out of scope for classification

The package hygiene defects below are not components to classify — they are reasons the ZIP
cannot be merged as-is, already enumerated in [`RISK_LEDGER.md`](RISK_LEDGER.md) and
[`READINESS_REPORT.md`](READINESS_REPORT.md):

- Committed `backend/.pytest_cache/` (4 files, including `lastfailed` and `CACHEDIR.TAG`).
- Malformed literal brace-expansion directories on disk, e.g. a directory literally named
  `spatial-rag/{backend/{app/{models,ingestion,spatial,retrieval,citation,api},migrations,tests,scripts},frontend/{src/{app,components,hooks,lib},public}}`
  — bash brace expansion failed when the package was assembled, leaving nested literal-brace
  paths alongside the real `backend/`/`frontend/` directories.
- Placeholder repository reference: `README.md` line 38, `git clone https://github.com/your-org/spatial-rag`.
- Hardcoded local database credentials: `spatial_rag`/`spatial_rag` in `.env.example` and `docker-compose.yml` (which also exposes port 5432 to the host).
- Dated, provider-specific LLM model hardcoded in `config.py`: `LLM_MODEL: str = "claude-3-5-haiku-20241022"`.
