# TheHub sole federation admin control plane

`THEHUB_ADMIN_BOUNDARY/1.0` makes TheHub the only federation-global
administrative plane. It does not make TheHub a runtime dependency for ordinary
repository work.

## Enforced planes

| Surface | Plane | Permitted authority |
|---|---|---|
| TheHub native workstation manager | Administrative control plane | All 68 signed operations, subject to existing enablement, approval, scope, rollback, secret and receipt rules |
| TheHub iOS | Read-only admin companion | Status, search, reports, certification status and alerts |
| Six producer applications | Bounded operational planes | Their own repository/domain scope only |

All manager operations are bound to `thehub_workstation`; no operation binding
permits `thehub_ios` or `repo_app`. The iOS source contains no workstation
audience, AdminKit, execution, deployment, migration, secret, certification
issuance, or Lockstep override capability.

## Availability invariant

When TheHub is unavailable, repository-local operations continue. Cross-repo
and federation-global mutations fail closed. Repository applications do not
link the control-plane implementation or receive its credential audience.

## Impact Lockstep

The contract is federation-visible. A boundary change impacts all seven nodes
and cannot merge, release, or certify until each affected node carries a valid
consumer manifestation and its negative isolation gate passes. Impact Lockstep
does not require synchronized commits or identical versions; it requires a
compatible federation state before promotion.

## Certification limit

Passing source and unit gates certifies the committed contract behavior only.
Final certification additionally requires green GitHub checks on every PR,
merge protection evidence, an actual macOS workstation build, an iOS simulator
build/test, deployment smoke, and audit/rollback evidence. Missing runtime
evidence remains `OPEN` or `BLOCKED`.
