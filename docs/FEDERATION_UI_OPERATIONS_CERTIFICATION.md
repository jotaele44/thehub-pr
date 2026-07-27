# End-to-End Certification — Federation UI-Only Operations v0.2

**This is not a completion claim for the full vector.** Eleven of twenty-three
gates pass, eight are deferred with stated reasons, and four are blocked because
the evidence cannot be produced in this environment at all. What follows is what
was actually built and actually verified.

## Scope

Certified: TheHub's 13 declared operations — twelve enabled and executed,
`hub.fetch` declared and deliberately disabled.

Not certified: the 55 producer operations. They are declared and classified in
the signed policy so accounting is complete, but none is enabled and none can
run. Only `thehub-pr` was modified.

## Baseline

| Item | Pinned | Observed |
|---|---|---|
| PR #94 state | open, draft, unmerged | open, draft, `merged: false`, `mergeable_state: clean` |
| PR #94 head | `817fb97ddc3617a843ea5b05ff3a4080e60ade79` | matches |
| TheHub `main` | `58a159ffef69768b093ca19db3f1feb3ceaf8adb` | **drifted** to `e668cad` — adjudicated below |
| PR #94 base | — | `3c195606f22cbbc462ffa881975f608d61499631` (older than main, confirming F017) |
| Operation count | 68 = 13 Hub + 55 producer | 68, zero unclassified |

PR #94 was not force-pushed, amended, closed, or merged. The successor branch
was cut from `main` and PR #94's additive diff replayed by hand, then rebased as
`main` advanced.

### `main` drift, adjudicated

G01 requires the pinned SHAs to match *or the drift to be adjudicated*; this is
the adjudication. `main` moved from `58a159f` to `e668cad` while this work was in
progress, adding a coverage gate (`fail_under = 88`), `pre-commit`, an
`ErrorBoundary`, and design-system v0.3.1, which deleted
`server/frontend/src/styles/federation.css` in favour of the shared package.

The drift does not invalidate the operations policy. `src/hub/cli.py` — the sole
source of every enabled operation's argv — is **byte-identical** across
`58a159f`, `e668cad`, and this branch, so each policy row's
`source: thehub-pr/src/hub/cli.py@58a159ff` still names the exact content it was
derived from. This branch modifies no file under `src/hub`.

Re-verified against the rebased tree: 742 Python tests pass, coverage 90.94%
against the new 88% floor, `uv lock --check` clean, frontend lint/build clean,
41 frontend unit tests and all 12 visual baselines pass unmodified.

## Operation accounting

```
total                 68
enabled               12
declared_not_enabled  56
unclassified           0
by_app  aguayluz 12 · centinelas 11 · moneysweep 13 · ovnis 7
        skywatcher 6 · spiderweb 6 · thehub 13
```

Every deferred operation carries a stated reason. The schema requires
`enablement_reason` on any `DECLARED_NOT_ENABLED` row and forbids
`composite_unresolved` on any enabled one, so a shell composite cannot be
enabled by editing a single field.

## What was executed

Five operations run against the real installed `hub` console script, producing a
verified receipt chain (`reports/federation/receipts/`, chain problems: none):

| Operation | Status | Exit | Parameter types exercised |
|---|---|---|---|
| `hub.list` | succeeded | 0 | fixed |
| `hub.validate_manifest` | succeeded | 0 | file token, staged and preflighted |
| `hub.graph_report` | succeeded | 0 | directory, fixed boolean |
| `hub.ingest` | succeeded | 0 | directory, managed SQLite path |
| `hub.analytics_v2` | succeeded | 0 | directory, managed file |

Both the `exit_code` and `write_scope` validators passed on all five.

## Gate disposition

Machine-derived: `reports/federation/gate_evidence.json`, produced by
`tools/evaluate_federation_gates.py` from verified receipts only.

**Passed (11):** G04 accounting, G05 policy signature, G06 typed parameters,
G08 prerequisites, G10 file pickers, G11 streamed logs, G12 receipts, G14 gate
binding, G19 no command injection, G21 synthetic end-to-end, plus G18 no secret
disclosure.

**Deferred (8), each with a reason in the evidence file:**

- **G01, G02, G23** — verified by inspection; no operation observes git state,
  so no receipt can attest to them.
- **G03** — enforced statically. `tests/test_federation_process.py` walks the
  parsed AST of every `federation_manager*.py` module and fails on any non-False
  `shell=` keyword or banned call. The claim is about code that must never run,
  which no execution can demonstrate.
- **G09** — `hub.fetch` is disabled; nothing acquires a repository.
- **G13** — six rollback strategies are certified by forced-failure tests at
  every boundary; three declared by producer operations are unbuilt. Partial
  coverage is not a pass.
- **G17** — producer exports are out of scope.
- **G20** — certified by absence; no deletion operation exists.

**Blocked, not certified (4):** G07 macOS Keychain, G15 seven-of-seven UI setup,
G16 seven-of-seven UI validation, G22 real macOS operator run. This vector was
built in a headless Linux container with no macOS host, no window server, no
native file picker, and no Keychain. These gates are not "not yet done" — the
evidence they require cannot be produced here at all.

## Test results

| Suite | Result |
|---|---|
| Python, full | 665 passed |
| — operations policy and argv | 58 |
| — process supervision | 26 |
| — secrets and file brokers | 51 |
| — transactions and rollback | 41 |
| — receipts and gates | 26 |
| — operations API | 48 |
| — headless end-to-end | 9 |
| ruff (`src/hub tests server/backend tools`) | clean |
| mypy (`src/hub`) | clean |
| Frontend vitest | 37 passed |
| Frontend lint, production build | clean |
| Playwright visual | 12 passed |

Baseline before this work was 389 Python and 20 frontend tests.

## Defects found during this work

Nine, all in the failure ledger. The ones that changed the design:

- **F027** — the write-scope audit compared filesystem paths against the
  catalog's *prose* write scope, so `hub.ingest` was quarantined despite exiting
  zero. Scope is now derived from the run's own resolved output parameters.
- **F020 is refuted as written.** The ovnis scripts do not mutate ledgers in
  place; both write new CSVs via `--output`. The real defect is cwd-relative
  defaults, restated as F026 and fixed centrally.
- A pre-execution refusal was returning HTTP 200 with a receipt for a run that
  never started — a misleading entry in the evidence chain.
- `integrity_check` raised on a file that is not a database rather than
  reporting it unsound.
- A `<label for>` on the file-slot button replaced its accessible name.

## Stop conditions

None was converted into a silent skip. Three are live and recorded: the ToS-gated
MiLUMA acquisition stays policy-disabled (F013); three rollback strategies are
unbuilt and raise rather than no-op (F010); macOS certification is impossible
here (F029).

No merge, release mutation, tag, deletion, or write to any repository other than
`thehub-pr` occurred.
