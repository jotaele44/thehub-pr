"""Documents adapter — archive text search over a local directory tree.

Backed by files on disk (markdown/plain text); no network, no secrets.
Serves the ``documents`` capability (declared by the ovnis case archive).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from hub.mcp_runtime.sdk import MCPAdapter, MCPRequest

_DEFAULT_MAX_HITS = 200
_GLOBS = ("**/*.md", "**/*.txt")


class DocumentsAdapter(MCPAdapter):
    """Read-only text search/read over a document root.

    Actions:
      - ``search``: case-insensitive substring across ``*.md``/``*.txt`` under
                    params ``root``; returns ``{path, line_no, line}`` hits
                    (params: query, optional max_hits).
      - ``get``:    return the text of params ``path`` (must resolve inside
                    ``root``).
    """

    def name(self) -> str:
        return "documents-archive"

    def version(self) -> str:
        return "0.1.0"

    def capabilities(self) -> List[str]:
        return ["documents"]

    @staticmethod
    def _root(request: MCPRequest) -> Path:
        raw = request.params.get("root")
        if not raw:
            raise ValueError(f"action {request.action!r} requires a 'root' param")
        return Path(raw).resolve()

    @staticmethod
    def _within(root: Path, target: Path) -> Path:
        resolved = target.resolve()
        # Path.is_relative_to lands in 3.9; guard against traversal escapes.
        if root not in resolved.parents and resolved != root:
            raise ValueError(f"path {target} escapes document root {root}")
        return resolved

    def execute(self, request: MCPRequest) -> Any:
        root = self._root(request)
        if not root.is_dir():
            raise FileNotFoundError(f"document root not found: {root}")

        if request.action == "search":
            query = request.params.get("query")
            if not query:
                raise ValueError("search requires a 'query' param")
            max_hits = int(request.params.get("max_hits", _DEFAULT_MAX_HITS))
            needle = query.lower()
            hits: List[Dict[str, Any]] = []
            for glob in _GLOBS:
                for path in sorted(root.glob(glob)):
                    if not path.is_file():
                        continue
                    text = path.read_text(encoding="utf-8", errors="replace")
                    for line_no, line in enumerate(text.splitlines(), start=1):
                        if needle in line.lower():
                            hits.append({
                                "path": str(path.relative_to(root)),
                                "line_no": line_no,
                                "line": line.strip(),
                            })
                            if len(hits) >= max_hits:
                                return {"hits": hits, "truncated": True}
            return {"hits": hits, "truncated": False}

        if request.action == "get":
            raw = request.params.get("path")
            if not raw:
                raise ValueError("get requires a 'path' param")
            target = self._within(root, root / raw)
            if not target.is_file():
                raise FileNotFoundError(f"document not found: {raw}")
            return {
                "path": str(target.relative_to(root)),
                "text": target.read_text(encoding="utf-8", errors="replace"),
            }

        raise ValueError(f"unknown action {request.action!r}")

    def provenance(self, request: MCPRequest) -> Dict[str, Any]:
        block = super().provenance(request)
        raw_root = request.params.get("root")
        if raw_root:
            block["root"] = str(Path(raw_root).resolve())
        return block
