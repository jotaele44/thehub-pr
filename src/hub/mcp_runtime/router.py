"""Router — resolve capability requests to adapters through the policy gate.

Hardened with priority-ordered fallback, a per-adapter circuit breaker, and
an audit sink. Governance is never bypassed: policy denials raise up front and
are not retried; only adapter *execution* failures fall through to the next
candidate.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional, Tuple

from hub.mcp_runtime.policy import PolicyEngine, PolicyViolation
from hub.mcp_runtime.registry import RuntimeRegistry
from hub.mcp_runtime.sdk import AdapterResult, MCPAdapter, MCPRequest


class _CircuitBreaker:
    """Per-adapter breaker: opens after N consecutive failures, cools down,
    then allows a single half-open probe before closing or re-opening."""

    def __init__(self, threshold: int, cooldown: float, clock: Callable[[], float]):
        self._threshold = threshold
        self._cooldown = cooldown
        self._clock = clock
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._half_open = False

    def allow(self) -> bool:
        if self._opened_at is None:
            return True  # closed
        if self._clock() - self._opened_at >= self._cooldown:
            self._half_open = True  # one probe permitted
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._half_open = False

    def record_failure(self) -> None:
        self._failures += 1
        if self._half_open or self._failures >= self._threshold:
            self._opened_at = self._clock()
            self._half_open = False


class Router:
    """Capability -> adapter resolution and gated execution.

    Each request traverses: policy access check -> write classification +
    write check -> priority-ordered adapter attempts (skipping open breakers,
    falling through execution failures) -> provenance-stamped result. The
    optional `provenance_sink` receives each *successful* result's provenance;
    the optional `audit_sink` receives one record per `route()` call
    (allowed/denied/error), including the per-adapter attempt trail.
    """

    def __init__(
        self,
        registry: RuntimeRegistry,
        policy: Optional[PolicyEngine] = None,
        provenance_sink: Optional[Callable[[Dict], None]] = None,
        audit_sink: Optional[Callable[[Dict], None]] = None,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.registry = registry
        self.policy = policy or PolicyEngine(registry)
        self.provenance_sink = provenance_sink
        self.audit_sink = audit_sink
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        # capability -> [(priority, seq, adapter)], kept priority-sorted
        self._adapters: Dict[str, List[Tuple[int, int, MCPAdapter]]] = {}
        self._breakers: Dict[int, _CircuitBreaker] = {}
        self._seq = 0

    def register_adapter(self, adapter: MCPAdapter, priority: int = 0) -> None:
        if not adapter.health_check():
            raise ValueError(f"adapter {adapter.name()!r} failed health check")
        self._breakers.setdefault(
            id(adapter),
            _CircuitBreaker(self._failure_threshold, self._cooldown_seconds, self._clock),
        )
        for capability in adapter.capabilities():
            bucket = self._adapters.setdefault(capability, [])
            bucket.append((priority, self._seq, adapter))
            bucket.sort(key=lambda entry: (entry[0], entry[1]))
            self._seq += 1

    def _candidates(self, capability: str) -> List[MCPAdapter]:
        return [adapter for _, _, adapter in self._adapters.get(capability, [])]

    def resolve(self, capability: str) -> MCPAdapter:
        candidates = self._candidates(capability)
        if not candidates:
            raise LookupError(f"no adapter registered for capability {capability!r}")
        return candidates[0]

    def _emit_audit(
        self,
        request: MCPRequest,
        decision: str,
        adapter: Optional[str],
        attempts: List[Dict],
        reason: str,
    ) -> None:
        if self.audit_sink is None:
            return
        self.audit_sink({
            "project": request.project,
            "capability": request.capability,
            "action": request.action,
            "decision": decision,
            "adapter": adapter,
            "attempts": attempts,
            "reason": reason,
        })

    def route(self, request: MCPRequest) -> AdapterResult:
        # 1. Access policy — a denial never falls back.
        try:
            self.policy.check_access(request)
        except PolicyViolation as exc:
            self._emit_audit(request, "denied", None, [], str(exc))
            raise

        candidates = self._candidates(request.capability)
        if not candidates:
            reason = f"no adapter registered for capability {request.capability!r}"
            self._emit_audit(request, "error", None, [], reason)
            raise LookupError(reason)

        # 2. Write classification is the strictest across candidates, so a
        #    caller can never conceal a write by hitting a read-only adapter.
        is_write = request.is_write or any(
            a.is_write_action(request.action) for a in candidates
        )
        try:
            self.policy.check_write(request, is_write)
        except PolicyViolation as exc:
            self._emit_audit(request, "denied", None, [], str(exc))
            raise

        # 3. Priority-ordered attempts, skipping open breakers.
        attempts: List[Dict] = []
        last_exc: Optional[Exception] = None
        for adapter in candidates:
            breaker = self._breakers[id(adapter)]
            if not breaker.allow():
                attempts.append({"adapter": adapter.name(), "outcome": "skipped:circuit_open"})
                continue
            try:
                result = adapter.run(request)
            except Exception as exc:  # execution failure -> fall through
                breaker.record_failure()
                attempts.append({
                    "adapter": adapter.name(),
                    "outcome": f"error:{type(exc).__name__}",
                })
                last_exc = exc
                continue
            breaker.record_success()
            attempts.append({"adapter": adapter.name(), "outcome": "ok"})
            capability = self.registry.capabilities.get(request.capability)
            if capability is not None:
                result.provenance["version_pin"] = capability.version_pin
            if self.provenance_sink is not None:
                self.provenance_sink(dict(result.provenance))
            self._emit_audit(request, "allowed", adapter.name(), attempts, "ok")
            return result

        # 4. Everything failed or was skipped.
        if last_exc is not None:
            self._emit_audit(request, "error", None, attempts, str(last_exc))
            raise last_exc
        reason = (
            f"no available adapter for capability {request.capability!r} "
            f"(circuit breakers open)"
        )
        self._emit_audit(request, "error", None, attempts, reason)
        raise LookupError(reason)
