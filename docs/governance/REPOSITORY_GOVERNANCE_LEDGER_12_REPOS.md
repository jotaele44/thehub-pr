# Twelve-Repository Governance Ledger

**Audit date:** 2026-07-27
**Scope:** all repositories visible through the authenticated GitHub installation used for the audit, at audit time.

| Repository | Portfolio class | ROAD_TO_100 status | Governance disposition |
|---|---|---|---|
| `moneysweep-pr` | Federation producer | Existing detailed ledger + normalized companion proposed | Governed; non-production diagnostic; live gate false |
| `spiderweb-pr` | Federation producer | Existing detailed ledger + normalized companion proposed | Governed; 85% restricted to core-pipeline scope |
| `aguayluz-pr` | Federation producer | Existing detailed ledger + normalized companion proposed | Governed; live with stale-outage provenance caveat |
| `ovnis-pr` | Federation producer | Existing detailed ledger + normalized companion proposed | Governed; reviewed corpus live, recurrent acquisition incomplete |
| `skywatcher-pr` | Federation producer | Existing detailed ledger + normalized companion proposed | Governed; provisional score; live gate false; PR #100 private gates unresolved |
| `centinelas-pr` | Federation producer | Existing detailed ledger + normalized companion proposed | Governed; generic engine distinct from intended PR product |
| `thehub-pr` | Federation Hub | Existing detailed ledger + normalized companion + portfolio authority proposed | Governed; 90% applies to local Hub code only |
| `Aerospace-Intelligence-Tool` | Legacy/independent candidate | No standard ledger found | Owner disposition required: adopt policy, archive, or identify successor |
| `Faces-Font` | Utility/empty repository | No standard ledger found | Classify as non-product or archive; do not invent completion percentage |
| `minecraft_seed` | Independent project | No standard ledger found | Adopt policy only if promoted into active product governance |
| `Puerto-Rico-Airspace-Intelligence-Tool` | Legacy airspace source/candidate | No standard ledger found | Identify whether SkyWatcher supersedes it; then archive or mark legacy source |
| `Puerto-Rico-Integrated-Intelligence-System` | Legacy integration candidate | No standard ledger found | Identify whether TheHub supersedes it; then archive, mark legacy, or adopt policy |

## Accounting

- Repositories accounted for: **12/12**.
- Federation repositories with a detailed ROAD_TO_100 ledger: **7/7**.
- Repositories outside the standard ledger: **5/5 explicitly dispositioned**.
- Silent omissions: **0**.

## Rules for the five non-standard repositories

No completion percentage is assigned until a product boundary, evidence denominator, and current owner disposition exist. Repository size, age, or the presence of code is not sufficient to infer product status.

A future governance PR for any of the five must include:

1. active, legacy, experimental, non-product, or archived classification;
2. successor repository where applicable;
3. intended product boundary;
4. current verified commit;
5. executable test/validation baseline;
6. real-data and operational-readiness evidence;
7. normalized ROAD_TO_100 fields if classified as active.

This ledger authorizes no code, archive, rename, visibility, or status changes in the five repositories.
