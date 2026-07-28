"""Secrets broker (no readback) and file-token broker (no browser paths).

Covers gates G07 (native secrets -- the platform-independent half; macOS
Keychain certification needs macOS and is recorded as blocked), G10 (file
pickers, brokered tokens, preflight, SHA-256, managed staging) and G18 (no
secret disclosure).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.backend.federation_manager import SecretProvider, UnavailableSecretProvider  # noqa: E402
from server.backend.federation_manager_files import (  # noqa: E402
    FILE_SET_FAMILIES,
    FileTokenBroker,
    FileTokenError,
    PreflightError,
    diff_paths,
    discard_run_intake,
    intake_inventory,
    observed_paths,
    preflight,
    safe_component,
    sha256_file,
    sniff_signature,
    stage_operation_inputs,
    unexpected_writes,
)
from server.backend.federation_manager_secrets import (  # noqa: E402
    InMemorySecretProvider,
    MacOSKeychainProvider,
    SecretAccessError,
    SecretBroker,
    SecretServiceProvider,
    WindowsCredentialManagerProvider,
    env_names_for,
    provider_description,
    select_provider,
)

CANARY = "prii-canary-secret-4b71ce9d02af"


# ── Secrets: the no-readback invariant ──────────────────────────────────────


def test_the_foundation_interface_still_has_no_getter():
    """The property PR #94 pinned must survive this vector."""
    for provider in (
        UnavailableSecretProvider(),
        InMemorySecretProvider(),
        MacOSKeychainProvider(),
        SecretServiceProvider(),
        WindowsCredentialManagerProvider(),
    ):
        for forbidden in ("get", "read", "resolve", "reveal", "value"):
            assert not hasattr(provider, forbidden), f"{type(provider).__name__}.{forbidden}"


def test_broker_exposes_no_value_returning_method():
    broker = SecretBroker(InMemorySecretProvider())
    public = [name for name in dir(broker) if not name.startswith("_")]
    assert "get" not in public
    assert set(public) >= {"set", "exists", "validate", "delete", "presence", "inject_into_env"}


def test_inject_into_env_returns_none_and_writes_into_the_sink():
    provider = InMemorySecretProvider()
    provider.set("centinelas", "ANTHROPIC_API_KEY", CANARY)
    broker = SecretBroker(provider)

    env: dict[str, str] = {}
    result = broker.inject_into_env("centinelas", ["ANTHROPIC_API_KEY"], env)

    assert result is None, "a sink must not return the value it moved"
    assert env["ANTHROPIC_API_KEY"] == CANARY


def test_presence_reporting_never_includes_the_value():
    provider = InMemorySecretProvider()
    provider.set("centinelas", "ANTHROPIC_API_KEY", CANARY)
    broker = SecretBroker(provider)

    report = broker.presence("centinelas", ["ANTHROPIC_API_KEY", "MISSING_KEY"])
    serialised = json.dumps(report)
    assert CANARY not in serialised
    assert report[0]["status"] == "present"
    assert report[1]["status"] == "absent"


def test_validate_does_not_leak_length_or_shape():
    provider = InMemorySecretProvider()
    provider.set("aguayluz", "EPA_WATERS_API_KEY", CANARY)
    broker = SecretBroker(provider)
    result = broker.validate("aguayluz", "EPA_WATERS_API_KEY")
    serialised = json.dumps(result)
    assert CANARY not in serialised
    assert str(len(CANARY)) not in serialised


def test_missing_reports_only_names():
    provider = InMemorySecretProvider()
    provider.set("moneysweep", "FEC_API_KEY", CANARY)
    broker = SecretBroker(provider)
    missing = broker.missing("moneysweep", ["FEC_API_KEY", "SAM_API_KEY", "FRED_API_KEY"])
    assert missing == ["SAM_API_KEY", "FRED_API_KEY"]
    assert CANARY not in json.dumps(missing)


def test_unavailable_provider_fails_loudly_rather_than_silently_unsetting():
    broker = SecretBroker(UnavailableSecretProvider())
    env: dict[str, str] = {}
    with pytest.raises(SecretAccessError, match="cannot supply secret values"):
        broker.inject_into_env("centinelas", ["ANTHROPIC_API_KEY"], env)
    assert env == {}


def test_empty_secret_is_refused():
    broker = SecretBroker(InMemorySecretProvider())
    with pytest.raises(SecretAccessError, match="empty secret"):
        broker.set("thehub", "PRII_WRITE_TOKEN", "")


def test_delete_is_idempotent():
    broker = SecretBroker(InMemorySecretProvider())
    broker.set("thehub", "PRII_WRITE_TOKEN", CANARY)
    broker.delete("thehub", "PRII_WRITE_TOKEN")
    broker.delete("thehub", "PRII_WRITE_TOKEN")
    assert broker.exists("thehub", "PRII_WRITE_TOKEN") is False


