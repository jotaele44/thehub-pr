"""thehub-pr — the PRII federation Hub.

Responsibilities:
  * registry   — discover producer nodes (registry/producers.yaml)
  * manifest   — validate a producer's federation.json (repo_federation_manifest_v1)
  * validate   — validate a producer export package (manifest + JSONL streams)
  * aggregate  — merge validated producer streams into a single federation graph

The Hub owns the canonical schemas under ``schemas/``; producers conform to them.
"""

__version__ = "0.1.0"
