# ADR 0013 — Cross-repository landfill registry ownership proposal

- **Status:** Proposed — **NOT ACCEPTED**
- **Authority:** TheHub federation architecture; this document does not grant a new permission.
- **Related proposal:** `aguayluz-pr` PR #403 / ADR-0004, head `93725524a4f48a884eef1c34bc78b5e09d218263`.
- **Downstream implementation:** `aguayluz-pr` PR #404, head `cfaa83968a8bc28738f6bb5e81ded714d343b849`.
- **Non-binding precedent:** TheHub ADR 0009 is Proposed, not ratified.
- **Binding precedent:** TheHub ADR 0006 is Accepted, scoped to TheHub and Skywatcher, not automatically Spiderweb.

## Problem and decision boundary

AguaYLuz contains environmental exposure models and a `PR_SOLID_WASTE` source family, but the family remains `REGISTERED_NOT_EXHAUSTED`. Its proposed source-truth declaration would add `solid_waste_landfill_site_registry` without implementing a certified ingestion or export. TheHub currently has no accepted, landfill-specific cross-repository ownership decision. Spiderweb has provisional spatial observations and discovery pins, not independently certified landfill identities. No producer can ratify TheHub authority on its own.

The following **candidate partition is submitted for review only**:

- **AguaYLuz (candidate producer):** bounded solid-waste site registry, source-native IDs, permitted site geometry, regulatory status and lifecycle events, exposure relationships and source-quality flags. The authoritative agency and record identifier must be proven per entry. Name or geospatial proximity does not establish identity.
- **Spiderweb (spatial producer):** geospatial discovery and imagery observations only within its currently accepted repository boundary. Cross-repo imagery acquisition remains provisional and must not be represented as a final exemption from the accepted TheHub/Skywatcher imagery-control ADR.
- **MoneySweep:** contracts, recipients, funding, and vendor chains. Registry ownership does not transfer money or procurement facts to AguaYLuz.
- **TheHub:** the federation-wide coordination/validation and evidence-promotion gates already assigned by accepted policy. Persistent cross-producer identity-equality and lineage mechanisms described by ADR 0009 remain **proposed** until separately ratified; do not treat them as a deployed registry.

## Mandatory acceptance criteria before ratification

1. Named TheHub architecture owner explicitly decides the producer/site registry boundary, what constitutes certified geometry, and the status of Spiderweb's imagery seam. This draft is not approval.
2. Confirm authoritative primary registry publishers and record namespaces; retain contradictory agency attributions, unknown coverage, alternate geometries and temporal source versions. `PR_SOLID_WASTE` registration is not data-source exhaustion.
3. Freeze all source bytes, source schema/version, SHA-256, coordinate CRS, identity candidates, temporal bindings, and reproducible negative tests. Do not join by name-only or location-only.
4. Check current TheHub accepted control-plane policies, AguaYLuz's producer contracts, Spiderweb's boundary, and MoneySweep's finance ownership for duplicate controls.
5. Require independent repository-specific reviews where GitHub protection mandates them, exact-head security/CI/GUI parity, qualified merge, merged-head replay, consumer pin reconciliation and TheHub LOCKSTEP before release claims.
6. Reconcile #403 against current AguaYLuz `main` **after** authority disposition. Resolve #404's `.gitignore` conflict separately, without discarding original sources or merely rewriting tests.

## Explicit non-effects

This proposal does not approve #403 or #404, does not add a production `source_truth.owns` declaration, does not create a canonical landfill registry, does not change any schema or frozen manifest, does not grant imagery or secret access, does not authorize identity merges, and does not enable promotion, release, or deployment. Any missing approval, source or check remains `OPEN`/`BLOCKED`/`UNVERIFIED`; certification remains **WITHHELD**.
