"""The desktop app's Launch Pad declaration is valid (federation template).

Rendered from thehub-pr/federation-templates/baseline/test_launchpad_declaration.py.
Change the template there and re-render; do not edit this copy.

A producer opts into the Launch Pad by declaring ``LAUNCHPAD`` in
``desktop/config.py``. The desktop launcher refuses to start on an invalid
declaration, so this test runs the same offline check in CI
(``python -m prii_desktop launchpad --check``): the declaration validates and
its readiness ``status`` provider runs without raising.

It skips when the repository has no desktop wrapper, when the shared runtime is
not installed in the test environment, or when the installed runtime predates
the check (prii-desktop < 0.4.0).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_launchpad_declaration_is_valid() -> None:
    if not (REPO_ROOT / "desktop" / "config.py").is_file():
        pytest.skip("no desktop wrapper in this repository")
    launchpad = pytest.importorskip("prii_desktop.launchpad")
    if not hasattr(launchpad, "check_declaration"):
        pytest.skip("installed prii-desktop predates the Launch Pad check")
    config = launchpad.load_config(REPO_ROOT, "desktop.config")
    assert launchpad.check_declaration(config) == []
