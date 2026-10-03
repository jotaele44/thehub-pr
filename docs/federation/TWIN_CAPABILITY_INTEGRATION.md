# Twin capability integration

TheHub owns the census that maps the Twin reference application
(`twin.parapsychlab.io`) onto the Federation. The reference is used only as a
**capability** reference. Its styling, its Skinwalker Ranch content and its
category labels are not copied.

## Two separate denominators

| Manifest | Path | What it counts |
|---|---|---|
| `TWIN_OBSERVED_CAPABILITY_MANIFEST_V1` | `federation/twin/TWIN_OBSERVED_CAPABILITY_MANIFEST_V1.json` | Exactly the 223 elements in the operator's frame-by-frame census of a 36.37 s recording, each with one Federation disposition |
| `FEDERATION_TWIN_DERIVED_EXTENSION_MANIFEST_V1` | `federation/twin/FEDERATION_TWIN_DERIVED_EXTENSION_MANIFEST_V1.json` | Federation-native extensions inspired by the reference. Every entry has `origin: FEDERATION_DERIVED` |

A derived entry is never counted as a Twin capability. The validator rejects
any derived name or alias that repeats an observed element.

## Evidence for the observed census

| `evidence_status` | Meaning |
|---|---|
| `RECORDED` | The element was rendered or exercised in the recording |
| `INFERRED_FROM_LABEL` | Only a navigation label or descriptive text was seen; the workspace body was not opened. This applies to rows 211–217 (Archive semantics taken from the Data page), 221 and 222 |
| `LIVE_VERIFIED` | Not used. A crawler of the live endpoint sees only the application shell |

`live_bundle_corroboration` records the SHA-256 of each client bundle file
captured on 2026-09-25, plus the literal label found per row. It is T1
technical corroboration only. It never changes `evidence_status` and never
adds a row. Bundle modules that are not in the recording, such as the
password-gated visitor analytics module, are listed under
`unrecorded_bundle_modules` and are not counted.

## Disposition fields

| Field | Values and rules |
|---|---|
| `canonical_repo` / `producer` | Exactly one in-scope repo per row, and the two fields must be equal. `centinelas-pr` is out of scope |
| `implementation_status` | `EXISTING` and `EXTEND` must cite `existing_equivalent`. `NEW` records `search_terms_without_equivalent`. `NOT_APPLICABLE` requires a `rationale`. `BLOCKED` requires a `blocker` |
| `canonical_gui_home` | Always a TheHub route, because TheHub is the only product surface (ADR 0001). `producer_diagnostic_gui` names the producer's diagnostic surface |
| `phase` | 1–10 of the Federation Max Implementation Directive |
| `delivery_state` | One of the values below, and it must agree with `implementation_status` |

`delivery_state` values:

- `ALREADY_PRESENT`
- `SCHEDULED_THIS_RUN`, `PARTIAL_THIS_RUN` and `IMPLEMENTED_THIS_RUN`. These three record run 1 and are only valid for Phases 1–3.
- `SCHEDULED_RUN_2`, `PARTIAL_RUN_2` and `IMPLEMENTED_RUN_2`. These record run 2 and are only valid for Phase 4 (OVNIS). A later run never rewrites what an earlier run recorded.
- `DEFERRED`
- `BLOCKED`
- `NOT_APPLICABLE`

### Category labels

Category labels come from Federation data. For example, the Twin "Cattle"
category maps to OVNIS's own `Mutilation` object type. Twin-only categories
with no Federation data behind them are `NOT_APPLICABLE`: Portal, Mesa,
Hitchhiker, History, and drilling correlations.

## Validation

```bash
python3 scripts/validate_twin_manifests.py          # CI check
python3 scripts/validate_twin_manifests.py --write  # refresh reconciliation blocks
pytest tests/test_twin_capability_manifests.py
```

The `reconciliation` block in each manifest is derived from the rows by
`hub.twin_manifest` and is never edited by hand. The observed census counts as
closed only when all of the following hold:

- `OBSERVED_TOTAL = 223`
- `ACCOUNTED_FOR = 223`
- `UNACCOUNTED = 0`

A closed census does **not** mean all 223 capabilities are implemented. It
means each one has an explicit disposition backed by evidence.

## Run 1 record

[`TWIN_RUN1_RECONCILIATION.md`](TWIN_RUN1_RECONCILIATION.md) is the closing record for run 1 (Phases 1–3). It lists the delivery counts, every pull request and merged SHA, and the producer verification. It also records:

- MoneySweep's BLOCKED status;
- why the evidence contracts remain CANDIDATE;
- the leads logged for later phases.

## Run 2 (Phase 4, OVNIS)

Run 2 delivers Phase 4. Its records are marked `IMPLEMENTED_RUN_2`, `PARTIAL_RUN_2` or a reasoned `DEFERRED`.

| Delivery | Document |
|---|---|
| Event timeline (`/timeline`) | [`EVENT_TIMELINE_V1.md`](EVENT_TIMELINE_V1.md) |
| Research Hub (`/research`), case reconstruction (`/research/case/:caseId`), and the `/ovnis` reports workspace and show log | [`RESEARCH_HUB_V1.md`](RESEARCH_HUB_V1.md) |

OVNIS owns the research record. Its ledgers, validator, duplicate candidates and case reports are documented in the [ovnis-pr research-ledger doc](https://github.com/jotaele44/ovnis-pr/blob/main/docs/RESEARCH_LEDGERS.md).
