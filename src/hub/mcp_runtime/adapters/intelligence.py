"""Intelligence adapter — read-only queries over the certified ACTIVE snapshot.

Backed entirely by ``intelligence_engine.reader.ActiveSnapshotReader``: local
filesystem snapshot pointer + aggregate JSONL files, no network, no secrets.
Serves the ``intelligence-query`` capability. See
``intelligence_engine.reader``'s module docstring for this reader's scope
limits (EXACT_ID/STRUCTURED only, no citation resolution, no real
access-classification enforcement yet).
"""

from __future__ import annotations

from typing import Any, Dict, List

from hub.mcp_runtime.sdk import MCPAdapter, MCPRequest
from intelligence_engine.query import QuerySpec
from intelligence_engine.reader import ActiveSnapshotReader


class IntelligenceQueryAdapter(MCPAdapter):
    """Read-only view over the Intelligence Engine's ACTIVE snapshot.

    Actions:
      - ``get_object``: one object by ``object_id`` (params: object_id).
      - ``query``:      a structured lookup (params: mode, object_id, stream,
                        filters) — see ``intelligence_engine.query.QuerySpec``.

    ``params["storage_root"]`` names the Control Plane snapshot registry root;
    an optional ``params["aggregate_dir"]`` overrides the aggregate JSONL
    location (defaults to ``data/aggregate``), mirroring how ``ProvenanceAdapter``
    and ``DocumentsAdapter`` take their data location from request params rather
    than a hard-coded path.
    """

    def name(self) -> str:
        return "intelligence-query"

    def version(self) -> str:
        return "0.1.0"

    def capabilities(self) -> List[str]:
        return ["intelligence-query"]

    def _reader(self, request: MCPRequest) -> ActiveSnapshotReader:
        storage_root = request.params.get("storage_root")
        if not storage_root:
            raise ValueError(f"action {request.action!r} requires a 'storage_root' param")
        aggregate_dir = request.params.get("aggregate_dir")
        return ActiveSnapshotReader(storage_root, aggregate_dir=aggregate_dir)

    def execute(self, request: MCPRequest) -> Any:
        reader = self._reader(request)
        params = request.params

        if request.action == "get_object":
            object_id = params.get("object_id")
            if not object_id:
                raise ValueError("get_object requires an 'object_id' param")
            return reader.get_object(object_id)

        if request.action == "query":
            mode = params.get("mode")
            if mode not in ("EXACT_ID", "STRUCTURED"):
                raise ValueError("query requires mode 'EXACT_ID' or 'STRUCTURED'")
            spec = QuerySpec(
                mode=mode,
                object_id=params.get("object_id"),
                stream=params.get("stream"),
                filters=params.get("filters"),
            )
            return reader.query(spec)

        raise ValueError(f"unknown action {request.action!r}")

    def provenance(self, request: MCPRequest) -> Dict[str, Any]:
        block = super().provenance(request)
        storage_root = request.params.get("storage_root")
        if storage_root is not None:
            block["storage_root"] = str(storage_root)
        return block
