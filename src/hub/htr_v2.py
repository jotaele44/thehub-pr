"""HTR v2 source-aware normalization and fail-closed discovery semantics.

Hydro-Toponym Recurrence (HTR) is a discovery layer. Name, fuzzy, proximity,
and cluster signals never establish canonical identity or hydraulic/electrical
connectivity. ``UNSUPPORTED`` means that a preserved source manifestation or
candidate lacks sufficient support for the analytical use at issue; it does
not mean false, disproved, or a distinct entity.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "htr-2.0"

TIGER_ROAD_EXPANSIONS = {
    "av": "avenida",
    "ave": "avenida",
    "bda": "barriada",
    "blvd": "boulevard",
    "bo": "barrio",
    "cam": "camino",
    "carr": "carretera",
    "cjon": "callejon",
    "cll": "calle",
    "ctra": "carretera",
    "plz": "plaza",
    "pso": "paseo",
    "sec": "sector",
    "urb": "urbanizacion",
}
ROAD_GENERIC_TOKENS = {
    "avenida",
    "barriada",
    "barrio",
    "boulevard",
    "calle",
    "callejon",
    "camino",
    "carretera",
    "highway",
    "hwy",
    "paseo",
    "plaza",
    "road",
    "ruta",
    "sector",
    "street",
    "urbanizacion",
}
HYDRO_CLASS_TOKENS = {
    "canal",
    "dam",
    "embalse",
    "lago",
    "lake",
    "presa",
    "quebrada",
    "reservoir",
    "rio",
    "river",
}
HYDRO_GENERIC_TOKENS = HYDRO_CLASS_TOKENS | {
    "central",
    "hidroelectrica",
    "hidroelectrico",
    "hydro",
    "hydroelectric",
    "plant",
    "planta",
    "tunel",
    "tunnel",
}
ROAD_PROFILES = {"SIGE_ROAD", "TIGER2025_ROAD"}
HYDRO_PROFILES = {"HYDRO_FROZEN_V1", "DRNA_RESERVOIR", "USGS_CONVEYANCE"}


class HTRV2InvariantError(ValueError):
    """Raised when HTR v2 safety or conservation invariants fail."""


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _fold(raw: str) -> str:
    folded = unicodedata.normalize("NFKD", raw.casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", folded).split())


def normalize_name(raw: str, source_profile: str) -> dict[str, Any]:
    """Normalize a name without replacing RAW or asserting a canonical identity."""
    if not isinstance(raw, str) or not raw.strip():
        raise HTRV2InvariantError("name must be a non-empty string")
    if source_profile not in ROAD_PROFILES | HYDRO_PROFILES:
        raise HTRV2InvariantError(f"unsupported normalization profile: {source_profile}")

    normalized = _fold(raw)
    tokens = normalized.split()
    if source_profile == "TIGER2025_ROAD":
        expanded = [TIGER_ROAD_EXPANSIONS.get(token, token) for token in tokens]
    else:
        expanded = list(tokens)
    source_normalized = " ".join(expanded)

    if source_profile in ROAD_PROFILES:
        removable = ROAD_GENERIC_TOKENS | HYDRO_CLASS_TOKENS
    else:
        removable = HYDRO_GENERIC_TOKENS
    core_tokens = [token for token in expanded if token not in removable]
    core = " ".join(core_tokens) or source_normalized

    return {
        "raw": raw,
        "normalized": normalized,
        "source_normalized": source_normalized,
        "core": core,
        "canonical": None,
        "normalization_profile": source_profile,
    }


def levenshtein(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, 1):
        current = [index]
        for offset, right_char in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[offset] + 1,
                    previous[offset - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    max_len = max(len(left), len(right), 1)
    sequence = SequenceMatcher(None, left, right, autojunk=False).ratio()
    edit = 1.0 - levenshtein(left, right) / max_len
    return round(max(sequence, edit, 0.0), 6)


def _require_unique(rows: Sequence[Mapping[str, Any]], field: str, kind: str) -> None:
    values: set[str] = set()
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str) or not value:
            raise HTRV2InvariantError(f"{kind} missing {field}")
        if value in values:
            raise HTRV2InvariantError(f"duplicate {field}: {value}")
        values.add(value)


def _road_profile(row: Mapping[str, Any]) -> str:
    source_id = str(row.get("source_id") or "")
    if source_id.startswith("census:tigerline:2025:roads"):
        return "TIGER2025_ROAD"
    return "SIGE_ROAD"


def _hydro_profile(row: Mapping[str, Any]) -> str:
    source_id = str(row.get("source_id") or "")
    if source_id.startswith("drna:"):
        return "DRNA_RESERVOIR"
    if source_id.startswith("usgs:"):
        return "USGS_CONVEYANCE"
    return "HYDRO_FROZEN_V1"


def discover_candidates(
    hydro_registry: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    *,
    fuzzy_threshold: float = 0.86,
) -> list[dict[str, Any]]:
    """Discover lexical recurrence candidates while preserving source multiplicity."""
    if not 0 <= fuzzy_threshold <= 1:
        raise HTRV2InvariantError("fuzzy_threshold must be between 0 and 1")
    _require_unique(hydro_registry, "hydro_entity_id", "hydro manifestation")
    _require_unique(observations, "observation_id", "road observation")

    grouped: dict[str, list[tuple[Mapping[str, Any], dict[str, Any]]]] = defaultdict(list)
    for observation in observations:
        raw_name = observation.get("raw_name")
        if not isinstance(raw_name, str):
            raise HTRV2InvariantError("road observation missing raw_name")
        name = normalize_name(raw_name, _road_profile(observation))
        grouped[name["core"]].append((observation, name))

    hydro_names: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for hydro in hydro_registry:
        raw_name = hydro.get("raw_name")
        if not isinstance(raw_name, str):
            raise HTRV2InvariantError("hydro manifestation missing raw_name")
        name = normalize_name(raw_name, _hydro_profile(hydro))
        name["canonical"] = hydro.get("canonical_entity_id")
        hydro_names.append((hydro, name))

    results: list[dict[str, Any]] = []
    for road_core, members in sorted(grouped.items()):
        for hydro, hydro_name in hydro_names:
            hydro_core = hydro_name["core"]
            similarity = _similarity(road_core, hydro_core)
            if road_core == hydro_core:
                method = "EXACT_NORMALIZED_NAME"
                distance = 0
            elif similarity >= fuzzy_threshold:
                distance = levenshtein(road_core, hydro_core)
                method = "ORTHOGRAPHIC_NEAR_MATCH" if distance <= 2 else "FUZZY_MATCH"
            else:
                continue

            hydro_id = str(hydro["hydro_entity_id"])
            for observation, source_name in members:
                observation_id = str(observation["observation_id"])
                results.append(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "candidate_id": _stable_id(
                            "htr2",
                            observation_id,
                            hydro_id,
                            method,
                            source_name["raw"],
                            hydro_name["raw"],
                        ),
                        "source_observation_id": observation_id,
                        "source_feature_type": str(observation.get("feature_type") or "ROAD"),
                        "source_id": observation.get("source_id"),
                        "source_name": dict(source_name),
                        "hydro_entity_id": hydro_id,
                        "hydro_source_id": hydro.get("source_id"),
                        "hydro_name": dict(hydro_name),
                        "discovery_method": method,
                        "similarity": similarity,
                        "levenshtein_distance": distance,
                        "state": "CANDIDATE_NOT_IDENTITY",
                        "identity_state": "UNRESOLVED",
                        "pair_binding_state": "UNBOUND",
                        "identity_claim": False,
                        "connectivity_claim": False,
                        "transitive_context_inheritance": False,
                        "unsupported_reasons": [],
                        "contradictions": [],
                        "context": {
                            "observation": {
                                key: observation[key]
                                for key in sorted(observation)
                                if key != "raw_name"
                            },
                            "hydro": {
                                key: hydro[key] for key in sorted(hydro) if key != "raw_name"
                            },
                        },
                    }
                )
    return sorted(results, key=lambda row: row["candidate_id"])


def classify_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Apply fail-closed negative controls without deleting the source manifestation."""
    row = dict(candidate)
    source_name = dict(row.get("source_name") or {})
    hydro_name = dict(row.get("hydro_name") or {})
    hydro_context = dict((row.get("context") or {}).get("hydro") or {})
    reasons: list[str] = []

    raw_hydro = str(hydro_name.get("raw") or "").strip()
    if (
        hydro_context.get("name_manifestation_role") == "OTHER"
        and len(raw_hydro) == 1
        and raw_hydro.isalnum()
    ):
        reasons.extend(
            ["AMBIGUOUS_SINGLE_CHARACTER_OTHER_NAME", "LOW_INFORMATION_HYDRO_DISCOVERY_KEY"]
        )

    source_core = str(source_name.get("core") or "")
    hydro_core = str(hydro_name.get("core") or "")
    if (
        row.get("discovery_method") != "EXACT_NORMALIZED_NAME"
        and " " not in source_core
        and " " not in hydro_core
        and source_core
        and hydro_core
        and source_core[0] != hydro_core[0]
    ):
        reasons.append("WEAK_SINGLE_TOKEN_FUZZY_PREFIX_MISMATCH")

    hydro_tokens = set(str(hydro_name.get("source_normalized") or "").split())
    source_tokens = set(str(source_name.get("source_normalized") or "").split())
    if (
        source_core == "blanco"
        and hydro_core == "blanco"
        and {"rio", "river"} & hydro_tokens
        and not ({"rio", "river"} & source_tokens)
    ):
        reasons.append("RIVER_CLASS_TOKEN_COLLAPSE")

    if {source_core, hydro_core} == {"luchetti", "lucchetti"}:
        row["contradictions"] = ["ORTHOGRAPHIC_VARIANT_UNBOUND_LUCHETTI_LUCCHETTI"]

    row["unsupported_reasons"] = sorted(set(reasons))
    if row["unsupported_reasons"]:
        row["state"] = "UNSUPPORTED"
        row["relation_resolution"] = "UNSUPPORTED_FOR_RELATION_INFERENCE"
        row["adjudication_class"] = "UNSUPPORTED_DISCOVERY_SIGNAL"
    else:
        row["state"] = "CANDIDATE_NOT_IDENTITY"
        row["relation_resolution"] = "UNRESOLVED"
        row["adjudication_class"] = {
            "EXACT_NORMALIZED_NAME": "SUPPORTED_EXACT_NAME_RECURRENCE",
            "ORTHOGRAPHIC_NEAR_MATCH": "SUPPORTED_ORTHOGRAPHIC_RECURRENCE",
            "FUZZY_MATCH": "SUPPORTED_FUZZY_RECURRENCE",
        }[str(row["discovery_method"])]

    row["identity_state"] = "UNRESOLVED"
    row["pair_binding_state"] = "UNBOUND"
    row["identity_claim"] = False
    row["connectivity_claim"] = False
    row["transitive_context_inheritance"] = False
    row["adjudication_complete"] = True
    row["unexplained_residue"] = False
    return row


def adjudicate_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [classify_candidate(candidate) for candidate in candidates]
    assert_safe(rows)
    return sorted(rows, key=lambda row: row["candidate_id"])


def assert_safe(candidates: Sequence[Mapping[str, Any]]) -> None:
    """Fail closed on any identity/connectivity/pair-binding/transitive promotion."""
    for row in candidates:
        if row.get("state") not in {"CANDIDATE_NOT_IDENTITY", "UNSUPPORTED"}:
            raise HTRV2InvariantError(f"unsafe HTR state: {row.get('state')}")
        if row.get("identity_state") != "UNRESOLVED":
            raise HTRV2InvariantError("HTR v2 cannot resolve canonical identity")
        if row.get("pair_binding_state") != "UNBOUND":
            raise HTRV2InvariantError("HTR v2 discovery cannot bind candidate pairs")
        if row.get("identity_claim") is not False:
            raise HTRV2InvariantError("HTR v2 identity promotion detected")
        if row.get("connectivity_claim") is not False:
            raise HTRV2InvariantError("HTR v2 connectivity promotion detected")
        if row.get("transitive_context_inheritance") is not False:
            raise HTRV2InvariantError("HTR v2 transitive context inheritance detected")
