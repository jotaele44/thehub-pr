"""thehub-pr — the PRII federation Hub.

Responsibilities:
  * registry   — discover producer nodes (registry/producers.yaml)
  * manifest   — validate a producer's federation.json (repo_federation_manifest_v1)
  * validate   — validate a producer export package (manifest + JSONL streams)
  * aggregate  — merge validated producer streams into a single federation graph

The Hub owns the canonical schemas under ``schemas/``; producers conform to them.
"""

from ._shared_transport_binding import install_import_guard as _install_import_guard

_install_import_guard()
del _install_import_guard

__version__ = "0.1.0"
