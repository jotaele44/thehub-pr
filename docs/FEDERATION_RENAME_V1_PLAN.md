# Federation rename v1 — identity migration plan (Phase 0)

Status: **IDENTITY_FROZEN**. No project has been renamed. Public branding is BLOCKED pending naming due diligence.

Artifacts live in `federation/rename/v1/`:
`rename_manifest.json` (FEDERATION_PROJECT_RENAME_MANIFEST_V1), `project_identity_registry.json`,
`alias_registry.json` (old → new only), `pre_rename_snapshot.json` (R0 freeze, per-repo HEAD/tree/GitHub repo id), `baseline_static.json` (STATIC_ONLY test counts; real denominators still OPEN),
`reference_inventory.json` (layer-classified old-name references; per-occurrence disposition still UNRESOLVED),
`output_hashes.json`.

## Mapping
| Stable project id (frozen `program_id`) | Old | New | Type |
|---|---|---|---|
| federation.project.thehub_pr | TheHub-PR | Batey-PR | RENAME (migrated last) |
| federation.project.moneysweep_pr | MoneySweep-PR | Chanchullos-PR | RENAME |
| federation.project.centinelas_pr | Centinelas-PR | Cronos-PR | RENAME + FUNCTIONAL REBUILD |
| federation.project.skywatcher_pr | Skywatcher-PR | Pitirre-PR | RENAME |
| federation.project.spiderweb_pr | Spiderweb-PR | Borikén-PR | RENAME |

AguaYLuz-PR, OVNIS-PR and Mucaro-AI are unchanged. Order: Borikén → Chanchullos → Pitirre → Cronos → Batey.

## Rules
- Names change, stable ids do not; ids bind to the existing `program_id` and the immutable GitHub repository id.
- Historical receipts and archived reports keep the name in force when produced (RAW is never rewritten).
- Legacy env-var names, DB files and storage paths are not renamed in the first migration.
- Scope is GitHub code only; hosting/deployment layers are out of scope by owner decision.

## Decisions
- **Pitirre charter (owner, 2026-10-06): ADOPT** `ADR_PITIRRE_DOMAIN_MODEL_v0_1` in skywatcher-pr (AIR | LAND | WATER | SPACE).
  Open boundary: the ADR claims temporal-state/replay semantics, which overlap Cronos; reconcile before Pitirre reaches CODE_MIGRATED.
  The ADR's frozen SHA (`afbf2f8`) has drifted; this plan's freeze is `skywatcher-pr@2100e65`.

## Known risks
- Registry and lockstep bindings currently key on name strings (`source_app: "skywatcher"`); stable-id resolution must land before consumers are renamed.
- ~97.5k of 118.7k tracked references are provenance paths (default RETAIN_HISTORICAL); ~21.3k are actionable.
- External name/trademark/domain/package clearance is OPEN (note: "Boriken" appears as a vendor name in moneysweep data).
