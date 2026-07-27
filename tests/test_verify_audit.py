"""Tests for the audit-claim verifier. Standalone (no hub).

The verifier's job is to fail when a document and the code disagree, so the
tests that matter are the negative ones: a harness that has only ever been seen
to pass is indistinguishable from a harness that always passes. Each check
below builds a throwaway repository tree so the assertions do not depend on the
sibling repositories being present.
"""
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "scripts" / "verify_audit.py"

_spec = importlib.util.spec_from_file_location("verify_audit", TOOL)
verify_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_audit)


BACKEND = '''
from fastapi import Depends, FastAPI

app = FastAPI()


def _require_key() -> None:
    ...


@app.get("/assets")
def list_assets():
    ...


@app.patch("/assets/{asset_id}")
def patch_asset(
    asset_id: str,
    _: None = Depends(_require_key),
):
    ...


@app.post("/notify")
def notify(_: None = Depends(_require_key)):
    ...


@app.post("/ai/query")
async def ai_query(request):
    ...
'''


def _make_repo(tmp_path: Path, name: str, *, backend: str = BACKEND) -> Path:
    repo = tmp_path / name
    (repo / "server" / "backend").mkdir(parents=True)
    (repo / "server" / "backend" / "main.py").write_text(backend, encoding="utf-8")
    (repo / "docs").mkdir(parents=True)
    return repo


# --- derivers -------------------------------------------------------------


def test_route_count_ignores_non_route_decorators(tmp_path):
    repo = _make_repo(tmp_path, "aguayluz-pr")
    assert verify_audit.backend_route_count(repo, "server/backend/main.py") == 4


def test_guard_is_read_from_the_signature_not_the_decorator(tmp_path):
    """The auth dependency is a default argument, and signatures wrap.

    Parsing only the decorator line reports every route as unguarded; parsing
    only the first line of the signature misses `patch_asset`, whose
    `Depends(_require_key)` sits two lines below the `def`.
    """
    repo = _make_repo(tmp_path, "aguayluz-pr")
    assert verify_audit.guarded_mutating_routes(
        repo, "server/backend/main.py", "_require_key"
    ) == "2 of 3"


def test_unguarded_route_is_named_with_its_line(tmp_path):
    repo = _make_repo(tmp_path, "aguayluz-pr")
    open_routes = verify_audit.unguarded_mutating_routes(
        repo, "server/backend/main.py", "_require_key"
    )
    assert len(open_routes) == 1
    assert open_routes[0].startswith("POST /ai/query (:")


def test_get_routes_are_not_counted_as_mutating(tmp_path):
    repo = _make_repo(tmp_path, "aguayluz-pr")
    guarded, _, total = verify_audit.guarded_mutating_routes(
        repo, "server/backend/main.py", "_require_key"
    ).partition(" of ")
    assert total == "3", "GET /assets must not appear in the mutating-route denominator"
    assert guarded == "2"


def test_subcommand_count_matches_multiline_add_parser(tmp_path):
    """A single-line regex undercounts wrapped `add_parser(` calls."""
    repo = tmp_path / "thehub-pr"
    (repo / "src" / "hub").mkdir(parents=True)
    (repo / "src" / "hub" / "cli.py").write_text(
        'sub.add_parser("alpha")\n'
        "sub.add_parser(\n"
        '    "beta",\n'
        "    help='wrapped onto its own line',\n"
        ")\n",
        encoding="utf-8",
    )
    assert verify_audit.argparse_subcommand_count(repo, "src/hub/cli.py") == 2


def test_npm_script_and_ci_gate_detection(tmp_path):
    repo = tmp_path / "repo"
    (repo / "frontend").mkdir(parents=True)
    (repo / "frontend" / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build", "lint": "eslint ."}}), encoding="utf-8"
    )
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text(
        "jobs:\n  frontend:\n    steps:\n      - run: npm ci\n", encoding="utf-8"
    )
    assert verify_audit.has_npm_script(repo, "frontend/package.json", "lint") is True
    assert verify_audit.has_npm_script(repo, "frontend/package.json", "test") is False
    # Having the script is not the same as gating it — the distinction the
    # rollup originally collapsed.
    assert verify_audit.ci_runs(repo, "npm run lint") is False
    assert verify_audit.ci_runs(repo, "npm ci") is True


