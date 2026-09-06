"""Exact-source import guard for TheHub's local artifact transport.

The guard binds the complete Python source-member set carried by
``prii-export-utils`` at TheHub #260. It does not prove whole-wheel identity,
retained transitive dependencies, or a disconnected rebuild.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Optional

SHARED_PACKAGE_NAME = "prii_export_utils"
SHARED_PACKAGE_DECLARED_VERSION = "0.2.1"
SHARED_PACKAGE_PARENT_SHA = "2a8b662262130fc9013a7bc5016a6c74117e8c4a"
EXPECTED_SHARED_BLOBS: Dict[str, str] = {
    "__init__.py": "8e22ab3332d266259e211b55b5fb3a6bd55c8d7d",
    "artifact_mirror.py": "25d36d61fa393ac1236a1f2d46499b96aeb8dc13",
    "artifact_transport.py": "45043023bbcd34e214256a4f71b28b0765cc74ab",
    "helpers.py": "1f15f759fd30b7443d1281d47ebf75f757f1c0c4",
}


class SharedTransportBindingError(RuntimeError):
    """Raised when shared-package source identity cannot be established."""


def git_blob_sha(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise SharedTransportBindingError(
            f"cannot read shared package file {path}: {exc}"
        ) from exc
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object ID


def verify_shared_package_dir(package_dir: Path) -> Path:
    """Require the exact complete Python member set and #260 Git blob IDs."""

    if package_dir.is_symlink() or not package_dir.is_dir():
        raise SharedTransportBindingError(
            f"shared package path is not a regular directory: {package_dir}"
        )
    expected_names = set(EXPECTED_SHARED_BLOBS)
    try:
        observed_names = {
            member.name
            for member in package_dir.iterdir()
            if member.is_file() and member.suffix == ".py"
        }
    except OSError as exc:
        raise SharedTransportBindingError(
            f"cannot inspect shared package directory {package_dir}: {exc}"
        ) from exc
    if observed_names != expected_names:
        raise SharedTransportBindingError(
            "shared package member set does not match exact TheHub #260 source: "
            f"missing={sorted(expected_names - observed_names)} "
            f"extra={sorted(observed_names - expected_names)}"
        )
    for name, expected_sha in sorted(EXPECTED_SHARED_BLOBS.items()):
        member = package_dir / name
        if member.is_symlink() or not member.is_file():
            raise SharedTransportBindingError(
                f"shared package member is not a regular file: {member}"
            )
        actual_sha = git_blob_sha(member)
        if actual_sha != expected_sha:
            raise SharedTransportBindingError(
                f"shared package member {name} does not match exact TheHub #260 "
                f"blob: expected={expected_sha} actual={actual_sha}"
            )
    return package_dir.resolve()


def source_checkout_shared_package() -> Optional[Path]:
    candidate = (
        Path(__file__).resolve().parents[2]
        / "packages"
        / "prii_export_utils"
        / "src"
        / SHARED_PACKAGE_NAME
    )
    return candidate if candidate.exists() else None


def installed_shared_package() -> Path:
    spec = importlib.machinery.PathFinder.find_spec(SHARED_PACKAGE_NAME, sys.path)
    if spec is None or spec.origin is None:
        raise SharedTransportBindingError(
            "prii_export_utils is unavailable; install the exact shared-package "
            "wheel or run from a complete TheHub source checkout"
        )
    init_path = Path(spec.origin)
    if init_path.name != "__init__.py":
        raise SharedTransportBindingError(
            f"prii_export_utils has an unsupported package origin: {init_path}"
        )
    return init_path.parent


def authoritative_shared_package() -> Path:
    source_package = source_checkout_shared_package()
    if source_package is not None:
        # A complete checkout outranks any merely name-equivalent installed copy.
        return verify_shared_package_dir(source_package)
    return verify_shared_package_dir(installed_shared_package())


class _ExactSharedPackageFinder(importlib.abc.MetaPathFinder):
    """Resolve only the top-level package from the verified authoritative path."""

    def find_spec(self, fullname, path=None, target=None):  # noqa: ANN001
        if fullname != SHARED_PACKAGE_NAME:
            return None
        try:
            package_dir = authoritative_shared_package()
        except SharedTransportBindingError as exc:
            raise ImportError(str(exc)) from exc
        return importlib.util.spec_from_file_location(
            fullname,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )


def _remove_loaded_package() -> None:
    for name in list(sys.modules):
        if name == SHARED_PACKAGE_NAME or name.startswith(f"{SHARED_PACKAGE_NAME}."):
            sys.modules.pop(name, None)


def _loaded_package_dir() -> Optional[Path]:
    loaded = sys.modules.get(SHARED_PACKAGE_NAME)
    if loaded is None:
        return None
    loaded_file = getattr(loaded, "__file__", None)
    if loaded_file is None:
        return None
    return Path(loaded_file).resolve().parent


def install_import_guard() -> None:
    """Install the guard once and displace any non-authoritative loaded copy."""

    if sys.version_info < (3, 10):
        return
    if any(isinstance(finder, _ExactSharedPackageFinder) for finder in sys.meta_path):
        return

    loaded_dir = _loaded_package_dir()
    if loaded_dir is not None:
        try:
            authoritative_dir = authoritative_shared_package()
            loaded_verified = verify_shared_package_dir(loaded_dir)
        except SharedTransportBindingError:
            _remove_loaded_package()
        else:
            if loaded_verified != authoritative_dir:
                _remove_loaded_package()

    sys.meta_path.insert(0, _ExactSharedPackageFinder())
