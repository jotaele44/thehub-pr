# FEX-32 P0 source-intake checkpoint — 2026-11-12

This bounded read-only evidence checkpoint registers **five P0 sources** at exact external commit and Git tree identities. It **does not** claim a 32-source freeze, source-archive download, SHA-256 file manifest, CI pass, or integration readiness.

## Verified domain overlaps
- **Spiderweb + TheHub GIS:** Spiderweb already has `scripts/source_adapters/pr_hydrography/`; TheHub has GIS Acquisition V2 including WFS `GetFeature` pagination and query receipts. Evaluate `geopr` for *incremental* discovery/export features only.
- **AguaYLuz LUMA:** Existing `scripts/fetch_luma_live.py` and source-intelligence route admission preserve endpoint bytes and SHA-256. External outage archives should be used as *historical independent manifestations*, not a second canonical scraper.
- **MoneySweep OCPR:** Existing `scripts/scrape_ocpr_contracts.py`, `scripts/ingest_ocpr_contracts.py`, `data/raw/OCPR_Contracts/` and source registries exist. Audit completeness and extraction gaps before importing external scraper code.
- **AguaYLuz hydro:** Existing source intelligence covers EIA-860M assets/capacity; PNNL EIA-923 historical generation is a distinct measurement universe. Preserve reported frequency, plant ID, annual/monthly distinctions and quality flags.

## Next bounded gates
1. Acquire original sources by exact commit; retain original bytes outside Git where necessary; write independent SHA-256 byte manifests and receipts. A Git tree SHA is **not** a SHA-256 source-byte receipt.
2. Verify external data redistribution rights and source lineage separately from repository code-license declarations.
3. Reconcile existing federation owner schemas and current exact heads before generating a patch.
4. Build only proven missing adapters or historical observation crosswalks in domain-owner repositories.
5. Require exact-head CI/security, review, qualified merge, replay and TheHub LOCKSTEP; fail closed if any required receipt is OPEN.

## Status
- Source identity: 5/5 P0 verified at default-branch commit and tree.
- Full 32-source byte freeze: OPEN.
- Source licenses: code declarations inspected for five; data rights UNVERIFIED.
- FEX-32 execution supervisor/durable AFK: UNVERIFIED.
- Source acquisition certification: WITHHELD.
