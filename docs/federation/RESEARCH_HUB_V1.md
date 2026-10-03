# Research Hub v1 (candidate)

TheHub renders the OVNIS research record at `/research`, `/research/case/:caseId` and the
`/ovnis` Reports and Show Log tabs. OVNIS owns that record: curators write it into the research
ledgers in `ovnis-pr`, whose `docs/RESEARCH_LEDGERS.md` describes the ledgers, their rules and how
they are exported. The Hub only reads the typed `entities` rows the export carries. Nothing is
generated, inferred or matched on this side.

Contract id: `federation-research-v1` (CANDIDATE, Hub-only read model).

## What the Hub reads

| Kind (`/api/research/records/{kind}`) | Exported `entity_type` | Written by |
|---|---|---|
| `topics` | `research_topic` | curators |
| `findings` | `finding` | curators |
| `hypotheses` | `hypothesis` | curators |
| `contradictions` | `contradiction` | curators |
| `adjudications` | `manifestation_adjudication` | OVNIS (`origin: COMPUTED`, always `CANDIDATE`) and curators (`origin: CURATED`, a reviewed decision) |
| `queue` | `research_queue_item` | curators |
| `episodes` | `media_episode` | curators |
| `reports` | `case_report` | OVNIS, one deterministic report per case |

## Rules the views keep

- **An empty ledger says so.** Every kind reports `kind_status: NONE_RECORDED` when the store
  holds none, and every view renders that as an explicit statement. It is never shown as an
  empty result.
- **A finding is not an established fact.** Each finding keeps the status OVNIS recorded:
  `CANDIDATE`, `ACCEPTED`, `REJECTED` or `SUPERSEDED`. `ACCEPTED` is shown as "accepted by a
  reviewer as supported by its cited sources; not an established fact".
- **Similarity never decides identity.** A computed duplicate pair is shown as
  "computed, not reviewed", together with its signals (date relation, place basis, narrative
  similarity, shared source). Only a curated adjudication records `SAME_EVENT`, `DISTINCT` or
  `UNRESOLVABLE`. No case is ever merged.
- **Distinct sources, not copies.** A topic card counts each cited source once, however many
  findings cite it (directive §44). A case reference counts as that case's exported source;
  a source-registry reference counts as that registry entry.
- **Dates and places as recorded.** The case reconstruction reuses the event timeline's rules:
  a year-only date stays a year, and only an exact timestamp carries a time.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/research` | The overview: per-kind totals, status counts, computed candidates vs curated decisions, and topic cards |
| `GET /api/research/records/{kind}` | One kind's records, paged (`status`, `origin`, `include_synthetic`, `limit` 1–200, `cursor`). Returns 422 for an unknown kind or a bad cursor |
| `GET /api/research/case/{case_id}` | A case reconstruction (FDX-016), described below. Returns 404 if the Hub does not hold the case |

A case reconstruction contains:

- the case as recorded and its source;
- its report. `report_status` is `HELD` or `NOT_HELD`: the committed fixture is a sample, so the
  report for a case may not be held;
- the report's `unresolved` list;
- every finding, hypothesis, contradiction, adjudication, queue item and episode that names the
  case.

Each candidate pair shows what the other case records, or `held: false` when the store does not
hold it.

## Where the research records also appear

- **Event timeline.** `findings_only` uses `hub.research_composition.finding_links`, so a case is
  kept when an OVNIS finding names it. See `EVENT_TIMELINE_V1.md`.
- **Search.** A `FINDING` search returns finding rows with their `finding_status`. While none
  exist it answers `type_status: NO_FINDINGS_RECORDED`. See `SEARCH_AND_ENTITY_V1.md`.

## GUI

| Route | Contents |
|---|---|
| `/research` | Tabs (in the URL as `?tab=`): Topics, Hypotheses, Contradictions, Duplicate candidates, Queue, and Assistant. The Assistant tab is the existing LLM research assistant, unchanged |
| `/research/case/:caseId` | The case reconstruction and its report viewer, including the reproducibility receipt |
| `/ovnis?tab=reports` | Every case report, each linking to its case |
| `/ovnis?tab=showlog` | Media episodes with their primary sources |

## Not built in this phase

| Item | Why |
|---|---|
| Live research swarm, web-search dispatch and real-time sourced findings (TWIN-171, 173, 174) | BLOCKED: there is no authorized research provider |
| OVNIS map counters and categories on `/gis` (TWIN-134, 145, 148) | DEFERRED to Phase 5. An OVNIS map layer needs a declared coordinate derivation, and OVNIS deliberately declares no `geometry_precision` |
| Anomaly Watch (TWIN-102) | DEFERRED until an analytical contract defines it |
| Witness/source graph (FDX-018) | PARTIAL: the case reconstruction shows source links, not a graph |
| Temporal playback (FDX-019), comparable-case finder (FDX-020) and temporal persistence classes (FDX-069) | DEFERRED, with reasons in the manifest |

## Files

| Path | Role |
|---|---|
| `src/hub/research_composition.py` | Pure read model |
| `server/backend/research_api.py` | The API |
| `server/frontend/src/pages/ResearchHub.jsx` | `/research` |
| `server/frontend/src/pages/CaseReconstruction.jsx` | `/research/case/:caseId` |
| `server/frontend/src/components/research/ResearchRecords.jsx` and `OvnisResearchTabs.jsx` | Shared views and the `/ovnis` tabs |
| `tests/test_research_composition.py`, `tests/test_research_api.py` | Backend tests |
| `server/frontend/src/pages/ResearchHub.test.jsx`, `CaseReconstruction.test.jsx` | Unit tests |
| The `research hub` block in `tests/visual/gui-parity.spec.js` | E2E tests |
