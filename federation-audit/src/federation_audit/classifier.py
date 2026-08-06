from __future__ import annotations

from .models import Classification, Trace


def classify_observations(observations: dict[str, object]) -> tuple[Classification, float, str | None, str]:
    """Apply fail-closed deterministic precedence to one executability trace."""
    if observations.get("unsafe_boundary"):
        return Classification.UNSAFE_TO_PROBE, 0.98, "side-effect-boundary", "Add an emulator or approved interceptor."
    if observations.get("runtime_failure"):
        return Classification.RUNTIME_FAILURE, 0.98, "runtime", "Repair the recorded exception before re-probing."
    if observations.get("placeholder"):
        return Classification.PLACEHOLDER, 0.97, "implementation", "Replace the stub with a contract-backed implementation."
    if observations.get("unreachable"):
        return Classification.UNREACHABLE, 0.95, "navigation-or-dispatch", "Add a normal route, command, or workflow edge."
    if observations.get("undeclared_precondition"):
        return Classification.PRECONDITION_UNDECLARED, 0.94, "precondition", "Declare and validate the hidden precondition."
    if observations.get("contract_mismatch"):
        return Classification.CONTRACT_MISMATCH, 0.99, "caller-to-target-contract", "Align method, path, and payload schema."
    if observations.get("target_missing") or (observations.get("handler_bound") and observations.get("handler_resolved") is False):
        return Classification.TARGET_MISSING, 0.99, "dispatch-target", "Implement the target or correct the binding."
    if observations.get("handler_bound") is False:
        return Classification.UI_NO_OP, 0.99, "gui-to-handler", "Bind a meaningful handler or render a non-action control."
    if observations.get("blocked_precondition"):
        return Classification.WIRED_BUT_BLOCKED, 0.95, "dependency-or-precondition", "Satisfy or explicitly surface the blocking condition."
    if observations.get("terminal_observed") and observations.get("side_effect_intercepted"):
        return Classification.EXECUTABLE_CONFIRMED, 0.99, None, "Retain the evidence bundle as a regression test."
    if observations.get("boundary_reached") and observations.get("contract_matched") and (observations.get("side_effect_intercepted") or observations.get("static_contract_resolved")):
        return Classification.EXECUTABLE_BY_CONTRACT, 0.97, None, "Graduate to a disposable shadow dependency for runtime confirmation."
    if observations.get("handler_bound") and (observations.get("intent_observed") or observations.get("handler_resolved")):
        return Classification.PARTIALLY_WIRED, 0.88, "handler-to-terminal", "Complete and expose the downstream terminal path."
    return Classification.INDETERMINATE, 0.5, None, "Collect T1 or T2 evidence for the unresolved path."


def classify_trace(trace: Trace) -> Trace:
    classification, confidence, boundary, fix = classify_observations(trace.observations)
    trace.classification = classification
    trace.confidence = confidence
    trace.fault_boundary = boundary
    trace.recommended_fix = fix
    return trace
