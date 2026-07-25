"""Project-consolidation "signs" for the Hub.

When the Hub finishes consolidating a project's information, this module renders a
public-works style placard — the kind posted at a funded project site: a project
title (award type), its location, one or more funding contributions ("Aportación")
with the responsible agency, its officials, and the dollar amount, plus an agency
seal badge.

A "project" here groups every ``funding_awards`` row that shares the same recipient
and location (municipality), so a single sign lists multiple contributions the way a
real placard does. Reads the JSONL streams produced by ``hub aggregate`` — this is a
consolidation-summary artifact, **not** an official notice; every sign says so, and
synthetic/test data renders a visible SYNTHETIC ribbon.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


# ── design tokens (mirrors federation-design/tokens/federation.tokens.json) ──
_FONT = ('Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, '
         '"Segoe UI", sans-serif')
_ACCENT = "#16a34a"  # repoAccents["moneysweep-pr"] — public-money domain

# Optional thank-you taglines keyed by normalized award type. Absent -> no tagline.
AWARD_TYPE_TAGLINES: Dict[str, str] = {
    "pavimentacion": "Gracias por ayudar a garantizar la seguridad vial.",
    "paving": "Gracias por ayudar a garantizar la seguridad vial.",
}


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "project"


def _money(amount: float, currency: str = "USD") -> str:
    symbol = "$" if currency == "USD" else ""
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}0.00"


def _title_case(text: str) -> str:
    return " ".join(w.capitalize() for w in (text or "").split())


def _normalize(text: str) -> str:
    """Fold accents/spacing so award-type lookups match ('Pavimentación' -> 'pavimentacion')."""
    lowered = (text or "").strip().lower()
    folds = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    return re.sub(r"\s+", " ", "".join(folds.get(c, c) for c in lowered))


def _location_label(loc: Dict[str, Any]) -> str:
    """Human location line, e.g. 'Urb. Encantada | Trujillo Alto'."""
    if not isinstance(loc, dict):
        return ""
    muni = loc.get("municipality_name") or loc.get("municipality") or ""
    sub = loc.get("postal_code") if loc.get("municipality_name") else ""
    parts = [p for p in (loc.get("municipality"), muni) if p]
    # De-dup when municipality and municipality_name coincide.
    seen: List[str] = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    label = " | ".join(seen)
    return label + (f" | {sub}" if sub else "")


def _location_key(loc: Dict[str, Any]) -> str:
    if not isinstance(loc, dict):
        return ""
    return _normalize(loc.get("municipality_name") or loc.get("municipality") or "")


def _officials_index(entities: Dict[str, dict], relationships: List[dict]) -> Dict[str, List[dict]]:
    """Map each agency entity_id -> list of {name, role} person entities linked to it.

    A person is any entity related to the agency by a relationship in either direction.
    The role comes from the relationship's ``explanation`` (e.g. 'Presidente'), falling
    back to a humanized ``relationship_type``.
    """
    index: Dict[str, List[dict]] = {}
    for rel in relationships:
        a = rel.get("source_entity_id")
        b = rel.get("target_entity_id")
        if a not in entities or b not in entities:
            continue
        role = rel.get("explanation") or _title_case(
            (rel.get("relationship_type") or "").replace("_", " ")
        )
        # Attach the *person* side to the *agency/org* side. We treat the entity whose
        # type looks person-ish as the official; when ambiguous, attach b -> a.
        for person_id, agency_id in ((a, b), (b, a)):
            if _is_person(entities.get(person_id, {})) and not _is_person(entities.get(agency_id, {})):
                index.setdefault(agency_id, []).append(
                    {"name": entities[person_id].get("name", ""), "role": role}
                )
                break
        else:
            index.setdefault(a, []).append({"name": entities[b].get("name", ""), "role": role})
    # Deterministic, de-duplicated per agency.
    for agency_id, people in index.items():
        uniq: List[dict] = []
        seen = set()
        for p in sorted(people, key=lambda x: (x["name"], x["role"])):
            key = (p["name"], p["role"])
            if key not in seen:
                seen.add(key)
                uniq.append(p)
        index[agency_id] = uniq
    return index


def _is_person(entity: Dict[str, Any]) -> bool:
    etype = _normalize(entity.get("entity_type", ""))
    return etype in {"person", "official", "individual", "people"}


def build_project_signs(aggregate_dir: str | Path) -> List[Dict[str, Any]]:
    """Group an aggregate's funding awards into per-project sign dicts.

    Returns a deterministic list; each sign carries the project title, location, the
    list of funding contributions (agency + officials + amount), a total, and a
    ``synthetic`` flag set when any contributing award is synthetic.
    """
    agg = Path(aggregate_dir)
    entities_list = _read_jsonl(agg / "entities.jsonl")
    awards = _read_jsonl(agg / "funding_awards.jsonl")
    relationships = _read_jsonl(agg / "relationships.jsonl")

    entities = {e["entity_id"]: e for e in entities_list if "entity_id" in e}
    officials = _officials_index(entities, relationships)

    # Group awards by (recipient, location municipality).
    groups: Dict[tuple, List[dict]] = {}
    for a in awards:
        recipient = a.get("recipient_entity_id", "")
        key = (recipient, _location_key(a.get("location", {})))
        groups.setdefault(key, []).append(a)

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    signs: List[Dict[str, Any]] = []
    for (recipient, loc_key), group in groups.items():
        recipient_ent = entities.get(recipient, {})
        # Dominant award type -> headline title.
        types = [a.get("award_type", "") for a in group if a.get("award_type")]
        headline = _title_case(max(set(types), key=types.count)) if types else "Proyecto"
        location = _location_label(group[0].get("location", {}))

        contributions: List[Dict[str, Any]] = []
        total = 0.0
        currency = "USD"
        synthetic = False
        for a in sorted(group, key=lambda x: (-float(x.get("amount", 0) or 0), x.get("award_id", ""))):
            agency_id = a.get("funding_agency_entity_id", "")
            currency = a.get("currency", currency)
            amt = float(a.get("amount", 0) or 0)
            total += amt
            synthetic = synthetic or bool(a.get("synthetic"))
            contributions.append({
                "agency_name": entities.get(agency_id, {}).get("name", agency_id or "—"),
                "amount": amt,
                "currency": a.get("currency", "USD"),
                "officials": officials.get(agency_id, []),
                "award_id": a.get("award_id", ""),
                "award_date": a.get("award_date", ""),
            })

        project_id = "sgn_" + hashlib.sha1(
            f"{recipient}|{loc_key}".encode("utf-8")
        ).hexdigest()[:16]
        signs.append({
            "project_id": project_id,
            "title": headline,
            "recipient_name": recipient_ent.get("name", recipient or "—"),
            "location": location,
            "tagline": AWARD_TYPE_TAGLINES.get(_normalize(headline), ""),
            "contributions": contributions,
            "total_amount": total,
            "currency": currency,
            "synthetic": synthetic,
            "generated_at": generated_at,
        })

    signs.sort(key=lambda s: s["project_id"])
    return signs


def _seal_badge(agency_name: str) -> str:
    initials = "".join(w[0] for w in agency_name.split()[:3]).upper() or "•"
    return html.escape(initials)


def render_sign_html(sign: Dict[str, Any]) -> str:
    """Render a single project sign as a self-contained HTML placard."""
    e = html.escape
    title = e(sign.get("title", ""))
    location = e(sign.get("location", ""))
    recipient = e(sign.get("recipient_name", ""))
    tagline = e(sign.get("tagline", ""))
    currency = sign.get("currency", "USD")

    ribbon = (
        '<div class="ribbon">SYNTHETIC / TEST DATA</div>' if sign.get("synthetic") else ""
    )

    blocks = []
    for c in sign.get("contributions", []):
        officials = "".join(
            f'<div class="official">{e(o.get("name", ""))}'
            + (f' <span class="role">— {e(o.get("role", ""))}</span>' if o.get("role") else "")
            + "</div>"
            for o in c.get("officials", [])
        )
        seal = _seal_badge(c.get("agency_name", ""))
        blocks.append(
            '<div class="aporte">'
            '<div class="aporte-head"><span class="tag">Aportación</span>'
            f'<span class="agency">{e(c.get("agency_name", ""))}</span>'
            f'<span class="seal" title="{e(c.get("agency_name", ""))}">{seal}</span></div>'
            f'<div class="officials">{officials}</div>'
            f'<div class="amount">{e(_money(c.get("amount", 0), c.get("currency", currency)))}</div>'
            "</div>"
        )
    contributions_html = "".join(blocks)
    total_html = e(_money(sign.get("total_amount", 0), currency))
    tagline_html = f'<div class="tagline">{tagline}</div>' if tagline else ""

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — {location or recipient}</title>
<style>
  :root {{ --accent: {_ACCENT}; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: {_FONT}; margin: 0; background: #0b1220; color: #f8fafc;
         display: flex; justify-content: center; padding: 24px; }}
  .sign {{ width: 100%; max-width: 820px; background: #111a2e;
          border: 3px solid var(--accent); border-radius: 16px; overflow: hidden;
          box-shadow: 0 12px 32px rgba(0,0,0,.28); position: relative; }}
  .ribbon {{ position: absolute; top: 16px; right: -44px; transform: rotate(45deg);
            background: #b45309; color: #fff; font-weight: 700; font-size: .72rem;
            letter-spacing: .08em; padding: 6px 56px; }}
  .head {{ display: flex; align-items: center; gap: 16px; padding: 24px 28px;
          background: linear-gradient(135deg, rgba(22,163,74,.22), transparent); }}
  .icon {{ flex: 0 0 auto; width: 54px; height: 54px; border: 3px solid var(--accent);
          border-radius: 12px; display: grid; place-items: center; font-size: 1.6rem; }}
  .head h1 {{ margin: 0; font-size: 2.2rem; font-weight: 700; letter-spacing: .01em;
             text-transform: uppercase; }}
  .loc {{ padding: 4px 28px 18px; font-size: 1.35rem; font-weight: 600; color: #e2e8f0; }}
  .loc .recipient {{ display: block; font-size: .95rem; font-weight: 500; color: #94a3b8; }}
  .tagline {{ padding: 0 28px 18px; color: var(--accent); font-weight: 600; font-size: 1.05rem; }}
  .aporte {{ margin: 0 28px 16px; padding: 16px 18px; background: #0b1220;
            border-radius: 12px; border: 1px solid #1e293b; }}
  .aporte-head {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
  .tag {{ background: var(--accent); color: #04140a; font-weight: 700; font-size: .75rem;
         text-transform: uppercase; letter-spacing: .05em; padding: 3px 10px; border-radius: 999px; }}
  .agency {{ font-weight: 700; font-size: 1.05rem; flex: 1 1 auto; }}
  .seal {{ flex: 0 0 auto; width: 40px; height: 40px; border-radius: 999px;
          border: 2px solid var(--accent); display: grid; place-items: center;
          font-weight: 700; font-size: .85rem; color: var(--accent); }}
  .officials {{ margin: 8px 0 4px; }}
  .official {{ font-size: .92rem; color: #cbd5e1; }}
  .official .role {{ color: #94a3b8; }}
  .amount {{ margin-top: 8px; font-size: 1.9rem; font-weight: 700; color: #f8fafc; }}
  .total {{ display: flex; justify-content: space-between; align-items: baseline;
           padding: 12px 28px 20px; border-top: 1px solid #1e293b; margin-top: 4px; }}
  .total .label {{ color: #94a3b8; text-transform: uppercase; font-size: .78rem; letter-spacing: .08em; }}
  .total .value {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
  .foot {{ padding: 10px 28px 18px; font-size: .72rem; color: #64748b; }}
</style></head>
<body>
  <div class="sign">
    {ribbon}
    <div class="head"><div class="icon">🚧</div><h1>{title}</h1></div>
    <div class="loc">{location}<span class="recipient">{recipient}</span></div>
    {tagline_html}
    {contributions_html}
    <div class="total"><span class="label">Total consolidado</span><span class="value">{total_html}</span></div>
    <div class="foot">Generado por el PRII Hub a partir de datos de la federación — no es un aviso oficial.</div>
  </div>
</body></html>"""


def write_project_signs(aggregate_dir: str | Path, out_dir: str | Path) -> Dict[str, Any]:
    """Build signs from an aggregate and write one HTML file per project plus index.json."""
    signs = build_project_signs(aggregate_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    for sign in signs:
        (out / f"{sign['project_id']}.html").write_text(render_sign_html(sign))
    (out / "index.json").write_text(
        json.dumps({"count": len(signs), "signs": signs}, indent=2, sort_keys=True)
    )

    return {
        "count": len(signs),
        "out_dir": str(out),
        "synthetic_count": sum(1 for s in signs if s["synthetic"]),
        "signs": signs,
    }
