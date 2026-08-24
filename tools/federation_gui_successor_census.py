#!/usr/bin/env python3
from pathlib import Path
import federation_gui_census as census

ROOT = Path(__file__).resolve().parents[1]
census.SCOPE_PATH = ROOT / 'audit' / 'federation_gui_scope_20260824.json'
census.OUT_DIR = ROOT / 'audit' / 'generated' / 'federation_gui_census_20260824'
census.OUT_DIR.mkdir(parents=True, exist_ok=True)
raise SystemExit(census.main())