def test_missing_package_json_is_not_a_lint_script(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert verify_audit.has_npm_script(repo, "frontend/package.json", "lint") is False


# --- the runner's verdicts ------------------------------------------------


def _claim_doc(repo: Path, guarded_phrase: str, unguarded_route: str) -> None:
    (repo / "docs" / "MATURITY_AUDIT.md").write_text(
        f"bearer auth, and it is attached to **{guarded_phrase}**\n"
        f"mutating routes — see below.\n\n"
        f"`POST {unguarded_route}` (`:44`) is **not** guarded, and no client sends the header.\n",
        encoding="utf-8",
    )


def _run(tmp_path):
    return {r.label: r for r in verify_audit.run_checks(tmp_path, require_all=False)}


AGUAYLUZ_RATIO = "aguayluz: mutating routes carrying _require_key"
AGUAYLUZ_ROUTE = "aguayluz: the unguarded mutating route is /ai/query"


def test_accurate_document_passes(tmp_path):
    repo = _make_repo(tmp_path, "aguayluz-pr")
    _claim_doc(repo, "two of the three", "/ai/query")
    results = _run(tmp_path)
    assert results[AGUAYLUZ_RATIO].status == "PASS"
    assert results[AGUAYLUZ_ROUTE].status == "PASS"


def test_overstated_count_fails_and_names_both_sides(tmp_path):
    """The exact defect this gate was built for."""
    repo = _make_repo(tmp_path, "aguayluz-pr")
    _claim_doc(repo, "three of the three", "/ai/query")
    result = _run(tmp_path)[AGUAYLUZ_RATIO]
    assert result.status == "FAIL"
    assert "'three of the three'" in result.detail
    assert "'two of the three'" in result.detail


def test_wrong_route_named_fails(tmp_path):
    repo = _make_repo(tmp_path, "aguayluz-pr")
    _claim_doc(repo, "two of the three", "/notify")
    result = _run(tmp_path)[AGUAYLUZ_ROUTE]
    assert result.status == "FAIL"
    assert "/notify" in result.detail and "/ai/query" in result.detail


def test_dropping_the_claim_fails_rather_than_passing_vacuously(tmp_path):
    """Deleting a sentence must not be a way to make the gate green."""
    repo = _make_repo(tmp_path, "aguayluz-pr")
    (repo / "docs" / "MATURITY_AUDIT.md").write_text("Nothing to see here.\n", encoding="utf-8")
    result = _run(tmp_path)[AGUAYLUZ_RATIO]
    assert result.status == "FAIL"
    assert "no claim matching" in result.detail


def test_code_change_alone_turns_the_gate_red(tmp_path):
    """Guarding /ai/query without updating the doc is also drift."""
    repo = _make_repo(
        tmp_path, "aguayluz-pr",
        backend=BACKEND.replace(
            "async def ai_query(request):", "async def ai_query(request, _: None = Depends(_require_key)):"
        ),
    )
    _claim_doc(repo, "two of the three", "/ai/query")
    results = _run(tmp_path)
    assert results[AGUAYLUZ_RATIO].status == "FAIL"
    assert "'three of the three'" in results[AGUAYLUZ_RATIO].detail
    assert results[AGUAYLUZ_ROUTE].status == "FAIL"


def test_absent_repo_skips_by_default_and_fails_under_require_all(tmp_path):
    by_label = {r.label: r for r in verify_audit.run_checks(tmp_path, require_all=False)}
    assert by_label[AGUAYLUZ_RATIO].status == "SKIP"

    strict = {r.label: r for r in verify_audit.run_checks(tmp_path, require_all=True)}
    assert strict[AGUAYLUZ_RATIO].status == "FAIL"


def test_missing_document_is_a_failure_not_a_skip(tmp_path):
    _make_repo(tmp_path, "aguayluz-pr")  # tree present, document absent
    result = _run(tmp_path)[AGUAYLUZ_RATIO]
    assert result.status == "FAIL"
    assert "missing document" in result.detail


# --- the live federation --------------------------------------------------


def test_this_repo_passes_its_own_local_checks():
    """No check may FAIL against the real tree.

    Scope depends on the checkout: in CI only thehub is present, so the
    cross-repo checks SKIP and this asserts the thehub-local subset. From a
    working copy holding all seven repositories it asserts the full set — the
    same run, strictly stronger, with no configuration difference.
    """
    results = verify_audit.run_checks(REPO_ROOT.parent, require_all=False)
    failures = [r for r in results if r.status == "FAIL"]
    assert not failures, "\n".join(f"{r.label}: {r.detail}" for r in failures)
