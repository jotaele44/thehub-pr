# macOS operator certification — runbook

Four gates cannot be certified in a headless Linux container, and this is how
they get closed. G07 needs a real Keychain, G15 and G16 need a window server and
the native file picker, and G22 needs a person driving the App Center. The
evidence does not exist anywhere else, which is why they were recorded
`blocked_not_certified` with a stated cause rather than skipped.

You run one script on the Mac. It emits four signed attestations; you send them
back with the public half of your key, and the gates move on evidence.

## What the script will and will not accept

**Your answers are not the evidence.** Where you must act — pick a file through
the native picker, click through the App Center — the script checks the
machine-observable consequence instead of recording what you said. A native pick
produces a receipt carrying a file token and a content hash; a validation run
produces a receipt whose operation id and status the script reads back. If the
consequence does not appear, the step is refuted no matter what you answered.

That is deliberate. A certification script that trusts its operator is a rubber
stamp, and a rubber stamp is worth less than an honest `blocked`.

**A failure is recorded, not hidden.** A step that does not hold writes
`result: refuted`, which makes its gate `failed` — a stronger and more useful
signal than the `not_run` you would get if the script simply refused to write
anything. Do not re-run to get a clean sheet; send the refuted artifact and we
fix the underlying problem.

## Before you start

1. **A Mac.** The script refuses to run anywhere else, and the attestation
   records its platform, so a Linux-produced document would be self-evidently
   not macOS evidence.
2. **A signing key that is not the published fixture seed.** The script refuses
   that seed explicitly. An operator certification's entire value is that a
   person really ran it on real hardware, so an artifact anyone could mint
   proves nothing.

   ```
   mkdir -p ~/.prii
   python3 -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; \
   from cryptography.hazmat.primitives import serialization; \
   open('$HOME/.prii/manager.pem','wb').write(Ed25519PrivateKey.generate().private_bytes( \
   encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, \
   encryption_algorithm=serialization.NoEncryption()))"
   chmod 600 ~/.prii/manager.pem
   ```

   Keep the private key on the Mac. Only its public half comes back.

3. **A bootstrap nonce, which you choose.** Nothing prints one — no code in this
   repository generates a nonce. `server/backend/federation_manager_api.py` reads
   `PRII_MANAGER_BOOTSTRAP_NONCE` from the environment at **import** time and
   hashes it; the script presents the same value to exchange it for a session. So
   it is a shared secret between two processes, and it must be exported *before*
   uvicorn starts, in the shell uvicorn runs in. If the manager starts without
   it, `POST /session` answers `503 native bootstrap is not configured`.

4. **The manager running**, with the App Center reachable in a browser. The script
   drives the same loopback HTTP surface the UI uses, because G15 and G16 are
   claims about what the UI can do and the UI has nothing else.

## Blocked: there is no host to run

**This certification cannot currently be completed, and the steps below will not
work as written until that changes.** Recorded here rather than left for the next
operator to discover at the fourth prompt.

`federation_manager_api.runtime` is `None` at import and **nothing in the
repository ever assigns it** — the only assignment is
`tests/test_federation_operations_api.py:110`, via `monkeypatch`. Fifteen
endpoints call `_require_runtime()`, including `/receipts`, `/gates`,
`/secrets/presence` and every `/operations/*`, and each returns
`503 operations runtime is not configured; start the manager through the native
host`.

`ManagerRuntime`'s own docstring says it is "assembled by the native host". That
host does not exist in this repository: `desktop/` never references
`PRII_MANAGER_*` and never constructs a runtime. `uvicorn server.backend.main:app`
mounts the router but leaves `runtime` unset, so it serves a manager whose entire
operations surface is 503.

Confirmed by a real run, not predicted. All four attestations came back with the
same single line:

```json
{"error": "<HTTPError 503: 'Service Unavailable'>"}
```

| Gate | Result | Cause |
|---|---|---|
| G07 | `refuted` | `secret_presence` 503s |
| G15 | `refuted` | `len(manager.receipts())` runs ahead of `ask()`, so it refutes *before* printing its prompt |
| G16 | `refuted` | prompts first, then 503s reading receipts back |
| G22 | `refuted` | cannot complete a run at all |

One cause, four refutations. This is not four independent macOS problems.

