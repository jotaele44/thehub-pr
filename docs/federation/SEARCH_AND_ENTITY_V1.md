# Federated search and entity composition v1 (candidate)

TheHub searches and composes records it already holds. It keeps no copy of any
producer database, runs no new identity matching, and never fills in a value a
producer did not publish. Each result and each composed item links back to the
row's Evidence Object ([`EVIDENCE_OBJECT_V1.md`](EVIDENCE_OBJECT_V1.md)).

## Federated search (`federation-search-v1`)

`hub.federated_search.FederatedSearchIndex` is an inverted word index over four
store streams: `entities`, `sources`, `observations` and `alerts`.
`GET /api/search` builds it once per store state and rebuilds it when the store
changes.

### Query parameters

| Parameter | Meaning |
|---|---|
| `q` | The query, at most 256 characters |
| `type` | `ALL`, `READING`, `FINDING`, `TIMELINE`, `SOURCE` or `ENTITY` |
| `include_synthetic` | `false` by default |
| `limit` | 1–100, default 25 |
| `cursor` | The `next_cursor` from the previous page |

An unknown type, or a limit or cursor out of range, returns 422.

### How a query matches

- **Words.** Case and Spanish accents are folded, so `san germán` matches `San German`.
- **All words must match.** Each query word must match a word in the record, either the whole word or its prefix. No partial match is ever returned.
- **Empty query.** It returns `query_status: EMPTY_QUERY` and no results.
- **Ranking.** Exact title words first, then title prefixes, then stream order (entities, sources, observations, alerts), then shorter titles.

### Result types

| Type | Records |
|---|---|
| `ENTITY` | Entity rows |
| `SOURCE` | Source rows, including OVNIS `source_document` rows |
| `READING` | Observations whose producer declares `epistemic_class: MEASURED` |
| `TIMELINE` | Alerts, and observations not declared `MEASURED` |
| `FINDING` | No producer publishes findings yet. The response says `type_status: NO_PRODUCER_EMITS_FINDINGS` instead of returning an empty list |

`READING` returns no rows from the committed aggregate. That aggregate predates the
producers' `evidence_state` declarations, and it fills once the aggregate is refreshed.

### Counts

These counts are reported, never guessed:

- `indexed_records`: the whole index.
- `matched`: rows that match the query and type.
- `excluded_synthetic`: matched rows hidden because they are synthetic.
- `total`: rows shown.

`matched = total + excluded_synthetic` always holds.

`producers` lists every producer present in the store, each `AVAILABLE` with its row
count. An in-scope producer with no indexed rows is listed as `NO_DATA`, so an absent
producer never reads as a query with no hits.

### Result fields

Each result carries:
- `evidence_id`, `stream`, `collection`, `record_id`, `kind`, `title` and `type`;
- `producers`, `synthetic` and `declared_epistemic_class` (`null` when the producer declares none);
- `source_ids`;
- `evidence_href` (`/evidence/{collection}/{record_id}`);
- `entity_href` (`/entity/{record_id}`, for entities only).

## Entity composition (`FEDERATION_ENTITY_COMPOSITION_V1`)

Schema: `schemas/federation/entity_composition.v1.schema.json`
(`urn:prii:federation:entity_composition:v1`), **CANDIDATE**.

`hub.entity_composition.compose_entity` arranges rows the store already links to one
entity, and `GET /api/entity/{record_id}` serves the result. An entity the Hub does
not hold returns 404.

### Sections of the composition

| Section | Content |
|---|---|
| `anchor` | The entity's own Evidence Object |
| `identity` | `identity_state`, `identity_scope`, `identity_basis`, `members` and `registry_status` |
| `sections` | One per producer, `AVAILABLE` or `NO_DATA`, with its relationship and linked-record counts |
| `relationships` | Relationship and correlation edges that name the entity: `direction` (`OUTBOUND`, `INBOUND` or `SELF`), `counterpart`, `edge_state`, `edge_basis` and `match_basis` |
| `linked_records` | Observations and alerts that carry the entity's `entity_id` |
| `truncated` / `limits` | At most 200 relationships and 200 linked records. Truncation is reported, never silent |

### `registry_status`

- `NOT_CONFIGURED`: the federation identity registry (`src/hub/identity_registry.py`) has no store wired into the server.
- `CONSULTED`: the caller passed a registry membership view.

### Rules

- **Identity is reported as recorded.** Proximity, timing and name similarity never join two entities (audit F13). The committed store holds three entities titled "San Juan": a municipality and two OVNIS cases. They stay three entities.
- **Edges keep their state.** An edge whose only basis is spatial proximity stays `CANDIDATE`, and a Hub correlation on a weak basis does the same.
- **An unknown counterpart stays unknown.** When the Hub does not hold a counterpart, it shows `resolved: false` with no title, and it is never filled in.

## Surfaces

| Surface | What it does |
|---|---|
| `/search?q&type&synthetic&cursor` | The search page. All of its state is in the URL |
| Command palette (Ctrl+K / Cmd+K) | Navigation derived from `NAV_GROUPS`, plus search, open evidence (`Collection/id`), open entity (`ent_…`) and jump to coordinates (`lat, lon [zN]`) |
| `/entity/:id` | The entity page |
| `/gis?lat&lon&z` | A map deep link, documented in [`../GIS_ARCHITECTURE_V1.md`](../GIS_ARCHITECTURE_V1.md) |

## Tests

| Test file | Covers |
|---|---|
| `tests/test_federated_search.py` | Folding, matching every query word, type mapping, synthetic exclusion and counts, `FINDING`, pagination |
| `tests/test_entity_composition.py` | Composition and schema validity; unresolved counterparts and weak edges |
| `tests/test_search_entity_api.py` | Both APIs against a real ingested store; 404 and 422 |
| `server/frontend/src/pages/Search.test.jsx`, `EntityPage.test.jsx` | Rendering, URL state, failure states, axe |
| `server/frontend/src/lib/commands.test.js`, `deepLinks.test.js`, `components/command/CommandPalette.test.jsx` | Palette model, keyboard use and deep-link parsing |
| `server/frontend/tests/visual/gui-parity.spec.js` | Reachability end to end |

## Twin traceability

**Implemented:**
- TWIN-012 and TWIN-082–085, 088–090 and 093–096.
- FDX-051 (entity page) and FDX-055 (command palette).

**Partial:**
- TWIN-086 and TWIN-092: readings.
- TWIN-087 and TWIN-091: findings.
- FDX-008: the resolver surfaces registry state only.
- FDX-056: deep links.

The manifests in `federation/twin/` record what remains of each partial item.
