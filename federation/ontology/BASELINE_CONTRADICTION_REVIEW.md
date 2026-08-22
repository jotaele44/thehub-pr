# Contradiction, Ownership, Identity, Cardinality, Compatibility, and Blind-Spot Review

## High-priority contradictions

| ID | Conflict | Evidence pattern | Decision |
|---|---|---|---|
| C-001 | Confidence scale | Hub schemas: 0–1; Centinelas doctrine: 0–100 | Introduce `ConfidenceAssessment(value, scale, target, method, assessor)`; prohibit bare cross-repo confidence values in ontology v1 |
| C-002 | Source homonym | provenance row vs monitored registry source vs source reference | Split into `SourceRecord`, `MonitoredSource`, `SourceReference` |
| C-003 | Observation homonym | Centinelas raw intake stage vs canonical sensor/airspace event | Split `RawObservation` and `CanonicalObservation` |
| C-004 | Relationship authority | producer-emitted relation vs Hub-derived cross-producer correlation | Split `AssertedRelationship`, `DerivedRelationship`, and `Correlation` |
| C-005 | Evidence homonym | substantive claim support vs validation/gate evidence | Split `EvidenceItem`, `ValidationEvidence`, and `Attestation` |
| C-006 | Alert projection | producer alert, canonical alert row, and `GovernanceAlerts` UI collection | Keep semantic event and UI projection separate |
| C-007 | Manifest/schema versioning | schema identifier is v1 but no independent ontology version is declared | Add `ontology_version` and `contract_version` separately |
| C-008 | Lineage duplication | same lineage shape repeated in multiple JSON Schemas | Extract one shared lineage schema/ontology definition |
| C-009 | Entity typing | open string `entity_type` with repo-specific taxonomies | Core owns Entity; each repo owns controlled subclasses/mappings |
| C-010 | Lifecycle status | readiness, alert, review, signal, and promotion states use unrelated enums | Model scoped state machines; do not create one universal `status` enum |

## Ownership review

- **Confirmed:** Producers own acquisition and local normalization.
- **Confirmed:** TheHub owns discovery, federation schemas, package validation, aggregation, and cross-producer correlation.
- **Confirmed:** SkyWatcher owns FR24/active airspace; SpiderWeb retains spatial bridge material.
- **Confirmed:** Centinelas owns pre-officialization signals; MoneySweep owns post-officialization public-money records.
- **Proposed joint object:** `PublicMatter`.

## Identity review

Canonical IDs currently use typed deterministic prefixes such as `src_`, `ent_`, `rel_`, and `obs_`. These are transport identifiers. The ontology MUST distinguish:

1. record identity;
2. real-world entity identity;
3. external identifier;
4. source-document identity;
5. semantic concept identity.

No two of these may be merged merely because one field references another.

## Cardinality review

Current Hub schemas generally require one `source_id`, one confidence value, one lineage object, and timestamps per row. Domain reality may require:

- multiple evidence items;
- multiple source documents;
- multiple confidence assessments by different methods;
- bounded or uncertain times;
- multiple locations or geometries;
- relationship assertions with multiple supporting sources.

The ontology should permit these richer semantics even when a transport schema remains denormalized.

## Compatibility review

The proposed core is additive if implemented first as mappings and generated documentation. It becomes breaking if existing JSONL fields are renamed or their scale/meaning changes without adapters. Initial implementation should therefore:

1. keep current JSONL schemas;
2. add ontology identifiers and mapping files;
3. generate compatibility reports;
4. migrate schemas only in a major contract release.

## Blind spots

- Full source-code symbol extraction across all seven repos is not complete.
- Test assertion vocabulary has not been exhaustively indexed.
- Some README doctrine may exceed current implementation.
- Producer manifests expose open-ended `source_truth` and `canonical_outputs` objects that require field-level inventory.
- No permanent namespace domain was verified.
- No formal CODEOWNERS-based ontology approval group was verified.
- Domain enum coverage remains incomplete.
- Existing historical/legacy schemas may contain contradictory terms not represented in the baseline.

## Approval status

**Do not approve the ontology as canonical yet.**  
Approve the charter and inventory protocol; treat the minimal core and modules as proposed inputs to a second, source-symbol-level pass.
