"""Provenance adapter — read source lineage from a federation export package.

Backed entirely by local export packages (the ``sources.jsonl`` stream a
producer emits); no network, no secrets. Serves the ``provenance``
capability every project inherits.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.mcp_runtime.sdk import MCPAdapter, MCPRequest


def _fid(prefix: str, *parts: Any) -> str:
    """Deterministic ``prefix_<sha256[:32]>`` id.

    Same construction as ``prii_export_utils.fid``; inlined so core ``hub``
    stays free of a cross-package dependency the main test env doesn't install.
    """
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return f"{prefix}_{digest[:32]}"


class ProvenanceAdapter(MCPAdapter):
    """Read-only view over an export package's source lineage.

    Actions:
      - ``list_sources``: every source row in ``<package>/sources.jsonl``.
      - ``get_source``:   one source row by ``source_id`` (params: source_id).
      - ``stamp``:        mint a deterministic provenance id from params
                          (``prefix`` + ``parts``) via a deterministic sha256 id.

    The package directory comes from ``params["package"]`` so the runtime
    never hard-codes a data path.
    """

    def name(self) -> str:
        return "provenance-ledger"

    def version(self) -> str:
        return "0.1.0"

    def capabilities(self) -> List[str]:
        return ["provenance"]

    def _sources(self, package: Path) -> List[Dict[str, Any]]:
        sources_file = package / "sources.jsonl"
        if not sources_file.is_file():
            raise FileNotFoundError(f"no sources.jsonl in package {package}")
        rows = []
        for line in sources_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def _package_path(self, request: MCPRequest) -> Optional[Path]:
        raw = request.params.get("package")
        return Path(raw) if raw else None

    def execute(self, request: MCPRequest) -> Any:
        if request.action == "stamp":
            prefix = request.params.get("prefix", "prov")
            parts = request.params.get("parts", [])
            return {"provenance_id": _fid(prefix, *parts)}

        package = self._package_path(request)
        if package is None:
            raise ValueError(f"action {request.action!r} requires a 'package' param")
        sources = self._sources(package)

        if request.action == "list_sources":
            return {"sources": sources, "count": len(sources)}
        if request.action == "get_source":
            source_id = request.params.get("source_id")
            if not source_id:
                raise ValueError("get_source requires a 'source_id' param")
            for row in sources:
                if row.get("source_id") == source_id:
                    return {"source": row}
            raise LookupError(f"source {source_id!r} not found in {package}")

        raise ValueError(f"unknown action {request.action!r}")

    def provenance(self, request: MCPRequest) -> Dict[str, Any]:
        block = super().provenance(request)
        package = self._package_path(request)
        if package is not None:
            block["package"] = str(package)
        return block
