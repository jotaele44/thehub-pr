# Data Contracts — Evidence & Intelligence Engine object model

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

This document specifies the object model the Evidence Engine writes and the Intelligence Engine
reads. **No schema file is added under `schemas/` in this phase.** Every object below is a target
for a future frozen JSON Schema (`schemas/federation_*.schema.json`, added to `schemas/FROZEN.sha256`
and covered by `tests/test_schema_freeze.py`, exactly like the 17 schemas that exist today) once
Phase 1 begins — see [`TARGET_REPO_TREE.md`](TARGET_REPO_TREE.md).

## 1. Distinct retrieval object types

The uploaded spatial-rag package centers everything on one shape: `document → page → chunk →
embedding`. thehub-pr already has structured canonical streams (`entities`, `relationships`,
`funding_awards`, `transactions`, `observations`, `alerts` — see `schemas/federation_*.schema.json`).
Flattening every database record into generic prose loses that structure. Retrieval objects must
therefore keep distinct identities, even when a single query combines several of them:

| Object | Purpose | Examples |
|---|---|---|
| `CanonicalRecord` | A structured fact from a Hub producer stream — not a document. | award, transaction, observation, alert |
| `SourceArtifact` | The original uploaded/acquired file. | PDF, image, spreadsheet, webpage capture |
| `TextChunk` | An extracted, embedded passage of a `SourceArtifact`. | document passage |
| `SpatialFeature` | A geometry reference, with uncertainty (§12). | point, line, polygon, raster reference |
| `Entity` | A canonical named thing. | contractor, agency, aircraft, facility |
| `Relationship` | A directed edge between two `Entity` records, evidence-backed. | funded-by, located-at, operated-by |
| `AnalyticalClaim` | A producer- or model-generated interpretation, never a raw fact. | "Contractor X received disproportionate awards in region Y" |
| `ContradictionSet` | A group of `AnalyticalClaim`/`EvidenceItem` records that conflict. | competing values for the same fact |
| `EvidenceItem` | The unifying wrapper: any of the above, carrying provenance/tier/geometry/temporal metadata common to all evidence. | — |

`EvidenceItem` is not a tenth type competing with the other nine — it is the common envelope
(provenance, tier, access classification, snapshot membership) that `TextChunk`, `SpatialFeature`,
`CanonicalRecord`, etc. all carry. A retrieval response may combine multiple object types, but each
result retains its own type tag; nothing is coerced into a generic "search result" string.

## 2. Evidence-tier provenance (replaces inferred T1–T4)

spatial-rag's `_assign_evidence_tier()` keyword-matches chunk text against hardcoded word lists and
writes the result straight into `entities.evidence_tier`/`citations.evidence_tier` as if it were
final — see [`COMPONENT_MIGRATION_MATRIX.md`](COMPONENT_MIGRATION_MATRIX.md) row 5. That is too weak
for a system doing FOIA/legal/entity-attribution work. Evidence tier is instead a structured record:

```
tier_value           # 1-4, the assigned tier
tier_source          # where the assignment came from
tier_rule_id         # the specific rule/model version that produced it
tier_assigned_by     # producer_id | rule_engine | human reviewer id
tier_assigned_at     # ISO timestamp
tier_confidence      # 0.0-1.0
tier_review_status   # machine_provisional | human_reviewed | producer_certified
```

Priority order when multiple tier assignments exist for the same item:

