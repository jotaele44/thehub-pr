# Federation Non-Destructive Executability Auditor

This subproject answers a narrow question: **is an exposed feature actually connected to an executable path?** It inventories GUI controls, handlers, commands, API routes, workflow stages, dependencies, terminal states, and side-effect boundaries without allowing production effects.

## Safety model

The default mode is fail-closed:

- source checkouts are read-only;
- the browser is restricted to an explicit origin allowlist;
- unmocked HTTP, WebSocket, download, shell, database, cloud, email, and message-delivery effects are blocked;
- writable paths are ephemeral;
- no production credentials are accepted;
- every conclusion carries evidence and confidence;
- static evidence never claims a real side effect completed.

## Commands

```bash
python -m pip install -e './federation-audit[dev]'
federation-audit validate-manifest federation-audit/manifests/federation.json
federation-audit inventory-graph --manifest federation-audit/manifests/federation.json --output federation-initial-static-graph.json
federation-audit scan --workspace-root .. --manifest federation-audit/manifests/federation.json --output audit-traces.json
federation-audit fixture-audit --output first-controlled-audit.json
pytest federation-audit/tests
```

The inventory graph is generated directly from the pinned manifest and performs no runtime execution. The workspace root must contain the seven repositories as exact siblings. The scanner is read-only and emits a graph plus a finding ledger. The Playwright harness is under `playwright/`; run it only inside the provided locked-down container or an equivalent disposable environment.

## Classification contract

| Classification | Deterministic meaning |
|---|---|
| `EXECUTABLE_CONFIRMED` | A terminal state was demonstrated in an isolated runtime. |
| `EXECUTABLE_BY_CONTRACT` | The full path reached an intercepted boundary with a matching declared contract. |
| `WIRED_BUT_BLOCKED` | Wiring exists, but an explicit precondition or dependency prevents completion. |
| `PARTIALLY_WIRED` | An interaction enters logic but no complete downstream and terminal path is established. |
| `UI_NO_OP` | An actionable GUI surface has no meaningful event binding or observable intent. |
| `TARGET_MISSING` | A referenced handler, service, route, command, or stage cannot be resolved. |
| `CONTRACT_MISMATCH` | Caller and target disagree on method, path, or declared payload contract. |
| `UNREACHABLE` | Implementation exists but no normal entry path reaches it. |
| `PLACEHOLDER` | The implementation is a stub, TODO, fixed demo response, or mock-only path. |
| `RUNTIME_FAILURE` | The path throws or rejects before its expected boundary or terminal state. |
| `PRECONDITION_UNDECLARED` | Completion depends on hidden configuration, state, or credentials. |
| `UNSAFE_TO_PROBE` | Isolation policy cannot contain the probable side effect. |
| `INDETERMINATE` | Available evidence is insufficient for a stronger classification. |

## Evidence policy

- **T1 Technical:** source locations, AST/DOM bindings, route registries, request traces, schemas.
- **T2 Operational:** reproducible isolated run, browser trace, container logs.
- **T3 Eyewitness:** maintainer/operator statement.
- **T4 Secondary:** documentation, issue, roadmap, or comment.

Only T1/T2 evidence may establish `EXECUTABLE_CONFIRMED` or `EXECUTABLE_BY_CONTRACT`.

## Current limitation

The committed first controlled audit is the deterministic six-case fixture. A live repository GUI run requires a local federation workspace and installed browser binaries. The inventory records unknown authentication and destructive boundaries explicitly rather than guessing them.

## Cost and dependency freedom

The `freedom-scan` command applies `FEDERATION_FREEDOM_CONTRACT_v1` to four independent axes:
`COST_FREE`, `SERVICE_INDEPENDENT`, `SELF_CONTAINED_RELEASE`, and
`OFFLINE_REPRODUCIBLE_BUILD`.

```bash
federation-audit freedom-scan \
  --workspace-root ../freedom-workspace \
  --snapshot federation-audit/manifests/freedom-snapshot.v1.json \
  --policy federation-audit/manifests/freedom-policy.v1.json \
  --output federation-audit/artifacts/freedom-static-audit.json
```

The scan preserves raw acquisition snapshots, emits whole-row findings, verifies exact commit/tree
identity when Git metadata is available, and closes its arithmetic. It deliberately returns
`certified: false`: static source and manifest evidence can establish blockers, but cannot establish
the absence of runtime egress, postinstall downloads, secret dependence, or clean-cache build
failure. Use `--require-no-static-blockers` only after the baseline blocker set has been remediated.
