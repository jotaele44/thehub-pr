"""Generalized check-result types for the federation doctor tool.

Promotes the *shape* of aguayluz-pr's Gate/GateResult pattern
(``src/aguayluz/validation.py``) into a repo-agnostic form. The central
invariant this module exists to enforce: a check's ``DiagnosabilityClass``
bounds which ``CheckStatus`` values it is allowed to report. A check that
cannot actually verify something (a WAF-gated API, a manual file-drop
pipeline, cross-repo state) must never report a false PASS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

CheckStatus = Literal["PASS", "WARN", "FAIL", "SKIP", "INFO"]


class DiagnosabilityClass(str, Enum):
    """How authoritatively a check can speak to the thing it inspects.

    - ``LOCAL_DETERMINISTIC``: the doctor can compute a real answer offline
      (schema validation, ledger integrity, a delegated gate suite). Full
      PASS/WARN/FAIL/SKIP vocabulary is available.
    - ``PRESENCE_ONLY``: an env var or file's *existence* is checkable; its
      *validity* is not (API keys, credential files). Presence never means
      "this credential works" -- it only ever renders INFO, or, when
      absent, FAIL/WARN depending on declared severity.
    - ``LIVE_PROBE_BEST_EFFORT``: a live network call is possible, but a
      failure is ambiguous (WAF block vs. rate limit vs. genuine outage).
      A clean success is PASS; anything ambiguous is WARN (never FAIL,
      since the doctor cannot tell whether the *source* or the *check* is
      at fault); only an unambiguous connection-level failure (DNS,
      connection refused) is FAIL.
    - ``NOT_AUTOMATABLE``: no check runs at all -- manual file-drop
      pipelines, ToS-gated scraping, cross-repo state this repo cannot
      compute. Always renders INFO, carrying the manifest's recorded
      ``last_known_state`` / ``operator_action`` verbatim. This class's
      runner performs zero I/O.
    """

    LOCAL_DETERMINISTIC = "local-deterministic"
    PRESENCE_ONLY = "presence-only"
    LIVE_PROBE_BEST_EFFORT = "live-probe-best-effort"
    NOT_AUTOMATABLE = "not-automatable"


# The invariant the whole design exists to guarantee: only a fully
# self-computed, LOCAL_DETERMINISTIC check may report PASS unconditionally --
# LIVE_PROBE_BEST_EFFORT may also PASS, but only for a genuinely clean,
# unambiguous live result. Every runner is expected to honor this by
# construction (see runners.py, each of which hardcodes the class it is
# entitled to produce); CheckResult itself additionally refuses to construct
# an illegal combination, so a runner bug surfaces immediately as a crash
# rather than a silently wrong green checkmark.
_STATUSES_ALLOWED_BY_CLASS: dict[DiagnosabilityClass, frozenset[str]] = {
    DiagnosabilityClass.LOCAL_DETERMINISTIC: frozenset({"PASS", "WARN", "FAIL", "SKIP"}),
    DiagnosabilityClass.PRESENCE_ONLY: frozenset({"INFO", "WARN", "FAIL"}),
    DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT: frozenset({"PASS", "WARN", "FAIL"}),
    DiagnosabilityClass.NOT_AUTOMATABLE: frozenset({"INFO"}),
}


def status_allowed(diagnosability_class: DiagnosabilityClass, status: str) -> bool:
    """True if `status` is a legal outcome for a check of this class."""
    return status in _STATUSES_ALLOWED_BY_CLASS.get(diagnosability_class, frozenset())


@dataclass
class CheckResult:
    check_id: str
    diagnosability_class: DiagnosabilityClass
    status: CheckStatus
    detail: str = ""
    operator_action: str = ""

    def __post_init__(self) -> None:
        if not status_allowed(self.diagnosability_class, self.status):
            allowed = sorted(_STATUSES_ALLOWED_BY_CLASS.get(self.diagnosability_class, frozenset()))
            raise ValueError(
                f"{self.check_id}: status {self.status!r} is not permitted for "
                f"diagnosability_class {self.diagnosability_class.value!r} (allowed: {allowed})"
            )

    @property
    def is_blocking_failure(self) -> bool:
        return self.status == "FAIL"


@dataclass
class CheckReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def all_blocking_passed(self) -> bool:
        return all(not r.is_blocking_failure for r in self.results)

    def by_id(self, check_id: str) -> CheckResult | None:
        return next((r for r in self.results if r.check_id == check_id), None)

    def as_rows(self) -> list[tuple[str, str, str, str]]:
        return [(r.check_id, r.diagnosability_class.value, r.status, r.detail) for r in self.results]
