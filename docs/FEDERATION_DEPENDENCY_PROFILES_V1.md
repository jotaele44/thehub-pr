# Federation dependency profiles v1

## Status

- **Contract:** `repo_federation_manifest_v1`
- **Authority:** TheHub manifest schema plus each producer's root `federation.json`
- **Certification relation:** profile declaration is necessary but never sufficient
- **Current certification:** no producer is certified by this document

## Why the profile split exists

A single dependency list cannot accurately represent all of these materially
different environments:

1. application/runtime code;
2. tests, coverage, linting, and type checking;
3. desktop packaging;
4. optional data connectors;
5. optional heavy analytical subsystems;
6. disconnected release reconstruction.

Putting pytest or build tooling into a runtime manifest makes the release larger
and obscures actual runtime requirements. Removing it without changing the Hub
command contract can silently break `test_suite`. The v1 profile model therefore
separates identity and purpose while preserving the existing Hub execution path.

## Command contract

| Command | Meaning | Required | Network rule |
|---|---|---:|---|
| `setup` | Backward-compatible audit/development environment. It must install everything required by the declared Hub commands, including `test_suite`. | Yes | May acquire only version- or SHA-pinned dependencies. |
| `runtime_setup` | Smaller candidate certified-core runtime. It must exclude test-only and operator-only tooling. | No during migration; required before runtime certification | May acquire only version- or SHA-pinned dependencies. |
| `setup_test` | Optional test-only overlay for future profile-aware runners. | No | May acquire only version- or SHA-pinned dependencies. |
| `test_suite` | Offline-safe execution of the repository's tests after `setup` or a profile-aware runtime-plus-test setup. | Yes | No network. |
| Other commands | Validation, exports, reports, maintenance, and producer functions. | Repository-specific | No network unless the command is explicitly classified as a data-acquisition connector outside the certified core. |

The current `startup_completion_audit.py` continues to execute `setup` before
`test_suite`; this preserves compatibility. Freedom certification must separately
exercise `runtime_setup`, because a passing development environment does not prove
that the runtime profile is minimal or self-contained.

## Profile invariants

A repository adopting `runtime_setup` must establish, at minimum:

- the runtime manifest contains no test-only packages;
- every direct runtime dependency is present in the runtime lock;
- development/test profiles contain the complete runtime closure;
- no runtime import depends on a package available only in the development profile;
- desktop constraints do not silently reintroduce test or operator tooling;
- `setup` still prepares every command TheHub currently invokes;
- `runtime_setup` cannot reference the development/test manifest;
- all setup profiles reject sibling-repository filesystem coupling;
- remote Git or registry coordinates do not count as retained offline bytes;
- optional connectors and heavy subsystems are not silently promoted into core.

## Identity and evidence

Dependency profile names do not prove package identity. Certification records must
preserve:

- raw package name and source string;
- normalized package name;
- resolved version or immutable source revision;
- direct/transitive role;
- runtime/development/desktop/optional profile membership;
- package or archive byte size and SHA-256;
- license and redistribution status;
- platform and ABI binding for native artifacts;
- SBOM manifestation;
- exact repository commit and tree receiving the profile.

A Git commit pin proves source-revision selection, not byte retention. A lockfile
proves a resolution declaration, not that every wheel, npm tarball, browser,
extension, or system executable required for a disconnected rebuild is locally
available.

## Current implementations

### `ovnis-pr`

Draft PR `ovnis-pr#125` introduces:

- `requirements.lock` as the eight-package runtime closure;
- `requirements-dev.lock` as the preserved sixteen-package development closure;
- `setup` bound to the development lock;
- `runtime_setup` bound to the runtime lock;
- a fail-closed dependency-plane validator and negative regressions.

### `moneysweep-pr`

Draft PR `moneysweep-pr#563` introduces:

- byte-identical `requirements.in` and `requirements.txt` runtime manifests;
- a twenty-eight-package runtime lock after removing nine test-only records;
- `setup` bound to `requirements-dev.txt`;
- `runtime_setup` bound to `requirements.txt`;
- a fail-closed dependency-profile validator and negative regressions.

Both implementations remain `PROVISIONAL`. Hosted lock regeneration, runtime
import closure, retained dependency bytes, and disconnected execution are still
open.

## Certification gates

A profile may advance beyond `PROVISIONAL` only after all relevant gates pass:

1. clean-cache install;
2. exact lock regeneration with zero drift;
3. runtime import closure from the runtime profile alone;
4. startup and core operation with no secrets;
5. denied-network startup;
6. connector-only allowlist execution;
7. packaged-release egress capture;
8. native binary and postinstall capture;
9. offline core browse/analyze/report/export;
10. disconnected rebuild from retained dependency bytes;
11. SBOM, licenses, hashes, and package counts reconcile arithmetically.

No profile declaration, test count, workflow success, or deterministic resolver
output may substitute for these runtime and rebuild observations.