def test_redaction_handle_drops_values_on_exit():
    provider = InMemorySecretProvider()
    provider.set("centinelas", "ANTHROPIC_API_KEY", CANARY)
    broker = SecretBroker(provider)

    with broker.collect_redaction_values("centinelas", ["ANTHROPIC_API_KEY"]) as handle:
        assert CANARY in handle.values()
    assert handle.values() == []


def test_redaction_handle_clears_even_when_the_body_raises():
    provider = InMemorySecretProvider()
    provider.set("centinelas", "ANTHROPIC_API_KEY", CANARY)
    broker = SecretBroker(provider)

    handle = broker.collect_redaction_values("centinelas", ["ANTHROPIC_API_KEY"])
    with pytest.raises(RuntimeError):
        with handle:
            raise RuntimeError("operation blew up")
    assert handle.values() == []


def test_redaction_handle_tolerates_a_missing_secret():
    broker = SecretBroker(InMemorySecretProvider())
    with broker.collect_redaction_values("centinelas", ["ABSENT_KEY"]) as handle:
        assert handle.values() == []


def test_provider_description_states_readback_is_unavailable():
    description = provider_description(InMemorySecretProvider())
    assert description["readback"] is False
    assert description["persistent"] is False, "in-memory must not claim to persist"
    assert provider_description(UnavailableSecretProvider())["available"] is False


def test_select_provider_maps_platforms():
    assert isinstance(select_provider("darwin"), MacOSKeychainProvider)
    assert isinstance(select_provider("linux"), SecretServiceProvider)
    assert isinstance(select_provider("freebsd"), UnavailableSecretProvider)


def test_macos_adapter_never_puts_a_secret_in_argv(monkeypatch):
    """A value in argv is visible to any local `ps`; it must go via stdin."""
    captured: dict[str, object] = {}

    def fake_run(argv, input_text=None):
        captured["argv"] = list(argv)
        captured["input"] = input_text

        class _Result:
            returncode = 0
            stdout = ""

        return _Result()

    monkeypatch.setattr("server.backend.federation_manager_secrets._run", fake_run)
    MacOSKeychainProvider().set("thehub", "PRII_WRITE_TOKEN", CANARY)

    assert CANARY not in " ".join(captured["argv"])
    assert captured["input"] == CANARY


