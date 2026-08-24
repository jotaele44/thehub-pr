#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'audit' / 'federation_gui_surface_applicability_20260824.json'
OUT = ROOT / 'audit' / 'generated' / 'federation_gui_census_20260824' / 'surface_arithmetic.json'

manifest = json.loads(PATH.read_text(encoding='utf-8'))
counts = {k: 0 for k in ['rendered','conditional_auth','not_found','dynamic','redirect_behavior','workbench_modules']}
for repo in manifest['repositories'].values():
    for key in counts:
        counts[key] += len(repo.get(key, []))

rendered_surfaces = counts['rendered'] + counts['conditional_auth'] + counts['not_found'] + counts['dynamic'] + counts['workbench_modules']
engines = 3
viewports = 6
a11y_modes = 3
result = {
    'snapshot_label': manifest['snapshot_label'],
    'classification_counts': counts,
    'rendered_surface_denominator': rendered_surfaces,
    'redirect_behavior_denominator': counts['redirect_behavior'],
    'baseline_browser_viewport_cells': rendered_surfaces * engines * viewports,
    'dynamic_positive_cells_in_baseline': counts['dynamic'] * engines * viewports,
    'dynamic_missing_record_additional_cells': counts['dynamic'] * engines * viewports,
    'minimum_surface_state_screenshot_cells_before_other_state_applicability': (rendered_surfaces + counts['dynamic']) * engines * viewports,
    'redirect_behavior_assertion_cells': counts['redirect_behavior'] * engines * viewports,
    'baseline_accessibility_mode_cells': rendered_surfaces * a11y_modes,
    'dynamic_missing_record_additional_accessibility_cells': counts['dynamic'] * a11y_modes,
    'native_200_percent_zoom_required': True,
    'state_applicability_beyond_dynamic_detail_states': 'OPEN',
    'certification': 'OPEN',
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2, sort_keys=True))
