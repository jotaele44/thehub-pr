# Event timeline v1

`/timeline` is the chronological ledger of the OVNIS case corpus (directive §13;
Twin rows TWIN-003 and TWIN-180–200). OVNIS owns the corpus. TheHub orders the case
observations its store already holds, and never infers anything about them.

## API

`GET /api/timeline` (`server/backend/timeline_api.py`, over `hub.event_timeline`).

| Parameter | Meaning |
|---|---|
| `sort` | `oldest` (default) or `newest` |
| `category` | Repeatable. OVNIS `object_type` values, such as `UAP`, `USO`, `Lights` or `Mutilation` |
| `findings_only` | Only cases that an OVNIS finding names |
| `include_synthetic` | `false` by default |
| `limit` | 1–200, default 50 |
| `cursor` | The `next_cursor` from the previous page |

An unknown sort, a bad cursor or a limit out of range returns 422.

## Rules

- **Dates.** A date is shown exactly as OVNIS recorded it. The precision comes from the
  producer's `evidence_state.temporal_precision`, or failing that from the shape of the
  recorded date. A year-only case stays a year: no day, month or time is invented to sort
  or display it.
- **Ordering.** "Oldest first" sorts on the period start. On the same start, a coarser
  record comes first (`1967` before `1967-03` before `1967-03-02`). "Newest first"
  reverses that.
- **Undated cases** are kept, listed last and counted in `undated`.
- **Places.** Geography is source-bounded: the municipality when the source gives one,
  otherwise the source's own location text. Coordinates are not part of the event and are
  never required.
- **Titles.** OVNIS has no title field. The title is the source's location text, falling
  back to the case id.
- **Narrative.** The case's ledger `description`, exported by ovnis-pr. A case without one
  says so.
- **Findings.** `findings_only` keeps only cases that an OVNIS finding names. Until OVNIS
  publishes findings through its research ledger, `findings_status` is
  `NO_FINDINGS_RECORDED` and the mode shows nothing. It never treats a case as a finding.
- **Counts.** The response reports what is loaded, never guessed:

  | Field | Meaning |
  |---|---|
  | `loaded_events` | Events in the store |
  | `matched` | Events that match the filters |
  | `undated` | Matched events with no parseable date |
  | `excluded_synthetic` | Synthetic events hidden by default |
  | `findings_total` | OVNIS findings recorded |

  Each category is listed with its count. The committed fixture is a bounded sample, so
  these are the store's counts, not federation totals.

## Events

Each event carries:

- **Identity:** `case_id`, `title`, `category` and `environment`.
- **Date:** `date` (as recorded), `time` (only for `EXACT_TIMESTAMP`),
  `temporal_precision` and `era` (the decade of the recorded year).
- **Content:** `narrative`, `place` and `evidence_tier`.
- **Source:** the cited source's name, URL and Evidence Object link.
- **Links:** `evidence_href` (the observation's Evidence Object) and `entity_href` (the
  case's composition).

## Tests

| Test file | Covers |
|---|---|
| `tests/test_event_timeline.py` | Precision, ordering, undated cases, synthetic exclusion, categories, findings mode, pagination |
| `tests/test_timeline_api.py` | The API against a real ingested store, provenance links, 422s, route ordering |
| `server/frontend/src/pages/Timeline.test.jsx` | Rendering, URL state, empty and error states, axe |
| `server/frontend/tests/visual/gui-parity.spec.js` | Reachability from navigation |