**A second defect is visible in those artifacts.** The step wrapper does
`outcome = {"satisfied": False, "observations": {"error": repr(exc)}}`, which
*replaces* every observation gathered before the exception. The operator was
separately prompted by `security add-generic-password -w` — the Keychain adapter
reads `/dev/tty`, not stdin, so a piped secret never arrives — but that is
invisible in the attestation because the handler discarded it. A refuted
attestation should carry what it learned up to the failure; right now it carries
only the failure.

Closing this needs a host that assembles `OperationRunner` (verified policy,
`ExecutionContext` roots, `ReceiptStore` plus signer, `FileTokenBroker`,
`SecretBroker`) and provisions the browser session the App Center expects. That is
production wiring the operations vector deliberately scoped out, not a
documentation fix.

## Running it, once a host exists

Two terminals. Copy the nonce from the first into the second.

**Terminal 1 — the manager:**

```
export PRII_MANAGER_BOOTSTRAP_NONCE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "$PRII_MANAGER_BOOTSTRAP_NONCE"          # copy this
export PRII_MANAGER_RECEIPT_SIGNING_KEY="$HOME/.prii/manager.pem"
python3 -m uvicorn server.backend.main:app --port 8000
```

**Terminal 2 — the certification:**

```
export PRII_MANAGER_RECEIPT_SIGNING_KEY="$HOME/.prii/manager.pem"
export PRII_MANAGER_BOOTSTRAP_NONCE='paste-the-value-from-terminal-1'
python3 scripts/certify_macos_operator.py
```

The defaults now point at `http://127.0.0.1:8000/api/federation-manager`, so the
flags are only needed if you serve the app somewhere else. **The router prefix is
not optional**: the manager API is mounted on the main app at
`/api/federation-manager`, and a bare host answers `405` on `POST /session`
because the SPA catch-all matches that path for `GET`.

Quote the nonce in Terminal 2. Keep each command on one line — a blank line
between backslash continuations ends the command, and the remaining flags then
run as their own commands.

It works through four steps, pausing where you need to act.

| Gate | Attestation | You do | It checks |
|---|---|---|---|
| G07 | `operator.macos_keychain` | nothing — automated | A real Keychain write/read/delete round trip, then hunts the canary value through the presence response, the gates payload and every receipt |
| G15 | `operator.macos_ui_setup` | Prerequisites, then attach a manifest with the **native picker** and run `hub.validate_manifest` | A succeeded receipt exists, records a file input by hash, and contains no path from your home directory |
| G16 | `operator.macos_ui_validation` | Run `hub.validate_package` and `hub.validate_federation`, then reload the page | Both receipts exist and survive the reload |
| G22 | `operator.macos_end_to_end` | Run `hub.list → aggregate → correlate → ingest → analytics_v2`, then force a rollback with a deliberately invalid `hub.ingest` | Every step produced a succeeded receipt, and the failed run recorded `rollback.performed` |

Run a subset with `--only operator.macos_keychain` (repeatable) if a step needs
retrying.

The G07 canary check is the one worth understanding: it writes a distinctive
value into the real Keychain and then looks for that exact string in everything
the manager will hand out. Finding it anywhere is unambiguous, and it is the
only way to test the no-readback property against a real credential store rather
than a stub.

## Sending the result back

Two things:

- `reports/federation/attestations/operator.*.attestation.json` (four files)
- `reports/federation/operator_public_key.pem`

Never the private key. The evaluator verifies the signature before any gate
moves, and an attestation signed by an untrusted key contributes nothing — it is
not "evidence we could not check", it is not evidence.

Folding them in:

```
python3 tools/evaluate_federation_gates.py \
    --receipts reports/federation/receipts \
    --public-key reports/federation/receipt_public_key.pem \
    --attestations reports/federation/attestations \
    --attestation-public-key reports/federation/attestation_public_key.pem \
    --attestation-public-key reports/federation/operator_public_key.pem \
    --policy-sha256 "$(tr -d '[:space:]' < reports/federation/policy_sha256.txt)"
```

Two `--attestation-public-key` flags because there are genuinely two signers: the
static checks are signed by whatever ran the test suite, the operator
certification by your Mac. An attestation counts if any trusted key signed it.

## What this does not certify

The Hub slice only. G15 and G16 are restated at Hub scope in the `hub_slice`
profile — TheHub completes setup and validation through the UI, not seven of
seven apps. The full 7-of-7 claim and the 6-of-6 producer exports stay in the
`federation_vector` profile, which is evaluated and published alongside and
remains openly incomplete.

Running this does not make the vector complete. It makes the slice honest.
