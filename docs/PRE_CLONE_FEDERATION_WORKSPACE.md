# PRII pre-clone federation workspace contract

## Status

Implementation candidate. The exact seven-repository operator command is intentionally withheld until the macOS clean-workspace certification gate succeeds on the final coordinated heads.

## Canonical topology

A federation workspace is one neutral directory whose immediate children are exactly the Hub and the six registered producers:

```text
PRII_ROOT/
├── thehub-pr/
├── moneysweep-pr/
├── spiderweb-pr/
├── skywatcher-pr/
├── centinelas-pr/
├── aguayluz-pr/
└── ovnis-pr/
```

`PRII_ROOT` must not be inside another Git checkout. Repository children must not be symlinks or nested inside one another. `thehub-pr` is cloned or updated first because producer dependency declarations resolve the shared packages at sibling-relative paths.

## Runtime policy

- Local federation baseline: Python 3.11.
- Each repository owns its own `.venv`.
- A shared federation virtual environment is prohibited.
- Local bootstrap must never use `uv pip install --system`, system `pip`, or an active global environment.
- TheHub may retain broader package-runtime compatibility where its own tests support it; that does not change the local federation workspace baseline.
- A repository that cannot use Python 3.11 must carry `federation/python-policy-exception.json` with the selected interpreter and a non-empty technical reason.

## Shared-package contract

The following directories must exist under the Hub checkout before producer setup begins:

```text
thehub-pr/packages/prii_maintenance
thehub-pr/packages/prii_export_utils
```

The workspace validator fails closed when either directory is absent.

## Mode separation

The workspace controller exposes independent actions:

| Action | Effect | Readiness requirement |
|---|---|---|
| `clone` | Clone or fast-forward all seven repositories, Hub first | None; no exports run |
| `validate` | Validate topology, manifests, Python markers, shared packages, and private venv separation | All structural checks |
| `bootstrap-local` | Create and populate one `.venv` per repository | Structurally valid workspace; no system install |
| `export-test` | Run only the safe test export command declared by each producer | Valid workspace |
| `export-production` | Run only an explicit production export command | `production_status=PRODUCTION`, live-ready true, zero blockers |
| `run-live` | Run only an explicit live-execution command | Same production gate plus an explicit live command |

A producer's legacy `export_canonical` command is accepted as a test export. It is accepted as production only when it explicitly carries `--mode production`. The controller never rewrites `--mode test` into production.

## Fail-closed behavior

The controller blocks rather than guesses when:

- the workspace is nested inside a Git checkout;
- an expected destination exists but is not a Git checkout;
- a repository is missing or is not an immediate sibling;
- a producer lacks `federation.json`;
- the Python marker is absent or inconsistent without a recorded exception;
- a shared Hub package is absent;
- multiple repository `.venv` paths resolve to the same directory;
- a manifest command is missing, unsafe, or uses shell metacharacters;
- a production/live readiness field is absent, false, or blocked;
- a production or live command is not explicit.

## Source-checkout entrypoint

The controller can be executed from an uninstalled TheHub checkout through `scripts/prii_workspace.py`. Installing TheHub also exposes the `prii-workspace` console script.

The exact root path and final clone/bootstrap command block are certification outputs, not assumptions. They will be published only after `scripts/certify_preclone_workspace_macos.py` succeeds against the final coordinated heads.

## Coordinated dependency order

1. Adjudicate TheHub PR #134 before any dependent native desktop adapter is promoted.
2. Reconcile Spiderweb PR #236 against current `main` without force push.
3. Adjudicate Skywatcher PR #153 after or with Spiderweb #236.
4. Prohibit restoration of direct, manual repository-to-repository file-copy handoffs.
5. Exchange Skywatcher-to-Spiderweb data only through a versioned, hash-bearing package validated by TheHub.

## Preservation

This contract does not authorize merge, production promotion, live source acquisition, direct writes to `main`, force pushes, shared virtual environments, or system Python mutation.