1. `producer_certified` — the producer itself asserts the tier at export time.
2. `source-registry rule` — a Hub-side deterministic rule keyed to a known source type.
3. `manual adjudication` — a human reviewer's explicit decision.
4. `provisional machine suggestion` — anything produced by a keyword/ML classifier (this is what
   spatial-rag's current mechanism becomes: an *input* to tier assignment, never the tier itself).

**A machine-inferred tier is always `tier_review_status = machine_provisional`.** It is never
silently promoted to `human_reviewed` or `producer_certified`. `EvidenceTierBadge`-style UI (as seen
in spatial-rag's `ChatPanel.tsx`) must render provisional tiers visibly differently, not blend them
with certified ones.

## 3. Claim ledger (replaces sentence-level citation gating)

spatial-rag's citation engine drops any LLM-generated sentence lacking a `[N]` reference — useful,
but insufficient: it discards ungrounded text without ever recording *what was claimed and why it
was trusted or not*. Every final claim produced by the Intelligence Engine is a structured record,
and the rendered answer is a presentation of the claim ledger, not the primary analytical artifact:

```json
{
  "claim_id": "claim_...",
  "claim_text": "...",
  "claim_type": "fact|inference|hypothesis|comparison",
  "supporting_evidence_ids": [],
  "contradicting_evidence_ids": [],
  "producer_ids": [],
  "confidence": 0.0,
  "confidence_basis": [],
  "snapshot_id": "...",
  "model_id": "...",
  "prompt_version": "...",
  "generated_at": "..."
}
```

`supporting_evidence_ids` and `contradicting_evidence_ids` reference `EvidenceItem` ids directly —
this is what lets a `ContradictionSet` (§1) be assembled mechanically from the ledger rather than
inferred after the fact. `confidence_basis` is a list of named signals (e.g. `["tier_1_source",
"cross_producer_corroboration", "high_retrieval_score"]`), not a bare float with no explanation.

## 4. Retrieval profiles (replaces fixed 0.4/0.4/0.2 weights)

spatial-rag hardcodes `bm25_weight=0.4, vector_weight=0.4, spatial_weight=0.2` independently in three
places (`RetrievalParams` dataclass, `SearchRequest` Pydantic schema, and `config.py` — the last of
which isn't even wired to the scoring SQL). A single fixed weighting is inappropriate across query
types (exact identifier lookup vs. spatial investigation vs. chronology all need different balances).
Replaced with a named, versioned `RetrievalProfile` object:

```
profile_id
lexical_weight
vector_weight
spatial_weight
temporal_weight
graph_weight
source_authority_weight
quality_weight
freshness_weight
hyde_enabled            # boolean, defaults false (see SECURITY_MODEL.md)
weights_sum_to_1         # contract invariant, enforced at write time — same check spatial-rag
                          # already does in RetrievalParams.__post_init__, kept as a validation rule
                          # rather than a hardcoded default
```

Suggested starter profiles (query planner may recommend one; the **selected profile is always
logged** against the `Claim`/`AnalyticalClaim` that resulted, per §3):

| Profile | Lexical | Vector | Spatial | Graph |
|---|---|---|---|---|
| Exact identifier | High | Low | None | Medium |
| Contract search | High | Medium | Low | Medium |
| Spatial investigation | Medium | Medium | High | Medium |
| Entity lineage | Medium | Medium | Low | High |
| Narrative comparison | Medium | High | Low | Medium |
| Chronology | High | Medium | Medium | High |

Freshness must never automatically outrank authoritative older evidence — `freshness_weight` is one
signal among eight, not a tiebreaker applied after the fact.

## 5. Contradiction-preserving entity resolution

Entity extraction and co-occurrence (as done today by spatial-rag's spaCy NER + `entity_edges` table,
and by thehub-pr's own `src/hub/correlate.py` normalized-name/external-id/location/date matching) are
necessary but not sufficient — neither pipeline treats a merge decision as reversible. Every merge is
instead one of these explicit, evidence-backed records:

```
entity_match_candidate      # a proposed match, not yet decided
entity_identity_decision    # the adjudicated outcome for a candidate
relationship_assertion      # a directed, evidence-backed edge (may be corroborates | contradicts | supersedes)
canonical_entity            # the merged identity, if a merge was accepted
alias                       # a name variant attached to a canonical_entity
rejected_match               # a candidate explicitly declined, with reason code, kept for audit
superseded_decision          # a prior decision later reversed, kept for audit (never deleted)
```

**Never merge solely because of:** similar names, shared address, shared coordinates, co-occurrence,
or embedding similarity. Each of those may produce an `entity_match_candidate`; only an explicit
reason code plus supporting evidence produces an `entity_identity_decision`.

`schemas/federation_relationship.schema.json`'s `relationship_type` field is confirmed free-form
(`{"type": "string"}`, not a closed enum), so adding `corroborates`/`contradicts`/`supersedes` values
is schema-unblocked. The resolution *logic* — deciding when to assert one of those types instead of
silently merging — is new-build; `src/hub/correlate.py` is a useful shape reference (grid-indexed
haversine, normalized-name matching) but does not implement contradiction preservation today.

## 6. Geographic uncertainty

spatial-rag's `SpatialEnricher` extracts only exact regex-matched coordinates (DMS/decimal); a
`geocode_place()` function exists but is never invoked, and DB columns for uncertainty
(`bbox_min/max_lat/lon`, added in migration `002_upgrades.sql`) exist but are never populated. A
municipality mention must never be displayed as an exact facility coordinate. `SpatialFeature`
supports the full geometry-type range — exact point, geocoded point, centroid, polygon, corridor,
radius, bounding box, approximate locality, redacted location, uncertain geometry — and every
instance carries:

```
geometry_source           # regex_extraction | geocoder | manual | producer_supplied
geometry_method
horizontal_accuracy_m
spatial_precision_class   # exact | approximate | locality | redacted
crs
geocoder                  # which service, if any (see DEFER note on geocode_place() in the matrix)
geocoded_at
manual_review_status
```

## 7. Document-page evidence geometry

thehub-pr today has no document/PDF ingestion at all. spatial-rag's DB has `pages.page_number`,
`mentions.start_char`/`end_char`, and `pages.ocr_confidence`, but no OCR bounding-box storage, no
rendered-page hash, and no source-file hash distinct from the content-addressed `doc_id`. Every
`TextChunk`/`SourceArtifact` pair citable from an answer must carry:

```
page_number
text_offsets            # start_char, end_char
ocr_bounding_box         # per-token or per-line box, when OCR-derived
extraction_method        # native_text | ocr
ocr_confidence
rendered_page_hash       # hash of the rendered page image, for viewer reproducibility
source_file_hash         # distinct from any content-addressed record id
```

A future Document Viewer should be able to highlight the exact supporting passage or OCR region a
citation points to, not just the source document as a whole.

## 8. Temporal model

Neither spatial-rag nor thehub-pr has a first-class temporal retrieval component today — spatial-rag
has lexical/vector/spatial retrieval with no distinct temporal engine, and thehub-pr's canonical
streams carry a single `created_at`/lineage timestamp, not a temporal model. Every `EvidenceItem` and
`CanonicalRecord` carries:

```
event_ts            # when the underlying fact occurred
publication_ts       # when it was published/disclosed
effective_ts         # when it took legal/operational effect
observation_ts        # when a producer observed it
ingestion_ts          # when the Hub ingested it
supersession_ts        # when a later record superseded it, if any
valid_from / valid_to  # for records with a bounded validity window
date_precision         # day | month | year | uncertain_range
timezone
```

`temporal_weight` in the `RetrievalProfile` (§4) and `freshness_weight` are separate signals —
temporal *relevance* to the query is not the same as *recency*, and neither should silently outrank
`source_authority_weight` for an older but authoritative record.

## 9. Abstention contract

spatial-rag returns a single generic low-confidence answer when evidence is thin. The Intelligence
Engine must instead distinguish and return one of these statuses explicitly — never collapse them
into one "low confidence" response:

```
ANSWERED
PARTIALLY_ANSWERED
INSUFFICIENT_EVIDENCE
CONTRADICTED
OUT_OF_SCOPE
SNAPSHOT_INCOMPLETE
RETRIEVAL_FAILURE
GENERATION_FAILURE
```

The response shape (`AbstainResponse`) carries the status, a human-readable reason, any
`partial_evidence_ids` gathered before abstaining, and — when `status = CONTRADICTED` — a reference
to the relevant `ContradictionSet`. This is a data contract as much as an API contract; see
[`API_CONTRACT.md`](API_CONTRACT.md) for how it's returned over the wire.

## 10. Reproducibility fields

spatial-rag hardcodes one Anthropic model string (`claude-3-5-haiku-20241022`) throughout
`config.py`. A model upgrade must never silently alter historical answers. Provider abstractions:

```
LLMProvider
EmbeddingProvider
RerankerProvider
OCRProvider
GeocoderProvider
```

Every analytical run (every `AnalyticalClaim`/`Claim` generated) records:

```
provider
model
model_revision           # where available
prompt_template_version
system_policy_version
temperature
retrieval_configuration    # the RetrievalProfile id used
snapshot_id
context_evidence_ids
```

This is the same information already implied by §3's `model_id`/`prompt_version`/`snapshot_id`
fields on `Claim` — this section states the provider-abstraction requirement that makes those fields
meaningful across model upgrades rather than tied to one hardcoded string.

## 11. Access classification

Every object above additionally carries an access-classification tag, enforced identically across
search, map, exports, and model context — specified in full in [`SECURITY_MODEL.md`](SECURITY_MODEL.md)
§ Access classifications; referenced here because it is a field on every object, not a separate model.

## Ownership summary

| Object | Written by | Read by |
|---|---|---|
| `SourceArtifact`, `TextChunk`, `EvidenceItem` (ingest-time fields), tier assignment inputs | Evidence Engine | Evidence Engine (mutable), Intelligence Engine (certified snapshot only — see [`DATABASE_BOUNDARIES.md`](DATABASE_BOUNDARIES.md)) |
| `CanonicalRecord` | Existing `src/hub/aggregate.py`/`correlate.py` pipeline (unchanged) | Evidence Engine (folds into snapshot), Intelligence Engine (via snapshot) |
| `Entity`, `Relationship`, `entity_identity_decision`, etc. | Evidence Engine (resolution logic), human reviewers (adjudication) | Intelligence Engine (via snapshot) |
| `RetrievalProfile` | Control Plane (registered profiles) | Intelligence Engine (selects/logs) |
| `AnalyticalClaim` / `Claim`, `ContradictionSet`, `AbstainResponse` | Intelligence Engine | Presentation layer only — never re-ingested as evidence |
| Snapshot manifests | Control Plane | Both engines (Evidence Engine writes into next snapshot; Intelligence Engine reads only `ACTIVE` snapshots) |
