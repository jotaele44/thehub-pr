"""Metrics sink backends beyond the in-memory collector.

`LoggingMetricsSink` is fully real with no external dependency — it emits one
structured JSON line per metric. `HttpMetricsSink` pushes each metric to an
env-configured collector via an injectable poster (a live collector is
operator config, not exercised in CI). `MultiMetricsSink` fans out to several
sinks so the in-memory aggregates (for `/mcp/metrics`) and a durable log/push
can coexist.

Metrics carry names and counts only — never request params or credentials —
so every sink here is safe.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import urllib.request
from typing import Any, Callable, Dict, Iterable, List

from hub.mcp_runtime.telemetry import Metric, MetricsSink


def _metric_dict(metric: Metric) -> Dict[str, Any]:
    return dataclasses.asdict(metric)


class LoggingMetricsSink:
    """Emit each metric as a structured JSON log line. No external backend."""

    def __init__(self, logger_name: str = "hub.mcp.metrics") -> None:
        self._logger = logging.getLogger(logger_name)

    def record(self, metric: Metric) -> None:
        self._logger.info(json.dumps(_metric_dict(metric), sort_keys=True))


class HttpMetricsSink:
    """POST each metric as JSON to a collector URL via an injectable poster."""

    def __init__(
        self,
        url: str,
        poster: Callable[[str, Dict[str, Any]], None] | None = None,
    ) -> None:
        self._url = url
        self._poster = poster if poster is not None else self._urllib_poster

    @staticmethod
    def _urllib_poster(url: str, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(request, timeout=5).close()

    def record(self, metric: Metric) -> None:
        # A metrics push must never break request handling; swallow errors.
        try:
            self._poster(self._url, _metric_dict(metric))
        except Exception:
            logging.getLogger("hub.mcp.metrics").warning(
                "metrics push failed", exc_info=False
            )


class MultiMetricsSink:
    """Fan a metric out to several sinks (e.g. in-memory + logging)."""

    def __init__(self, sinks: Iterable[MetricsSink]) -> None:
        self._sinks: List[MetricsSink] = list(sinks)

    @property
    def sinks(self) -> List[MetricsSink]:
        return self._sinks

    def record(self, metric: Metric) -> None:
        for sink in self._sinks:
            sink.record(metric)
