"""Federated lexical search over the federation streams the Hub already ingests.

A pure, read-only index: it holds no copy of any producer database, only the
canonical rows the Hub store already carries, and it never writes back.

Query semantics (TWIN-084, TWIN-090; filters TWIN-085..089):

* case- and accent-folded (``San Germán`` matches ``san german``);
* every query term must match (AND); a term matches a word that starts with it;
* an empty query returns nothing — it never lists the whole federation;
* synthetic rows are excluded by default and counted, so
  ``matched = visible + excluded_synthetic`` always holds;
* results are bounded and paginated with an opaque offset cursor.

Result kinds follow the stream a row came from: ``SOURCE`` (sources),
``ENTITY`` (entities), ``TIMELINE`` (alerts, and observations not declared
MEASURED) and ``READING`` (observations whose producer declares them
MEASURED). No producer emits findings yet, so ``FINDING`` is a declared,
always-empty type with an explicit ``type_status`` rather than a silently
missing one. Relationships are edges, not search subjects; the entity
composition surfaces them.
"""

from __future__ import annotations

import bisect
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from . import epistemic as ep
from .evidence_object import ID_FIELDS, evidence_id, record_title

CONTRACT_ID = "federation-search-v1"
SEARCH_STREAMS: Tuple[str, ...] = ("entities", "sources", "observations", "alerts")
SEARCH_TYPES: Tuple[str, ...] = ("ALL", "READING", "FINDING", "TIMELINE", "SOURCE", "ENTITY")
# Producers this run is scoped to (thehub-pr computes correlations). A producer
# with no indexed rows is reported NO_DATA; any other producer present in the
# store is reported as found, never assumed.
IN_SCOPE_PRODUCERS: Tuple[str, ...] = (
    "aguayluz-pr", "moneysweep-pr", "ovnis-pr", "skywatcher-pr", "spiderweb-pr",
)
MAX_LIMIT = 100
DEFAULT_LIMIT = 25

_WORD = re.compile(r"[a-z0-9]+")
_TEXT_FIELDS = (
    "name", "normalized_name", "source_name", "title", "location_name", "municipality",
    "entity_type", "observation_type", "object_type", "alert_type", "source_type",
    "module", "description", "summary", "jurisdiction", "source_ref",
)
_STREAM_ORDER = {stream: index for index, stream in enumerate(SEARCH_STREAMS)}


