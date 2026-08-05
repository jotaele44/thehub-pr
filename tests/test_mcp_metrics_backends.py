import json
import logging

from hub.mcp_runtime import (
    HttpMetricsSink,
    InMemoryMetrics,
    LoggingMetricsSink,
    MultiMetricsSink,
)
from hub.mcp_runtime.telemetry import Metric


def _metric(**kw):
    base = dict(
        capability="weather", action="forecast", decision="allowed",
        duration_s=0.01, cache_hit=False, adapter="weather-nws", status="ok",
    )
    base.update(kw)
    return Metric(**base)


def test_logging_sink_emits_json_line(caplog):
    sink = LoggingMetricsSink()
    with caplog.at_level(logging.INFO, logger="hub.mcp.metrics"):
        sink.record(_metric())
    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].message)
    assert payload["capability"] == "weather"
    assert payload["decision"] == "allowed"
    assert payload["cache_hit"] is False


def test_http_sink_posts_via_fake_poster():
    posted = []
    sink = HttpMetricsSink("https://collector.example/metrics",
                           poster=lambda url, payload: posted.append((url, payload)))
    sink.record(_metric(decision="error", status=None))
    url, payload = posted[0]
    assert url == "https://collector.example/metrics"
    assert payload["decision"] == "error"


def test_http_sink_swallows_poster_errors(caplog):
    def boom(url, payload):
        raise RuntimeError("collector down")

    sink = HttpMetricsSink("https://collector.example/metrics", poster=boom)
    with caplog.at_level(logging.WARNING, logger="hub.mcp.metrics"):
        sink.record(_metric())  # must not raise
    assert any("push failed" in r.message for r in caplog.records)


def test_multi_sink_fans_out():
    mem = InMemoryMetrics()
    posted = []
    multi = MultiMetricsSink([
        mem,
        HttpMetricsSink("u", poster=lambda url, payload: posted.append(payload)),
    ])
    multi.record(_metric())
    multi.record(_metric(decision="denied"))
    assert mem.count() == 2
    assert len(posted) == 2
    assert mem.by_decision() == {"allowed": 1, "denied": 1}
