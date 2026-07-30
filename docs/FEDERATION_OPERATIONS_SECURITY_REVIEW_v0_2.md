# Security Review — Federation UI-Only Operations v0.2

Scope: the operations plane added on top of the PR #94 read-only foundation.
Certified surface is TheHub's 13 declared operations (12 enabled, `hub.fetch`
declared and disabled). The 55 producer operations are declared, classified,
and not enabled.

## Threat model

The manager is a privileged local orchestrator: it decides what executable runs
with what arguments, holds credentials, and writes the evidence that gates
consume. The primary threats are command injection, malicious or compromised
release metadata, path traversal, secret disclosure, unintended data mutation,
supply-chain substitution, local cross-site request abuse, stale-policy
downgrade, and rollback failure.

## Controls

| Threat | Control | Where |
|---|---|---|
| Command injection | No string is ever parsed into a command. argv is assembled from policy literals and validated parameters, then handed to `Popen` with `shell=False` | `federation_manager_operations.build_argv`, `federation_manager_process.run_process` |
| Manifest execution | The release catalog stays declarative and recursively rejects command-bearing keys at any depth; executable intent lives in a separate signed artifact | `federation_manager.validate_release_manifest` |
| Artifact substitution | Ed25519 signature over a canonical encoding, pinned key id, payload digest, schema | `verify_policy` |
| Policy downgrade | Monotonic sequence plus an issuer-published floor; the verifier takes the higher of the two | `verify_policy` |
| Path traversal | Every component resolved, absolute paths and `..` rejected, containment required in a managed root | `resolve_within`, `_require_contained` |
| Symlink escape | `Path.resolve()` on the full path before the containment check, so a link partway along cannot smuggle the result out | `resolve_within` |
| Secret exfiltration | No readback anywhere: the only value-moving method is a sink returning `None`; streaming redaction; deny-by-default environment | `SecretBroker.inject_into_env`, `Redactor` |
| Browser CSRF / local attack | Loopback only, exact origin allow-list, expiring opaque bearer | `federation_manager_api._authorize` |
| Log leakage | Redaction applied as lines stream, not after; the log hash covers the redacted bytes | `run_process` |
| Unbounded process | Timeout, process group kill, cancellation, byte-capped logs | `run_process` |
| Unexpected writes | Pre/post inventory diff against the run's own resolved output paths; a run that writes outside them is quarantined | `_declared_write_scopes` |
| Partial data commit | Staging, validation, atomic promotion, rollback receipt | `federation_manager_transactions` |
| False readiness | Only verified signed receipts satisfy a gate; annotations are ignored; the schema rejects a passed gate with no evidence | `evaluate_gates`, `gate_evidence.schema.json` |
| Destructive mistake | No deletion operation exists and no delete endpoint beyond removing a credential the operator stored | — |
| ToS violation | `aguayluz.fetch_luma_live` is policy-disabled with its own reason | `config/operations_policy.json` |

## Decisions worth stating plainly

**`python -m` is permitted here and forbidden in `src/hub/fetch.py`.** That is
not an inconsistency. `fetch.py` parses producer command *strings*, so it must
assume the string is hostile and rejects `-m` alongside `-c`/`-e`. This module
parses nothing: the module name is a fixed value inside a signed policy and can
never come from a request. The two guards protect different pipelines and are
deliberately not shared. Collapsing them would either weaken `fetch.py` or
forbid a safe execution form the handoff explicitly permits.

**The sealed sink instead of a getter.** The foundation's `SecretProvider` has
no `get`, and its own test asserts that structurally. Adding one would have been
the obvious way to feed a child process, and it would have put a secret value
into a caller's local variable one step away from a log line or a receipt.
`inject_into_env(app_id, secret_ids, env)` writes into the child's environment
and returns `None`, so no expression in the manager evaluates to a secret.

**Secrets travel by environment, not argv.** argv is visible to any local user
running `ps`. The same reasoning drove the macOS and Linux credential adapters
to write through stdin rather than as a command-line parameter. The Windows
adapter cannot currently do this and that exposure is recorded as F021 rather
than papered over.

**Log stream tickets rather than a bearer in the URL.** `EventSource` cannot set
an `Authorization` header. Putting the session token in a query string would
have worked and would have leaked a credential that authorises every other
endpoint into access logs and browser history. A single-use, short-TTL ticket
bound to one run is a capability to read one log and nothing else.

**Receipts are signed with a different key from the policy.** The policy says
what *may* run and is issued upstream; a receipt says what *did* run and is
attested locally. One key for both would let anyone able to issue a policy also
forge evidence that it had been executed.

**A run that exits zero can still fail.** If the post-run inventory shows a
write outside the operation's declared outputs, the run is marked `quarantined`
regardless of exit code. During certification this control fired incorrectly
because it compared paths against the catalog's prose write scope; the fix
(F027) derives the scope from the run's own resolved output parameters.

## Residual risks that must remain visible

- **First-party producer code is trusted code.** Path and process controls
  reduce accidents; they are not a hostile-code sandbox. An enabled operation
  can do anything its own code does inside its managed roots.
- **The manager receipt key is ephemeral** (F022). Receipts do not survive a
  manager restart as gate evidence. The failure direction is safe — old
  receipts stop counting rather than being trusted — but a deployment that
  needs durable evidence must persist a key.
- **macOS Keychain integration is implemented but uncertified** (F029). It has
  not been tested against locked-keychain or denied-access states on a real
  macOS host, because no such host exists in this environment.
- **Windows credential writes expose the value in argv** (F021).
- **Sessions and file tokens are in-memory and single-process** (F024).
- **A readable secret provider still exists elsewhere in the repository**
  (F025), predating this vector.
- **MiLUMA access remains policy-disabled** pending ToS adjudication.
- **Three rollback strategies are unbuilt**, so G13 is deferred rather than
  passed even though six strategies are certified.

## What this review does not cover

The 55 producer operations, because none is enabled and none can run. Their
entry-point hardening, rollback strategies, and adapters are enumerated in
`docs/FEDERATION_UI_OPERATIONS_HANDOFF_NEXT.md`.
