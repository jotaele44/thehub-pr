# PRII Federation Canon Ontology Charter v0.1

**Status:** Proposed baseline  
**Authority location:** `thehub-pr/federation/ontology/`  
**Adoption model:** Federation core + repo-owned modules + cross-repo contracts + generated validation schemas  
**Discovery snapshot date:** 2026-08-05  
**Normative keywords:** MUST, MUST NOT, SHOULD, SHOULD NOT, MAY

## 1. Purpose

The PRII Canon Ontology establishes stable meanings, identifiers, ownership boundaries, and compatibility rules for concepts exchanged or interpreted across the seven repositories. It prevents semantic drift while preserving producer autonomy.

The canon is not a universal model of every implementation detail. It governs only meanings that affect federation discovery, package admission, aggregation, correlation, provenance, review, reproducibility, or cross-repository interoperability.

## 2. Scope

### 2.1 Federation-wide normative scope

The federation core MAY contain a concept only when at least one condition is true:

1. It crosses a repository boundary.
2. It is used by at least two repositories with the same intended semantics.
3. TheHub validates, aggregates, correlates, projects, or reports it.
4. Semantic change could break compatibility or provenance.
5. It is required to determine authority, lifecycle, readiness, or reproducibility.

### 2.2 Repo-local scope

Each producer owns a bounded ontology module for domain concepts, local workflows, specialized classifications, and implementation mappings. Repo modules MUST extend or map to the federation core and MUST NOT redefine a core concept incompatibly.

### 2.3 Exclusions

The canon does not automatically include:

- every class, function, CLI flag, table, UI collection, or temporary implementation symbol;
- unsupported claims about real-world truth;
- labels derived only from filenames;
- coincidentally similar terms lacking semantic equivalence;
- analytical rankings owned by downstream consumers.

## 3. Semantic layers

1. **Governance layer:** ownership, authority, namespace, lifecycle, versioning.
2. **Federation protocol layer:** repository manifest, capability/command, package, stream, schema, readiness gate.
3. **Evidence layer:** source, source reference, artifact, lineage, evidence item, extraction, confidence assessment.
4. **Canonical record layer:** entity, relationship, observation, alert, transaction, funding award.
5. **Domain module layer:** producer-owned domain classes.
6. **Projection layer:** JSON Schema rows, JSONL streams, database collections, API resources, UI projections.

A projection MUST NOT silently become the definition of the semantic concept it represents.

## 4. Authority

| Object | Semantic owner | Approval |
|---|---|---|
| Federation core term | Federation governance in TheHub | TheHub owner + every materially affected producer |
| Manifest/package contract | TheHub | TheHub + at least one producer implementer |
| Producer-local term | Owning producer | Producer owner |
| Output contract | Producing repo | Producer + consuming Hub reviewer |
| Cross-producer correlation relation | TheHub | TheHub + affected producer owners |
| Shared lifecycle object | Jointly named owners | All lifecycle-stage owners |
| Deprecated mapping | Existing term owner | Consumers with active dependency |

TheHub is the aggregation and cross-producer correlation authority. It is not the owner of domain acquisition or producer-local factual interpretation.

## 5. Namespace policy

Recommended stable namespace:

- `https://prii.dev/ontology/core#`
- `https://prii.dev/ontology/contract#`
- `https://prii.dev/ontology/repo/<program_id>#`

Until a permanent domain is controlled, use compact identifiers in source files:

- `prii:Entity`
- `prii:SourceRecord`
- `contract:RepositoryManifest`
- `centinelas:Signal`
- `moneysweep:OfficialRecord`

Identifiers MUST NOT depend on local file paths, Python import paths, Git branches, or UI labels. Concept identity remains stable across compatible releases.

## 6. Term lifecycle

`observed → candidate → proposed → canonical → deprecated → retired`

- **observed:** extracted verbatim from evidence.
- **candidate:** deduplicated but not semantically approved.
- **proposed:** definition, owner, relationships, examples, and compatibility impact supplied.
- **canonical:** approved normative meaning.
- **deprecated:** retained for compatibility with replacement mapping.
- **retired:** no longer valid for new data; historical resolution remains possible.

No term may move from observed directly to canonical.

## 7. Versioning

The ontology uses semantic versioning:

- **PATCH:** editorial clarification with no semantic or validation change.
- **MINOR:** additive concept/property/relationship or optional constraint.
- **MAJOR:** identity change, meaning change, removal, cardinality change, required-field change, scale change, or authority transfer that can invalidate existing data or consumers.

Every release MUST record:

- ontology version;
- source commit pins;
- changed identifiers;
- compatibility classification;
- migrations and aliases;
- affected schemas and repositories.

## 8. Breaking-change rules

A change is breaking when it:

- changes a concept's extension or necessary conditions;
- changes identifier interpretation;
- changes a property from optional to required;
- narrows accepted values;
- changes numeric units or confidence scale;
- changes lifecycle-state semantics;
- transfers authoritative ownership;
- merges concepts that were previously distinguishable;
- splits one concept without a deterministic migration;
- changes relationship direction or cardinality.

Breaking changes require an ADR/RFC, major release, impact matrix, migration mapping, and cross-repo contract tests.

## 9. Canonical definition requirements

Every canonical term MUST have:

- stable identifier;
- preferred label;
- precise definition;
- semantic owner;
- scope and layer;
- lifecycle status;
- parent or relationship placement;
- examples and non-examples;
- source evidence at exact commit/path;
- implementation mappings;
- cardinality and scale declarations where applicable;
- compatibility notes;
- competency questions it supports.

## 10. Governance workflow

1. Open a term proposal.
2. Attach evidence from exact repository commits.
3. Run synonym, homonym, identity, ownership, cardinality, unit, and scale checks.
4. Identify affected contracts and consumers.
5. Obtain required owners' review.
6. Merge source definition.
7. Generate schemas/docs/mappings.
8. Run cross-repo validation.
9. Release and record migration effects.

## 11. CI requirements

Federation CI MUST reject:

- duplicate canonical identifiers;
- undefined references;
- repo-local redefinitions of core terms;
- unowned terms;
- invalid lifecycle transitions;
- incompatible scale or unit mappings;
- undocumented breaking changes;
- stale generated artifacts;
- producer exports that violate pinned contracts;
- canonical rows missing deterministic identity, lineage, timestamps, confidence metadata, or synthetic/test declaration when required.

## 12. Initial governance decisions

1. `PublicMatter` is a proposed jointly owned lifecycle object between Centinelas and MoneySweep.
2. Cross-producer correlations are Hub-derived relationships and MUST remain distinguishable from producer-asserted relationships.
3. `SourceRecord`, `MonitoredSource`, `SourceReference`, and `EvidenceItem` remain distinct pending explicit mappings.
4. Confidence values MUST declare scale and assessment target.
5. Raw observations and canonical observations MUST remain distinct.
6. Gate evidence/attestations MUST remain distinct from substantive domain evidence.
