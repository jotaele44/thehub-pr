#!/usr/bin/env python3
"""Validate Federation Experience Contract v1 documents.

A contract document is one application's declaration. Shape is checked against
the five JSON Schemas in ``rc2/schemas``. This module adds the rules a single
schema cannot express because they span sections or applications: duplicate ids,
namespace ownership, keyboard-binding conflicts, references between sections,
and version support.

``validate`` returns findings; an empty list means the set is acceptable. It
never repairs a document. ``canonical`` and ``digest`` give the deterministic
serialization used when a contract is hashed or compared.

Usage:
  rc2_validate.py <contract.json> [<contract.json> ...]
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, NamedTuple

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "rc2" / "schemas"
#: Major versions of the contract this validator understands.
SUPPORTED_MAJOR = (1,)
SECTION_SCHEMAS = {
    "contract": "federation-experience.contract.schema.json",
    "actions": "federation-actions.schema.json",
    "settings": "federation-settings.schema.json",
    "navigation": "federation-navigation.schema.json",
    "compatibility": "federation-compatibility.schema.json",
}


class Finding(NamedTuple):
    code: str
    application: str
    where: str
    message: str


def _validators() -> dict[str, Draft202012Validator]:
    loaded = {}
    for section, name in SECTION_SCHEMAS.items():
        schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        loaded[section] = Draft202012Validator(schema)
    return loaded


def canonical(document: Any) -> str:
    """Deterministic text form: sorted keys, no insignificant whitespace, UTF-8.

    Array order is preserved because it is meaningful (navigation order, display
    surfaces). NaN and infinities are refused: they are not JSON.
    """
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(document: Any) -> str:
    return hashlib.sha256(canonical(document).encode("utf-8")).hexdigest()


def _version(text: Any) -> tuple[int, int, int]:
    core = str(text).split("-", 1)[0].split(".")
    return (int(core[0]), int(core[1]), int(core[2]))


def _schema_findings(
    validator: Draft202012Validator, instance: Any, section: str, app: str, prefix: str = ""
) -> list[Finding]:
    findings = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        # Report the innermost failure of a conditional rule, not the wrapper.
        leaves = [error]
        while any(leaf.context for leaf in leaves):
            leaves = [sub for leaf in leaves for sub in (leaf.context or [leaf])]
        for leaf in leaves:
            path = prefix + "".join("/" + str(part) for part in leaf.absolute_path)
            findings.append(
                Finding(f"schema:{section}:{leaf.validator}", app, path or "/", leaf.message)
            )
    return findings


def _duplicates(values: Iterable[str]) -> list[str]:
    seen, repeated = set(), []
    for value in values:
        if value in seen and value not in repeated:
            repeated.append(value)
        seen.add(value)
    return repeated


def _as_dict(value: Any) -> dict:
    """The value when it is an object, else an empty one. A section of the wrong
    type is reported by the schema; the cross-section checks then skip it
    instead of failing on it."""
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    """The value when it is a list, else an empty one (see ``_as_dict``)."""
    return value if isinstance(value, list) else []


def _validate_one(doc: Any, validators: dict[str, Draft202012Validator]) -> list[Finding]:
    app = "?"
    if isinstance(doc, dict) and isinstance(doc.get("application"), dict):
        app = str(doc["application"].get("id", "?"))
    findings = _schema_findings(validators["contract"], doc, "contract", app)
    if not isinstance(doc, dict):
        return findings

    actions = _as_list(doc.get("actions"))
    settings = _as_list(doc.get("settings"))
    navigation = _as_dict(doc.get("navigation"))
    compatibility = _as_dict(doc.get("compatibility"))
    for index, action in enumerate(actions):
        findings += _schema_findings(validators["actions"], action, "actions", app, f"/actions/{index}")
    for index, setting in enumerate(settings):
        findings += _schema_findings(validators["settings"], setting, "settings", app, f"/settings/{index}")
    if "navigation" in doc:
        findings += _schema_findings(validators["navigation"], navigation, "navigation", app, "/navigation")
    if "compatibility" in doc:
        findings += _schema_findings(
            validators["compatibility"], compatibility, "compatibility", app, "/compatibility"
        )

    def add(code: str, where: str, message: str) -> None:
        findings.append(Finding(code, app, where, message))

    capabilities = [c.get("id") for c in _as_list(doc.get("capabilities")) if isinstance(c, dict)]
    for repeated in _duplicates(capabilities):
        add("duplicate-capability-id", "/capabilities", f"capability id {repeated!r} is declared twice")
    action_ids = [a.get("id") for a in actions if isinstance(a, dict)]
    for repeated in _duplicates(action_ids):
        add("duplicate-action-id", "/actions", f"action id {repeated!r} is declared twice")
    setting_ids = [s.get("id") for s in settings if isinstance(s, dict)]
    for repeated in _duplicates(setting_ids):
        add("duplicate-setting-id", "/settings", f"setting id {repeated!r} is declared twice")

    renameable_types = _as_list(_as_dict(doc.get("evidence")).get("renameable_object_types"))
    renameable = {t for t in renameable_types if isinstance(t, str)}
    modes = {m for m in _as_list(_as_dict(doc.get("authorization")).get("modes")) if isinstance(m, str)}
    bindings: dict[str, str] = {}
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        where, action_id = f"/actions/{index}", str(action.get("id"))
        if action.get("owning_application") != app:
            add("action-owner-mismatch", where,
                f"{action_id} is owned by {action.get('owning_application')!r}, not {app!r}")
        if not action_id.startswith(app + "."):
            add("action-namespace", where, f"{action_id} is not in the {app}. namespace")
        if action.get("capability_id") not in capabilities:
            add("action-capability-unknown", where,
                f"{action_id} names capability {action.get('capability_id')!r}, which is not declared")
        if action.get("kind") == "rename" and action.get("object_type") not in renameable:
            add("rename-not-declared", where,
                f"{action_id} renames {action.get('object_type')!r}, which evidence."
                "renameable_object_types does not list")
        if action.get("permission") == "guest" and "guest" not in modes and "single" not in modes:
            add("permission-mode-unknown", where, f"{action_id} is for guests but the app has no guest mode")
        binding = action.get("keyboard_binding")
        if binding:
            if binding in bindings:
                add("binding-conflict", where,
                    f"{binding} is bound to both {bindings[binding]} and {action_id}")
            else:
                bindings[binding] = action_id

    settings_by_id = {s.get("id"): s for s in settings if isinstance(s, dict)}
    for index, setting in enumerate(settings):
        if not isinstance(setting, dict):
            continue
        owner, setting_id = setting.get("owning_application"), str(setting.get("id"))
        if owner is not None:
            if owner != app:
                add("setting-owner-mismatch", f"/settings/{index}",
                    f"{setting_id} is owned by {owner!r}, not {app!r}")
            if not setting_id.startswith(app + "."):
                add("setting-namespace", f"/settings/{index}",
                    f"{setting_id} is application-scoped but not in the {app}. namespace")

    nav_ids: list[str] = []
    for g_index, group in enumerate(_as_list(navigation.get("groups"))):
        if not isinstance(group, dict):
            continue
        nav_ids.append(f"group:{group.get('id')}")
        for i_index, item in enumerate(_as_list(group.get("items"))):
            if not isinstance(item, dict):
                continue
            nav_ids.append(f"item:{item.get('id')}")
            if item.get("capability_id") not in capabilities:
                add("nav-capability-unknown", f"/navigation/groups/{g_index}/items/{i_index}",
                    f"navigation item {item.get('id')!r} names an undeclared capability")
            binding = item.get("keyboard_binding")
            if binding:
                owner_id = f"navigation:{item.get('id')}"
                if binding in bindings:
                    add("binding-conflict", f"/navigation/groups/{g_index}/items/{i_index}",
                        f"{binding} is bound to both {bindings[binding]} and {owner_id}")
                else:
                    bindings[binding] = owner_id
        if group.get("kind") in ("pinned", "recent"):
            stored = settings_by_id.get(group.get("setting_id"))
            where = f"/navigation/groups/{g_index}"
            if stored is None:
                add("nav-setting-unknown", where,
                    f"group {group.get('id')!r} stores its list in {group.get('setting_id')!r}, "
                    "which is not a declared setting")
            else:
                if stored.get("value_type") != "id-list":
                    add("nav-setting-type", where, f"{stored.get('id')} is not an id-list")
                if stored.get("scope") != "APPLICATION_USER":
                    add("nav-setting-scope", where,
                        f"{stored.get('id')} must be APPLICATION_USER so one application's "
                        "list cannot overwrite another's")
                if isinstance(stored.get("max_items"), int) and isinstance(group.get("max_items"), int) \
                        and stored["max_items"] < group["max_items"]:
                    add("nav-setting-capacity", where,
                        f"group shows {group['max_items']} items but {stored.get('id')} keeps "
                        f"{stored['max_items']}")
    for repeated in _duplicates(nav_ids):
        add("duplicate-navigation-id", "/navigation", f"{repeated} is declared twice")
    if navigation.get("application") not in (None, app):
        add("navigation-application-mismatch", "/navigation", "navigation is for another application")
    integration = _as_dict(doc.get("integration"))
    if navigation.get("addressing") == "in-memory" and integration.get("deep_links") is True:
        add("deep-link-contradiction", "/integration/deep_links",
            "deep links are claimed but navigation is in-memory")

    if compatibility.get("application") not in (None, app):
        add("compatibility-application-mismatch", "/compatibility",
            "compatibility is for another application")
    try:
        declared = _version(_as_dict(doc.get("contract")).get("version"))
        if declared[0] not in SUPPORTED_MAJOR:
            add("version-unsupported", "/contract/version",
                f"contract major {declared[0]} is not supported (supported: {SUPPORTED_MAJOR})")
        low = _version(compatibility.get("min_contract_version"))
        high = _version(compatibility.get("max_contract_version"))
        stated = _version(compatibility.get("contract_version"))
        if stated != declared:
            add("version-mismatch", "/compatibility/contract_version",
                "compatibility.contract_version differs from contract.version")
        if not low <= declared <= high:
            add("version-range", "/compatibility",
                f"contract {declared} is outside the declared range {low}..{high}")
    except (ValueError, IndexError, TypeError):
        pass  # malformed versions are already reported by the schema
    return findings


def validate(documents: Iterable[Any]) -> list[Finding]:
    """Findings for a set of contracts that are meant to coexist."""
    validators = _validators()
    documents = list(documents)
    findings: list[Finding] = []
    for doc in documents:
        findings += _validate_one(doc, validators)

    def app_of(doc: Any) -> str:
        return str(_as_dict(doc.get("application")).get("id", "?")) if isinstance(doc, dict) else "?"

    apps = [app_of(doc) for doc in documents]
    for repeated in _duplicates(apps):
        findings.append(Finding("duplicate-application", repeated, "/application/id",
                                f"{repeated} is declared by more than one contract"))
    owners: dict[str, dict[str, str]] = {"action": {}, "setting": {}}
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        app = app_of(doc)
        for kind, key in (("action", "actions"), ("setting", "settings")):
            for item in _as_list(doc.get(key)):
                if not isinstance(item, dict) or "id" not in item:
                    continue
                item_id = str(item["id"])
                # A federation-global setting may be restated by several apps,
                # but only with one definition.
                if kind == "setting" and item.get("scope") == "GLOBAL_USER":
                    previous = owners["setting"].get("global:" + item_id)
                    current = digest(item)
                    if previous is not None and previous != current:
                        findings.append(Finding(
                            "global-setting-conflict", app, "/settings",
                            f"{item_id} is defined differently by another application"))
                    owners["setting"]["global:" + item_id] = current
                    continue
                previous = owners[kind].get(item_id)
                if previous is not None and previous != app:
                    findings.append(Finding(
                        f"{kind}-collision", app, f"/{key}",
                        f"{item_id} is also declared by {previous}"))
                owners[kind].setdefault(item_id, app)
    return findings


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    documents = [json.loads(Path(path).read_text(encoding="utf-8")) for path in argv]
    findings = validate(documents)
    for finding in findings:
        print(f"{finding.code}\t{finding.application}\t{finding.where}\t{finding.message}")
    print(f"{len(documents)} contract(s), {len(findings)} finding(s)", file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
