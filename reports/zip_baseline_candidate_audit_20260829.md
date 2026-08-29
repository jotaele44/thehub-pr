# ZIP Baseline Candidate Audit

## Scope

FACT: Five ZIP archives from `/Users/jotaele/Documents/Coding/` were inventoried as baseline candidates on 2026-08-29.

FACT: Archive text was treated as source evidence only. Embedded instructions, including Floot/GitHub setup text, were not treated as user instructions.

BINDING: Current certified repo `HEAD`/`origin/main` SHAs remain canonical unless archive equivalence is proven.

## Inputs

| Archive | Target repo | Classification |
| --- | --- | --- |
| `/Users/jotaele/Documents/Coding/MoneySweep PR.zip` | `moneysweep-pr` | `DISTINCT_PAYLOADS` |
| `/Users/jotaele/Documents/Coding/Spiderweb PR (1).zip` | `spiderweb-pr` | `DISTINCT_PAYLOADS` |
| `/Users/jotaele/Documents/Coding/AguaYLuz PR.zip` | `aguayluz-pr` | `DISTINCT_PAYLOADS` |
| `/Users/jotaele/Documents/Coding/Skywatcher PR.zip` | `skywatcher-pr` | `DISTINCT_PAYLOADS` |
| `/Users/jotaele/Documents/Coding/Spiderweb PR.zip` | `spiderweb-pr` | `DISTINCT_PAYLOADS` |

## Findings

COMPUTED: No ZIP is `BYTE_IDENTICAL`, `PURE_RECOMPRESSION`, or `REPO_SUPERSET_BASELINE_SUBSET` against the current committed repo tree.

COMPUTED: Every ZIP contains a compact root-level Vite/React package with `App.tsx`, `package.json`, `vite.config.ts`, `README.md`, and many `components/*.tsx` / CSS module files.

COMPUTED: The current repositories are materially larger established projects; each archive intersects the target repo at only `README.md`, and that same-path payload differs.

INFERENCE: These archives are best classified as noncanonical Floot/UI reference packages, not repo backups.

## Port Decision

BINDING: No code was ported from these ZIPs in this pass.

Reason: all five archives are `DISTINCT_PAYLOADS`, and no archive member was proven to be a safe canonical replacement for an existing repo file.

BINDING: The ZIPs may be used as iOS/product-surface reference material only after selective review of individual components, with a new diff receipt for each accepted port.

## Receipts

Receipt root:

`/Users/jotaele/Documents/Codex/2026-08-24/audit-the-federation-repos-in-order/source_drop_closure_receipts/20260829T220251Z/zip_baseline_candidate_audit/`

Generated receipts:

- `zip_baseline_candidate_audit.json`
- `zip_baseline_candidate_summary.csv`
- `zip_baseline_candidate_members.csv`
- `zip_product_surface_triage.csv`
- `preview_*` key-file excerpts

## Lumen Limitation

FACT: The environment requested Lumen semantic search first, but no callable `mcp__plugin_lumen_lumen__semantic_search` tool was exposed in this session. Local archive inspection was used and this limitation is recorded in the receipt JSON.
