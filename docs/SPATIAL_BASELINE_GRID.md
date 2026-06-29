# Puerto Rico Baseline Grid

This repository uses the shared Puerto Rico federation baseline grid as its canonical cell-level spatial index.

## Canonical file

```text
registry/spatial/pr_grid_full_cell_index_saturated.csv
```

## Source metrics

| Metric | Value |
|---|---:|
| Rows | 98,304 |
| Columns | 13 |
| Row range | 0-255 |
| Column range | 0-383 |
| Water / empty cells | 96,339 |
| Gridline-dominant cells | 1,171 |
| Coastline / land cells | 794 |
| Source SHA-256 | `17733f3f18c8a644e31c1eb25fb27b73b4bf353c6de57d5203c4311e05d64483` |
| Source size | 6,807,952 bytes |

## Required columns

```text
Cell_ID
Row_Index
Column_Index
Pixel_X_Min
Pixel_Y_Min
Pixel_X_Max
Pixel_Y_Max
Centroid_X
Centroid_Y
Dark_Pixel_Count
Total_Pixel_Count
Land_Pixel_Ratio
Classification
```

## Operating rule

Use `Cell_ID` as the stable spatial join key. Repo-specific geographies such as municipality, barrio, watershed, utility zone, airspace sector, SATIM tile, permit zone, or legislative district must be modeled as overlays that join back to this grid rather than replacing it.

## Validation

```bash
python scripts/validate_pr_grid.py --grid registry/spatial/pr_grid_full_cell_index_saturated.csv
python scripts/validate_pr_grid.py --grid registry/spatial/pr_grid_full_cell_index_saturated.csv --require-sha
```
