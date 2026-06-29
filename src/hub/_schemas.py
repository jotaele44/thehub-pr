"""Locate and load the Hub's canonical JSON schemas.

Schemas live at the repo root under ``schemas/`` (single source of truth that
producers copy). When installed editable (``pip install -e .``) the package sits
at ``<root>/src/hub`` so the schema dir is two parents up. A ``HUB_SCHEMA_DIR``
env override is honoured for installed/relocated layouts.
"""
from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import Dict


def schema_dir() -> Path:
    override = os.environ.get("HUB_SCHEMA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "schemas"


# stream name -> canonical schema file
STREAM_SCHEMA: Dict[str, str] = {
    "sources": "federation_source.schema.json",
    "entities": "federation_entity.schema.json",
    "relationships": "federation_relationship.schema.json",
    "funding_awards": "federation_funding_award.schema.json",
    "transactions": "federation_transaction.schema.json",
    "observations": "federation_observation.schema.json",
    "alerts": "federation_alert.schema.json",
}

# stream name -> the field that holds the row's deterministic id (for dedup)
STREAM_ID_FIELD: Dict[str, str] = {
    "sources": "source_id",
    "entities": "entity_id",
    "relationships": "relationship_id",
    "funding_awards": "award_id",
    "transactions": "transaction_id",
    "observations": "observation_id",
    "alerts": "alert_id",
}


@functools.lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    return json.loads((schema_dir() / name).read_text())
