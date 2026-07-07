# Federation Topology — Centinelas → MoneySweep + SpiderWeb → Hub

This document declares how four PRII producers are **grouped and connected** to
carry a single end-to-end flow: pre-officialization intelligence from Centinelas
is turned into *located finance* by the MoneySweep + SpiderWeb pair, and the
result is aggregated and correlated by the Hub.

It complements `registry/producers.yaml` (the machine-readable producer list) and
`ARCHITECTURE.md` (the federated-engines / single-hub doctrine). It does not
change any Hub code — the Hub consumes the result through its existing
aggregate → correlate → ingest pipeline.

## The grouping

```
  ┌─────────────────────┐
  │  INTEL SOURCE        │   centinelas-pr
  │  (pre-official)      │   classify → route FINANCIAL/POLITICAL to the anchor
  └──────────┬──────────┘
             │  intake/ drop  (JSON payload; finance/location enrichment)
             ▼
  ┌───────────────────────────────────────────────────────────────┐
  │  FINANCE / LOCATION FUSION PAIR                                 │
  │                                                                │
  │   moneysweep-pr  (ANCHOR)  ───bundle───►  spiderweb-pr          │
  │   turns signals into pre-official          scores the bundle    │
  │   located-finance candidates and           into a municipality-│
  │   emits the contract-finance bundle        scored overlay      │
  └──────────────────────────────┬────────────────────────────────┘
                                 │  canonical federation packages
                                 ▼
  ┌─────────────────────┐
  │  AGGREGATION         │   thehub-pr
  │                     │   fetch → aggregate → correlate → ingest
  └─────────────────────┘
```

- **Intel source — `centinelas-pr`.** Classifies public-interest items into six
  domains and drops JSON payloads into each sibling repo's `intake/` folder.
  `FINANCIAL`/`POLITICAL` route to MoneySweep (the money anchor); every item also
  goes to the Hub.
- **Finance/location fusion pair — `moneysweep-pr` (anchor) + `spiderweb-pr`.**
  MoneySweep ingests the Centinelas drops as *pre-official located-finance
  candidates*, then emits a contract-finance bundle that SpiderWeb scores into a
  municipality-tiered overlay. This pairing is the "assign finances to a location"
  step.
- **Aggregation — `thehub-pr`.** Discovers, validates, aggregates, and correlates
  every producer's canonical export. The located pre-official finance correlates
  across producers by municipality/proximity with no Hub code change.

## Seam contracts

### 1. Centinelas → MoneySweep (intake drop)

- **Producer:** `centinelas-pr` `src/centinelas/route/{router,dispatch}.py`.
- **Transport:** file-drop into `<CENTINELAS_REPOS_DIR>/moneysweep-pr/intake/<item_id>.json`.
- **Contract:** `centinelas-pr/src/centinelas/route/contracts/moneysweep.schema.json`.
  The MoneySweep-bound payload additionally carries pre-officialization
  finance/location enrichment (`municipalities`, `agencies`, `estimated_value`,
  `signal_stage`, `beat`) when the classifier extracted it; MoneySweep re-derives
  municipality from `title`/`body_text` when absent.

### 2. MoneySweep consumes the drop → located finance candidates

- **Consumer:** `moneysweep-pr/moneysweep/runtime/centinelas_intake.py` +
  `scripts/ingest_centinelas_signals.py`
  (hub command `ingest_centinelas`; also `run_all.py --ingest-centinelas`).
- **Behavior:** keeps `FINANCIAL`/`POLITICAL` drops, resolves each to a PR
  municipality with the deterministic `moneysweep.runtime.geo_attribution`, and
  emits export-stream rows (`funding_awards.jsonl`) with a `location` block,
  `source_id="centinelas-pr"`, `signal_stage="pre_official"`, `synthetic=false`,
  and lineage. Registered as source `centinelas_pre_official_signals`.

### 3. MoneySweep → SpiderWeb (contract-finance bundle)

- **Producer:** `moneysweep-pr/scripts/build_contract_finance_bundle.py`
  (hub command `build_contract_finance_bundle`). Reuses
  `scripts/run_contract_finance_geo_reasoning.py` for row-level geo reasoning.
- **Bundle (the handoff):** `outputs/contract_finance/`
  - `contract_awards.geojson`, `financial_flows.geojson`
    (`properties`: `record_id`, `entity_id`, `amount`, `date`,
    `municipality_code`, `municipality_name`, `feature_type`, `source_layer`,
    `source_id`),
  - `municipality_funding_density.csv` (one clean row per municipality),
  - `contract_finance_ingest_report.json` (producer, `export_contract_version`,
    and a `centinelas_pre_official` provenance block).

### 4. SpiderWeb scores the bundle (assign finances to a location)

- **Consumer:** `spiderweb-pr/readiness/contract_finance_layer.py`
  (`build_contract_finance_layer`) via `scripts/build_contract_finance_layer.py --input <bundle>`.
- **Output:** `contract_finance_scored_overlay.geojson` (per-feature
  `spiderweb_score` + `evidence_tier`) and `contract_finance_layer_report.json`,
  which surfaces the Centinelas pre-official contribution
  (`centinelas_pre_official.feature_count` / `located_feature_count`, plus the
  producer-reported block).

### 5. → Hub (aggregate → correlate → ingest)

- MoneySweep's `funding_awards`/`transactions` (including Centinelas-derived
  pre-official candidates, each carrying a `location` block) and SpiderWeb's
  observations/overlay reach the Hub through their canonical federation packages.
- `src/hub/correlate.py` links cross-producer entities by
  `location.municipality` (`_municipality`) and by lat/lon proximity
  (`correlate_spatial`), so the located pre-official finance correlates with
  officialized money and spatial records **without any Hub code change**.

## Provenance & guardrails

- Centinelas-derived rows are **pre-official**, not officialized money:
  `signal_stage="pre_official"`, `synthetic=false`, `source_id="centinelas-pr"`,
  full lineage. Downstream consumers can filter or weight them accordingly.
- Location attribution is enrichment, never a filter: unresolved rows are kept
  with an empty `municipality_code` and `attribution_confidence="unknown"`.
