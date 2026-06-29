# Spatial Overlay Join Rules

## Purpose

The Puerto Rico federation uses a shared cell-level baseline grid to prevent spatial-format drift across producer repos and the hub. Every domain-specific geography must resolve to the same `Cell_ID` index before cross-repo promotion.

## Join hierarchy

| Layer | Required key | Role |
|---|---|---|
| Baseline grid | `Cell_ID` | Canonical federation spatial index |
| Civil geography | `municipality`, `barrio`, `Cell_ID` | Local government and place context |
| Infrastructure geography | `utility_zone`, `watershed`, `facility_id`, `Cell_ID` | Water, power, transport, and continuity context |
| Airspace geography | `airspace_sector`, `tile_id`, `Cell_ID` | FR24, SATIM, route, and airspace correlation |
| Governance geography | `permit_id`, `district`, `Cell_ID` | Permits, legislation, appropriations, and authority mapping |
| Event geography | `event_id`, `Cell_ID` | Incident, sighting, or disaster records |

## Rules

1. Do not fork the grid schema per repo.
2. Do not use municipality or barrio as the primary federation spatial key.
3. Preserve `Cell_ID`, `Row_Index`, and `Column_Index` in every derived overlay.
4. Store overlay provenance with source name, source URL or file, run timestamp, and confidence method when available.
5. Treat overlays as many-to-many when boundaries cross cell edges.
6. Use `Land_Pixel_Ratio` and `Classification` for filtering only, not as proof of jurisdiction or infrastructure presence.
7. Hub rollups should join producer outputs through `Cell_ID` first, then enrich with overlay labels.

## Recommended overlay record shape

```json
{
  "overlay_id": "municipality:san_juan:R042_C219",
  "overlay_type": "municipality",
  "overlay_name": "San Juan",
  "cell_id": "R042_C219",
  "coverage_ratio": 0.81,
  "source": "overlay source name",
  "source_tier": "T1",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "method": "boundary_intersection"
}
```

## Evidence tiers

| Tier | Use |
|---|---|
| T1 technical | GIS boundary files, authoritative APIs, official machine-readable data |
| T2 operational | Agency maps, operational dashboards, utility zone references |
| T3 eyewitness | Geolocated reports, sightings, field notes |
| T4 secondary | News, blogs, non-authoritative summaries |

## Promotion rule

A cross-repo spatial correlation may be promoted only when at least one record on each side resolves to a valid `Cell_ID`. If a record has coordinates but no resolved cell, it remains in staging until the spatial join is computed.
