"""Federation-wide check-running primitives for the "doctor" diagnostics tool.

Public API:
- ``DiagnosabilityClass``, ``CheckStatus``, ``CheckResult``, ``CheckReport``
  -- the generalized result types (promoted from aguayluz-pr's
  ``Gate``/``GateResult`` shape in ``src/aguayluz/validation.py``).
- ``run(repo_root)`` -- runs every check in a repo's
  ``.federation/doctor-checks.json``.
- ``print_table(report)`` / ``to_gui_dicts(report)`` -- CLI and
  desktop-GUI renderers.

The central design constraint: a check's ``diagnosability_class`` bounds
which statuses it may ever report, enforced by ``CheckResult`` itself at
construction time. A check that cannot verify something (a WAF-gated API, a
manual file-drop pipeline, cross-repo state) must never render a green PASS.
"""

from __future__ import annotations

from .engine import run
from .manifest import CheckSpec, DoctorManifest, ManifestError
from .manifest import load as load_manifest
from .render import print_table, to_gui_dicts
from .types import CheckReport, CheckResult, CheckStatus, DiagnosabilityClass

__all__ = [
    "CheckReport",
    "CheckResult",
    "CheckSpec",
    "CheckStatus",
    "DiagnosabilityClass",
    "DoctorManifest",
    "ManifestError",
    "load_manifest",
    "print_table",
    "run",
    "to_gui_dicts",
]
__version__ = "0.1.0"
