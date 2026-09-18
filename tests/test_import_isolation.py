from pathlib import Path

import hub


def test_hub_import_resolves_inside_active_checkout() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    imported_package = Path(hub.__file__).resolve()

    assert imported_package.is_relative_to(repository_root / "src" / "hub")
