from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Classification(str, Enum):
    EXECUTABLE_CONFIRMED = "EXECUTABLE_CONFIRMED"
    EXECUTABLE_BY_CONTRACT = "EXECUTABLE_BY_CONTRACT"
    WIRED_BUT_BLOCKED = "WIRED_BUT_BLOCKED"
    PARTIALLY_WIRED = "PARTIALLY_WIRED"
    UI_NO_OP = "UI_NO_OP"
    TARGET_MISSING = "TARGET_MISSING"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    UNREACHABLE = "UNREACHABLE"
    PLACEHOLDER = "PLACEHOLDER"
    RUNTIME_FAILURE = "RUNTIME_FAILURE"
    PRECONDITION_UNDECLARED = "PRECONDITION_UNDECLARED"
    UNSAFE_TO_PROBE = "UNSAFE_TO_PROBE"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class Evidence:
    tier: str
    kind: str
    locator: str
    digest: str | None = None


@dataclass
class Trace:
    trace_id: str
    repository: str
    commit: str
    surface: dict[str, Any]
    path: list[dict[str, Any]] = field(default_factory=list)
    observations: dict[str, Any] = field(default_factory=dict)
    classification: Classification = Classification.INDETERMINATE
    fault_boundary: str | None = None
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    recommended_fix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["classification"] = self.classification.value
        return result