def test_linux_adapter_never_puts_a_secret_in_argv(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(argv, input_text=None):
        captured["argv"] = list(argv)
        captured["input"] = input_text

        class _Result:
            returncode = 0
            stdout = ""

        return _Result()

    monkeypatch.setattr("server.backend.federation_manager_secrets._run", fake_run)
    SecretServiceProvider().set("centinelas", "ANTHROPIC_API_KEY", CANARY)

    assert CANARY not in " ".join(captured["argv"])
    assert captured["input"] == CANARY


def test_keychain_distinguishes_not_found_from_locked(monkeypatch):
    """A locked keychain must not be reported as 'secret is absent'."""

    def make_run(code):
        def fake_run(argv, input_text=None):
            class _Result:
                returncode = code
                stdout = ""

            return _Result()

        return fake_run

    monkeypatch.setattr("server.backend.federation_manager_secrets._run", make_run(44))
    assert MacOSKeychainProvider().exists("thehub", "X") is False

    monkeypatch.setattr("server.backend.federation_manager_secrets._run", make_run(51))
    with pytest.raises(SecretAccessError, match="unavailable or access was denied"):
        MacOSKeychainProvider().exists("thehub", "X")


def test_env_names_for_is_names_only():
    assert env_names_for(["B_KEY", "A_KEY", "A_KEY"]) == ["A_KEY", "B_KEY"]


def test_secret_provider_abc_cannot_be_instantiated():
    with pytest.raises(TypeError):
        SecretProvider()  # type: ignore[abstract]


# ── File tokens ─────────────────────────────────────────────────────────────


@pytest.fixture
def broker(tmp_path):
    return FileTokenBroker(tmp_path / "intake")


@pytest.fixture
def picked(tmp_path):
    path = tmp_path / "operator" / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema_version": "x", "records": []}), encoding="utf-8")
    return path


def test_token_is_opaque_and_reveals_no_path(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    assert "manifest" not in token
    assert str(picked) not in token
    assert "/" not in token and "\\" not in token
    assert len(token) >= 32


def test_token_is_bound_to_its_session(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    with pytest.raises(FileTokenError, match="does not belong to this session"):
        broker.resolve(token, session_token="s2", app_id="thehub")


def test_token_is_bound_to_its_application(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    with pytest.raises(FileTokenError, match="different application"):
        broker.resolve(token, session_token="s1", app_id="ovnis")


def test_token_expires(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked, now=1000.0)
    broker.resolve(token, session_token="s1", app_id="thehub", now=1000.0)
    with pytest.raises(FileTokenError, match="expired"):
        broker.resolve(token, session_token="s1", app_id="thehub", now=1000.0 + 100000)


def test_unknown_token_is_rejected(broker):
    with pytest.raises(FileTokenError, match="unknown file token"):
        broker.resolve("not-a-real-token", session_token="s1", app_id="thehub")


def test_revoked_token_stops_working(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    broker.revoke(token)
    with pytest.raises(FileTokenError, match="unknown file token"):
        broker.resolve(token, session_token="s1", app_id="thehub")


def test_purge_expired_removes_only_expired(broker, picked):
    live = broker.mint(session_token="s1", app_id="thehub", source_path=picked, now=time.time())
    stale = broker.mint(session_token="s1", app_id="thehub", source_path=picked, now=1000.0)
    assert broker.purge_expired() == 1
    broker.resolve(live, session_token="s1", app_id="thehub")
    with pytest.raises(FileTokenError):
        broker.resolve(stale, session_token="s1", app_id="thehub")


def test_a_directory_cannot_be_minted(broker, tmp_path):
    with pytest.raises(FileTokenError, match="not a readable file"):
        broker.mint(session_token="s1", app_id="thehub", source_path=tmp_path)


def test_staging_copies_rather_than_references(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    staged = broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")

    assert staged.path != picked
    assert staged.path.exists()
    assert staged.sha256 == sha256_file(picked)

    # Replacing the original after staging must not change what runs.
    picked.write_text('{"tampered": true}', encoding="utf-8")
    assert sha256_file(staged.path) == staged.sha256


def test_staged_path_is_under_the_managed_intake_root(broker, picked, tmp_path):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    staged = broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")
    assert str(staged.path).startswith(str((tmp_path / "intake").resolve()))


def test_receipt_artifact_omits_the_operator_path(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    staged = broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")
    artifact = staged.receipt_artifact()
    serialised = json.dumps(artifact)
    assert str(picked) not in serialised
    assert "operator" not in serialised
    assert artifact["logical_name"] == "manifest.json"
    assert len(artifact["sha256"]) == 64


def test_hostile_filename_is_reduced_to_a_safe_leaf():
    assert safe_component("../../etc/passwd") == "passwd"
    # Anything before the last separator is discarded, so a name that embedded a
    # path keeps only its final component.
    assert safe_component("a; rm -rf /.json") == "json"
    assert safe_component("nested/dir/file.json") == "file.json"
    assert safe_component("") == "file"


def test_metacharacters_in_a_leaf_name_are_replaced():
    assert safe_component("a; rm -rf *.json") == "a_rm_-rf_.json"
    assert safe_component("$(id).json") == "id_.json"
    assert safe_component("x`whoami`.csv") == "x_whoami_.csv"
    for hostile in ("..", "...", "$(id)", "a;b|c&d"):
        cleaned = safe_component(hostile)
        assert "/" not in cleaned and "\\" not in cleaned
        assert cleaned not in ("", ".", "..")


def test_safe_component_is_length_bounded():
    assert len(safe_component("a" * 500 + ".json")) <= 120


def test_symlinked_selection_is_resolved_at_mint(broker, tmp_path, picked):
    link = tmp_path / "operator" / "link.json"
    link.symlink_to(picked)
    token = broker.mint(session_token="s1", app_id="thehub", source_path=link)
    record = broker.resolve(token, session_token="s1", app_id="thehub")
    assert record.source_path == picked.resolve()


# ── Preflight ───────────────────────────────────────────────────────────────


def test_preflight_records_digest_size_and_checks(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    staged = broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")
    findings = preflight(staged, extensions=[".json"])
    names = {check["name"] for check in findings["checks"]}
    assert {"non_empty", "size_limit", "extension"} <= names
    assert all(check["status"] == "passed" for check in findings["checks"])
    assert findings["sha256"] == staged.sha256


def test_preflight_rejects_an_empty_file(broker, tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    token = broker.mint(session_token="s1", app_id="thehub", source_path=empty)
    staged = broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")
    with pytest.raises(PreflightError, match="empty"):
        preflight(staged)


def test_preflight_rejects_a_wrong_extension(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    staged = broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")
    with pytest.raises(PreflightError, match="must end with"):
        preflight(staged, extensions=[".csv"])


def test_preflight_validates_against_a_schema(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    staged = broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")
    schema = {"type": "object", "required": ["schema_version"]}
    findings = preflight(staged, schema=schema)
    assert {"name": "schema", "status": "passed", "detail": ""} in findings["checks"]

    with pytest.raises(PreflightError, match="failed schema validation"):
        preflight(staged, schema={"type": "object", "required": ["absent_field"]})


def test_preflight_rejects_malformed_json(broker, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    token = broker.mint(session_token="s1", app_id="thehub", source_path=bad)
    staged = broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")
    with pytest.raises(PreflightError, match="not valid JSON"):
        preflight(staged, schema={"type": "object"})


def test_signature_extension_mismatch_is_reported_not_fatal(broker, tmp_path):
    """A PNG named .jpg is surfaced to the operator, not silently accepted."""
    disguised = tmp_path / "photo.jpg"
    disguised.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    token = broker.mint(session_token="s1", app_id="thehub", source_path=disguised)
    staged = broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")
    findings = preflight(staged)
    mismatch = [c for c in findings["checks"] if c["name"] == "signature_matches_extension"]
    assert mismatch and mismatch[0]["status"] == "failed"
    assert "image/png" in mismatch[0]["detail"]


def test_sniff_signature_identifies_known_types(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.7\n%...")
    assert sniff_signature(pdf) == "application/pdf"
    plain = tmp_path / "x.json"
    plain.write_text("{}", encoding="utf-8")
    assert sniff_signature(plain) is None


def test_shapefile_set_requires_its_sidecars(broker, tmp_path):
    base = tmp_path / "counties"
    base.mkdir()
    (base / "counties.shp").write_bytes(b"\x00" * 128)
    token = broker.mint(
        session_token="s1", app_id="aguayluz", source_path=base / "counties.shp", family="shapefile"
    )
    staged = broker.stage(token, session_token="s1", app_id="aguayluz", run_id="r1")
    with pytest.raises(PreflightError, match="missing required sidecars"):
        preflight(staged, family="shapefile")


def test_shapefile_set_passes_when_complete(broker, tmp_path):
    base = tmp_path / "counties"
    base.mkdir()
    for suffix in (".shp", ".shx", ".dbf", ".prj"):
        (base / f"counties{suffix}").write_bytes(b"\x00" * 128)
    token = broker.mint(
        session_token="s1", app_id="aguayluz", source_path=base / "counties.shp", family="shapefile"
    )
    staged = broker.stage(token, session_token="s1", app_id="aguayluz", run_id="r1")
    findings = preflight(staged, family="shapefile")
    sidecar = [c for c in findings["checks"] if c["name"] == "sidecar_completeness"]
    assert sidecar and sidecar[0]["status"] == "passed"
    assert set(FILE_SET_FAMILIES["shapefile"]["required"]) <= set(staged.sidecars)


def test_stage_operation_inputs_returns_paths_artifacts_and_preflights(broker, picked):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    paths, artifacts, preflights = stage_operation_inputs(
        broker,
        session_token="s1",
        app_id="thehub",
        run_id="r1",
        token_parameters={"path": token},
        specs={"path": {"extensions": [".json"]}},
    )
    assert set(paths) == {"path"}
    assert artifacts[0]["logical_name"] == "manifest.json"
    assert preflights[0]["sha256"] == artifacts[0]["sha256"]


def test_discard_run_intake_is_safe_when_absent(tmp_path):
    discard_run_intake(tmp_path / "intake", "never-created")


def test_discard_run_intake_removes_staged_files(broker, picked, tmp_path):
    token = broker.mint(session_token="s1", app_id="thehub", source_path=picked)
    broker.stage(token, session_token="s1", app_id="thehub", run_id="r1")
    assert intake_inventory(tmp_path / "intake", "r1")
    discard_run_intake(tmp_path / "intake", "r1")
    assert intake_inventory(tmp_path / "intake", "r1") == []


# ── Write-scope audit ───────────────────────────────────────────────────────


def test_write_audit_detects_writes_outside_the_declared_scope(tmp_path):
    root = tmp_path / "app"
    (root / "exports").mkdir(parents=True)
    (root / "exports" / "ok.json").write_text("{}", encoding="utf-8")
    before = observed_paths(root)

    (root / "exports" / "new.json").write_text("{}", encoding="utf-8")
    (root / "somewhere-else.txt").write_text("oops", encoding="utf-8")
    after = observed_paths(root)

    diff = diff_paths(before, after)
    assert "exports/new.json" in diff["created"]
    assert unexpected_writes(diff, ["exports"]) == ["somewhere-else.txt"]


def test_write_audit_flags_modification_of_an_existing_file(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    target = root / "data.json"
    target.write_text("{}", encoding="utf-8")
    before = observed_paths(root)
    target.write_text('{"changed": true}', encoding="utf-8")
    diff = diff_paths(before, observed_paths(root))
    assert diff["modified"] == ["data.json"]
    assert unexpected_writes(diff, ["exports"]) == ["data.json"]


def test_write_audit_with_no_declared_scope_treats_every_change_as_unexpected(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    before = observed_paths(root)
    (root / "x").write_text("y", encoding="utf-8")
    assert unexpected_writes(diff_paths(before, observed_paths(root)), []) == ["x"]
