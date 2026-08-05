"""Telemetry — one metric per routing decision.

Metrics carry names and counts only (capability, action, adapter, decision,
duration, cache-hit, status) — never request params or credentials — so they
are safe to expose over the introspection endpoint. `InMemoryMetrics` is the
default collector for tests and the hosted `/mcp/metrics` view; a
`MetricsSink` can forward to an external backend later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol


@dataclass
class Metric:
    capability: str
    action: str
    decision: str  # allowed | denied | error
    duration_s: float
    cache_hit: bool
    adapter: Optional[str] = None
    status: Optional[str] = None


class MetricsSink(Protocol):
    def record(self, metric: Metric) -> None:
        ...


class InMemoryMetrics:
    """Collects metrics and computes simple aggregates for dashboards/tests."""

    def __init__(self) -> None:
        self.metrics: List[Metric] = []

    def record(self, metric: Metric) -> None:
        self.metrics.append(metric)

    def count(self) -> int:
        return len(self.metrics)

    def error_rate(self) -> float:
        if not self.metrics:
            return 0.0
        errors = sum(1 for m in self.metrics if m.decision == "error")
        return errors / len(self.metrics)

    def cache_hit_rate(self) -> float:
        # Denominator is allowed responses (only reads are cacheable); a
        # denied/errored request never had a chance to hit the cache.
        served = [m for m in self.metrics if m.decision == "allowed"]
        if not served:
            return 0.0
        return sum(1 for m in served if m.cache_hit) / len(served)

    def _tally(self, key: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for metric in self.metrics:
            value = getattr(metric, key)
            if value is not None:
                counts[value] = counts.get(value, 0) + 1
        return counts

    def by_capability(self) -> Dict[str, int]:
        return self._tally("capability")

    def by_adapter(self) -> Dict[str, int]:
        return self._tally("adapter")

    def by_decision(self) -> Dict[str, int]:
        return self._tally("decision")

    def aggregates(self) -> Dict[str, object]:
        return {
            "count": self.count(),
            "error_rate": self.error_rate(),
            "cache_hit_rate": self.cache_hit_rate(),
            "by_capability": self.by_capability(),
            "by_adapter": self.by_adapter(),
            "by_decision": self.by_decision(),
        }
