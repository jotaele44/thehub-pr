#!/usr/bin/env python3
"""Compare SpiderWeb's frozen local --fd-* CSS namespace to the frozen Hub canonical foundation.

This compares CSS custom-property manifestations only. It does not claim semantic or
visual equivalence: equal names can have different values, and different names can
represent related concepts. Those remain review candidates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "audit" / "generated" / "federation_gui_census" / "spiderweb_token_diff.json"
CANON = ROOT / "repos" / "thehub-pr" / "federation-design" / "styles" / "foundation.css"
SPIDER = ROOT / "repos" / "spiderweb-pr" / "server" / "frontend" / "src" / "styles" / "federation.css"
VAR_RE = re.compile(r"(--fd-[A-Za-z0-9_-]+)\s*:")


def vars_in(path: Path) -> set[str]:
    if not path.exists():
        raise SystemExit(f"missing required token source: {path}")
    return set(VAR_RE.findall(path.read_text(encoding="utf-8", errors="strict")))


def main() -> int:
    a = vars_in(CANON)
    b = vars_in(SPIDER)
    intersection = sorted(a & b)
    a_only = sorted(a - b)
    b_only = sorted(b - a)
    union = sorted(a | b)
    symmetric_difference = sorted(a ^ b)
    payload = {
        "comparison": "CSS_CUSTOM_PROPERTY_NAME_MANIFESTATION_ONLY",
        "a": "thehub-pr canonical federation-design/styles/foundation.css",
        "b": "spiderweb-pr server/frontend/src/styles/federation.css",
        "a_count": len(a),
        "b_count": len(b),
        "intersection": intersection,
        "intersection_count": len(intersection),
        "a_only": a_only,
        "a_only_count": len(a_only),
        "b_only": b_only,
        "b_only_count": len(b_only),
        "union": union,
        "union_count": len(union),
        "symmetric_difference": symmetric_difference,
        "symmetric_difference_count": len(symmetric_difference),
        "semantic_equivalence": "UNRESOLVED",
        "warning": "Name equality is not semantic/visual identity; name difference is not proof of semantic difference. Values and usage require adjudication."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