def fold(text: Any) -> str:
    """Lowercase and strip diacritics (NFKD) so Spanish accents never block a match."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def words(text: Any) -> List[str]:
    return _WORD.findall(fold(text))


def result_kind(stream: str, row: Mapping[str, Any]) -> str:
    if stream == "sources":
        return "SOURCE"
    if stream == "entities":
        return "ENTITY"
    if stream == "observations" and ep.declared(row).get("epistemic_class") == "MEASURED":
        return "READING"
    return "TIMELINE"


def _searchable_text(stream: str, record_id: str, row: Mapping[str, Any]) -> str:
    parts: List[str] = [record_id]
    for key in _TEXT_FIELDS:
        value = row.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            parts.append(str(value))
    location = ep.as_mapping(row.get("location"))
    if location.get("municipality"):
        parts.append(str(location["municipality"]))
    for key in ("external_ids", "attributes"):
        for value in ep.as_mapping(row.get(key)).values():
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                parts.append(str(value))
    return " ".join(parts)


@dataclass(frozen=True)
class SearchDoc:
    stream: str
    collection: str
    record_id: str
    row: Mapping[str, Any]
    kind: str
    title: str
    title_words: Tuple[str, ...]
    producers: Tuple[str, ...]
    synthetic: bool


@dataclass
class FederatedSearchIndex:
    """Inverted word index over canonical stream rows. Build once per store state."""

    docs: List[SearchDoc] = field(default_factory=list)
    _postings: Dict[str, Set[int]] = field(default_factory=dict)
    _vocabulary: List[str] = field(default_factory=list)

    @classmethod
    def build(cls, rows: Iterable[Tuple[str, str, Mapping[str, Any]]]) -> "FederatedSearchIndex":
        """``rows`` yields ``(stream, collection, row)``; rows without an id are skipped."""
        index = cls()
        for stream, collection, row in rows:
            if stream not in SEARCH_STREAMS:
                continue
            record_id = str(row.get(ID_FIELDS[stream]) or row.get("id") or "")
            if not record_id:
                continue
            title = record_title(row, record_id)
            doc = SearchDoc(
                stream=stream, collection=collection, record_id=record_id, row=row,
                kind=result_kind(stream, row), title=title, title_words=tuple(words(title)),
                producers=tuple(str(p) for p in row.get("_producers") or []),
                synthetic=bool(row.get("synthetic", False)),
            )
            position = len(index.docs)
            index.docs.append(doc)
            for word in set(words(_searchable_text(stream, record_id, row))):
                index._postings.setdefault(word, set()).add(position)
        index._vocabulary = sorted(index._postings)
        return index

    def _matching(self, term: str) -> Set[int]:
        """Docs holding a word that starts with ``term``."""
        hits: Set[int] = set()
        start = bisect.bisect_left(self._vocabulary, term)
        for word in self._vocabulary[start:]:
            if not word.startswith(term):
                break
            hits |= self._postings[word]
        return hits

    def producer_availability(self) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        for doc in self.docs:
            for producer in doc.producers or ("unattributed",):
                counts[producer] = counts.get(producer, 0) + 1
        names = sorted(set(IN_SCOPE_PRODUCERS) | set(counts))
        return [
            {"producer": name, "status": "AVAILABLE" if counts.get(name) else "NO_DATA",
             "indexed_records": counts.get(name, 0)}
            for name in names
        ]

    def search(
        self,
        query: str,
        *,
        kind: str = "ALL",
        include_synthetic: bool = False,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> Dict[str, Any]:
        if kind not in SEARCH_TYPES:
            raise ValueError(f"unknown search type {kind!r}; expected one of {', '.join(SEARCH_TYPES)}")
        limit = max(1, min(int(limit), MAX_LIMIT))
        offset = max(0, int(offset))
        terms = list(dict.fromkeys(words(query)))
        response: Dict[str, Any] = {
            "contract": CONTRACT_ID,
            "query": query,
            "terms": terms,
            "type": kind,
            "type_status": "OK",
            "query_status": "OK",
            "include_synthetic": include_synthetic,
            "indexed_records": len(self.docs),
            "matched": 0,
            "excluded_synthetic": 0,
            "total": 0,
            "results": [],
            "next_cursor": None,
            "producers": self.producer_availability(),
        }
        if kind == "FINDING":
            response["type_status"] = "NO_PRODUCER_EMITS_FINDINGS"
        if not terms:
            response["query_status"] = "EMPTY_QUERY"
            return response
        if kind == "FINDING":
            return response

        candidates: Optional[Set[int]] = None
        for term in terms:
            hits = self._matching(term)
            candidates = hits if candidates is None else candidates & hits
            if not candidates:
                break
        matched = [self.docs[i] for i in sorted(candidates or set()) if kind == "ALL" or self.docs[i].kind == kind]
        visible = [doc for doc in matched if include_synthetic or not doc.synthetic]
        visible.sort(key=lambda doc: _rank(doc, terms))

        response["matched"] = len(matched)
        response["excluded_synthetic"] = len(matched) - len(visible)
        response["total"] = len(visible)
        page = visible[offset:offset + limit]
        response["results"] = [_result(doc) for doc in page]
        if offset + limit < len(visible):
            response["next_cursor"] = str(offset + limit)
        return response


def _rank(doc: SearchDoc, terms: Sequence[str]) -> Tuple[int, int, int, int, str]:
    exact = sum(1 for term in terms if term in doc.title_words)
    prefix = sum(1 for term in terms if any(word.startswith(term) for word in doc.title_words))
    return (-exact, -prefix, _STREAM_ORDER[doc.stream], len(doc.title), doc.record_id)


def _result(doc: SearchDoc) -> Dict[str, Any]:
    row = doc.row
    declared = ep.declared(row)
    source_ids = sorted({str(v) for v in (row.get("source_id"), row.get("evidence_source_id")) if v})
    return {
        "evidence_id": evidence_id(doc.stream, doc.record_id),
        "stream": doc.stream,
        "collection": doc.collection,
        "record_id": doc.record_id,
        "kind": doc.kind,
        "title": doc.title,
        "type": str(row.get("entity_type") or row.get("observation_type") or row.get("alert_type")
                    or row.get("source_type") or doc.stream),
        "producers": list(doc.producers),
        "synthetic": doc.synthetic,
        "declared_epistemic_class": declared.get("epistemic_class"),
        "source_ids": source_ids,
        "evidence_href": f"/evidence/{doc.collection}/{doc.record_id}",
        "entity_href": f"/entity/{doc.record_id}" if doc.stream == "entities" else None,
    }


def parse_cursor(cursor: Optional[str]) -> int:
    """Opaque cursor -> offset. Anything that is not a non-negative integer is rejected."""
    if cursor in (None, ""):
        return 0
    if not str(cursor).isdigit():
        raise ValueError("invalid cursor")
    return int(str(cursor))
