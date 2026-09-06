from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from hub import _shared_transport_binding as binding


def _write_complete_fake_package(package_dir: Path) -> None:
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("VALUE = 'bound'\n", encoding="utf-8")


def _bind_fake_members(monkeypatch: pytest.MonkeyPatch, package_dir: Path) -> None:
    expected = {
        member.name: binding.git_blob_sha(member)
        for member in package_dir.iterdir()
        if member.is_file() and member.suffix == ".py"
    }
    monkeypatch.setattr(binding, "EXPECTED_SHARED_BLOBS", expected)


def _without_guard():
    return [
        finder
        for finder in sys.meta_path
        if not isinstance(finder, binding._ExactSharedPackageFinder)
    ]


def test_guard_is_installed_for_supported_runtime() -> None:
    assert any(
        isinstance(finder, binding._ExactSharedPackageFinder)
        for finder in sys.meta_path
    )


def test_exact_repository_source_members_match_frozen_blobs() -> None:
    package_dir = binding.source_checkout_shared_package()
    if package_dir is None:
        pytest.skip("isolated patch harness has no complete #260 source tree")
    assert binding.verify_shared_package_dir(package_dir) == package_dir.resolve()


def test_tampered_shared_member_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_dir = tmp_path / "prii_export_utils"
    _write_complete_fake_package(package_dir)
    _bind_fake_members(monkeypatch, package_dir)
    init = package_dir / "__init__.py"
    init.write_text("VALUE = 'tampered'\n", encoding="utf-8")

    with pytest.raises(binding.SharedTransportBindingError, match="does not match"):
        binding.verify_shared_package_dir(package_dir)


def test_missing_or_extra_member_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_dir = tmp_path / "prii_export_utils"
    _write_complete_fake_package(package_dir)
    _bind_fake_members(monkeypatch, package_dir)
    (package_dir / "unexpected.py").write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(binding.SharedTransportBindingError, match="member set"):
        binding.verify_shared_package_dir(package_dir)


def test_authoritative_source_precedes_installed_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_dir = tmp_path / "prii_export_utils"
    _write_complete_fake_package(package_dir)
    _bind_fake_members(monkeypatch, package_dir)
    monkeypatch.setattr(binding, "source_checkout_shared_package", lambda: package_dir)
    monkeypatch.setattr(
        binding,
        "installed_shared_package",
        lambda: (_ for _ in ()).throw(AssertionError("installed candidate used")),
    )

    assert binding.authoritative_shared_package() == package_dir.resolve()


def test_finder_loads_only_the_verified_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_dir = tmp_path / "prii_export_utils"
    _write_complete_fake_package(package_dir)
    _bind_fake_members(monkeypatch, package_dir)
    monkeypatch.setattr(binding, "source_checkout_shared_package", lambda: package_dir)
    finder = binding._ExactSharedPackageFinder()

    spec = finder.find_spec(binding.SHARED_PACKAGE_NAME)

    assert spec is not None
    assert Path(spec.origin or "").resolve() == (package_dir / "__init__.py").resolve()
    assert finder.find_spec("unrelated_package") is None


def test_finder_converts_binding_failure_to_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        binding,
        "authoritative_shared_package",
        lambda: (_ for _ in ()).throw(
            binding.SharedTransportBindingError("wrong shared bytes")
        ),
    )

    with pytest.raises(ImportError, match="wrong shared bytes"):
        binding._ExactSharedPackageFinder().find_spec(binding.SHARED_PACKAGE_NAME)


def test_guard_evicts_preloaded_non_authoritative_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_dir = tmp_path / "authoritative" / "prii_export_utils"
    _write_complete_fake_package(package_dir)
    _bind_fake_members(monkeypatch, package_dir)
    monkeypatch.setattr(binding, "source_checkout_shared_package", lambda: package_dir)

    loaded = ModuleType(binding.SHARED_PACKAGE_NAME)
    loaded.__file__ = str(tmp_path / "other" / "prii_export_utils" / "__init__.py")
    child = ModuleType(f"{binding.SHARED_PACKAGE_NAME}.artifact_transport")
    sys.modules[binding.SHARED_PACKAGE_NAME] = loaded
    sys.modules[child.__name__] = child
    original_meta_path = list(sys.meta_path)
    sys.meta_path[:] = _without_guard()
    try:
        binding.install_import_guard()
        assert binding.SHARED_PACKAGE_NAME not in sys.modules
        assert child.__name__ not in sys.modules
        assert isinstance(sys.meta_path[0], binding._ExactSharedPackageFinder)
    finally:
        binding._remove_loaded_package()
        sys.meta_path[:] = original_meta_path


def test_guard_is_idempotent_and_python39_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_meta_path = list(sys.meta_path)
    try:
        sys.meta_path[:] = _without_guard()
        binding.install_import_guard()
        binding.install_import_guard()
        assert sum(
            isinstance(finder, binding._ExactSharedPackageFinder)
            for finder in sys.meta_path
        ) == 1

        sys.meta_path[:] = _without_guard()
        monkeypatch.setattr(binding.sys, "version_info", (3, 9, 99))
        binding.install_import_guard()
        assert not any(
            isinstance(finder, binding._ExactSharedPackageFinder)
            for finder in sys.meta_path
        )
    finally:
        sys.meta_path[:] = original_meta_path


def test_verified_preloaded_authoritative_package_is_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_dir = tmp_path / "prii_export_utils"
    _write_complete_fake_package(package_dir)
    _bind_fake_members(monkeypatch, package_dir)
    monkeypatch.setattr(binding, "source_checkout_shared_package", lambda: package_dir)

    loaded = ModuleType(binding.SHARED_PACKAGE_NAME)
    loaded.__file__ = str(package_dir / "__init__.py")
    sys.modules[binding.SHARED_PACKAGE_NAME] = loaded
    original_meta_path = list(sys.meta_path)
    sys.meta_path[:] = _without_guard()
    try:
        binding.install_import_guard()
        assert sys.modules[binding.SHARED_PACKAGE_NAME] is loaded
    finally:
        binding._remove_loaded_package()
        sys.meta_path[:] = original_meta_path


def test_installed_discovery_and_blob_read_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        binding.importlib.machinery.PathFinder,
        "find_spec",
        lambda _fullname, _path=None, _target=None: None,
    )
    with pytest.raises(binding.SharedTransportBindingError, match="unavailable"):
        binding.installed_shared_package()

    class BadSpec:
        origin = str(tmp_path / "not-init.py")

    monkeypatch.setattr(
        binding.importlib.machinery.PathFinder,
        "find_spec",
        lambda _fullname, _path=None, _target=None: BadSpec(),
    )
    with pytest.raises(binding.SharedTransportBindingError, match="unsupported"):
        binding.installed_shared_package()

    directory = tmp_path / "not-a-file"
    directory.mkdir()
    with pytest.raises(binding.SharedTransportBindingError, match="cannot read"):
        binding.git_blob_sha(directory)


def test_loaded_package_without_file_has_no_binding() -> None:
    loaded = ModuleType(binding.SHARED_PACKAGE_NAME)
    sys.modules[binding.SHARED_PACKAGE_NAME] = loaded
    try:
        assert binding._loaded_package_dir() is None
    finally:
        binding._remove_loaded_package()
