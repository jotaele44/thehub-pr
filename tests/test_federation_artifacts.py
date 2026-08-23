from __future__ import annotations

from pathlib import Path

import pytest

from server.backend.federation_manager_artifacts import (
    ArtifactRegistrationError,
    ArtifactStore,
)

PASSED = [{"name": "exit_code", "status": "passed"}, {"name": "schema", "status": "passed"}]
FAILED = [{"name": "exit_code", "status": "passed"}, {"name": "schema", "status": "failed"}]


def test_failed_validation_cannot_register_or_move_active(tmp_path: Path) -> None:
    allowed = tmp_path / "repo"
    allowed.mkdir()
    first = allowed / "first.json"
    first.write_text('{"version":1}\n', encoding="utf-8")
    second = allowed / "second.json"
    second.write_text('{"version":2}\n', encoding="utf-8")

    store = ArtifactStore(tmp_path / "artifacts")
    good = store.register_validated(
        app_id="aguayluz",
        run_id="run-good",
        source=first,
        allowed_root=allowed,
        validators=PASSED,
    )
    store.activate("aguayluz", good.artifact_id)

    with pytest.raises(ArtifactRegistrationError, match="all-passed"):
        store.register_validated(
            app_id="aguayluz",
            run_id="run-bad",
            source=second,
            allowed_root=allowed,
            validators=FAILED,
        )

    assert store.current("aguayluz")["artifact_id"] == good.artifact_id


def test_activation_and_rollback_only_target_registered_objects(tmp_path: Path) -> None:
    allowed = tmp_path / "repo"
    allowed.mkdir()
    one = allowed / "one.txt"
    two = allowed / "two.txt"
    one.write_text("one\n", encoding="utf-8")
    two.write_text("two\n", encoding="utf-8")
    store = ArtifactStore(tmp_path / "artifacts")

    first = store.register_validated(
        app_id="ovnis", run_id="run-1", source=one, allowed_root=allowed, validators=PASSED
    )
    second = store.register_validated(
        app_id="ovnis", run_id="run-2", source=two, allowed_root=allowed, validators=PASSED
    )

    store.activate("ovnis", first.artifact_id)
    transition = store.activate("ovnis", second.artifact_id)
    assert transition["previous_artifact_id"] == first.artifact_id
    assert store.current("ovnis")["artifact_id"] == second.artifact_id

    store.rollback("ovnis", first.artifact_id)
    assert store.current("ovnis")["artifact_id"] == first.artifact_id

    with pytest.raises(ArtifactRegistrationError, match="does not exist"):
        store.activate("ovnis", "art_missing")
    assert store.current("ovnis")["artifact_id"] == first.artifact_id


def test_artifact_registration_rejects_paths_outside_allowed_root(tmp_path: Path) -> None:
    allowed = tmp_path / "repo"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("no\n", encoding="utf-8")
    store = ArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ArtifactRegistrationError, match="escapes its allowed root"):
        store.register_validated(
            app_id="skywatcher",
            run_id="run-outside",
            source=outside,
            allowed_root=allowed,
            validators=PASSED,
        )


def test_directory_identity_includes_member_paths_sizes_and_hashes(tmp_path: Path) -> None:
    allowed = tmp_path / "repo"
    package = allowed / "export"
    package.mkdir(parents=True)
    (package / "a.jsonl").write_text("a\n", encoding="utf-8")
    nested = package / "nested"
    nested.mkdir()
    (nested / "b.jsonl").write_text("b\n", encoding="utf-8")
    store = ArtifactStore(tmp_path / "artifacts")

    artifact = store.register_validated(
        app_id="spiderweb",
        run_id="run-dir",
        source=package,
        allowed_root=allowed,
        validators=PASSED,
    )

    assert artifact.kind == "directory"
    assert artifact.bytes == 4
    assert artifact.payload_path.is_dir()
