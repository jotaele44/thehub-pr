# ADR 0018 — MoneySweep financial-intelligence domain boundaries proposal

- **Status:** Proposed — **NOT ACCEPTED**
- **Date:** 2026-11-26
- **Authority:** TheHub federation architecture; this document does not grant a new permission.
- **Related candidate:** `moneysweep-pr` PR #730, head `41edf3c`, a draft that is not adopted.
- **Non-binding precedent:** [ADR 0009](0009-persistent-federation-identity-authority.md) and [ADR 0013](0013-landfill-registry-ownership-proposal.md) are Proposed, not ratified.

## Problem and decision boundary

`moneysweep-pr` PR #730 proposes widening MoneySweep from public-money source lanes to a 25-domain financial and economic intelligence model. One of those domains, Strategic Infrastructure, records who owns, finances and operates physical assets. The candidate states that MoneySweep must consume certified asset identities and geometries from the repository that owns them and must not keep an asset registry of its own.

That rule needs an owner for each asset class, and the federation has not decided one for most of them. No producer can ratify TheHub authority on its own, so the candidate marks every class as unratified and submits the partition below **for review only**.

## Candidate partition

The candidate owner is the producer whose registered role in `registry/producers.yaml` is closest to the asset class. It is a starting point for the decision, not evidence that the producer holds a certified registry for that class today.

| Asset class | Candidate identity owner | State |
|---|---|---|
| Power plants | `aguayluz-pr` | Candidate, unratified |
| Transmission and distribution | `aguayluz-pr` | Candidate, unratified |
| Reservoirs and water systems | `aguayluz-pr` | Candidate, unratified |
| Airports | `spiderweb-pr` | Candidate, unratified. It publishes airport reference locations; a certified airport identity registry is not established. |
| Waste management | `aguayluz-pr` | Candidate, unratified. Depends on ADR 0013, which is itself Proposed. |
| Ports and terminals | none | Unassigned |
| Roads and tollways | none | Unassigned. MoneySweep holds road-corridor join inputs but does not own road identity. |
| Submarine cables | none | Unassigned |
| Telecommunications towers | none | Unassigned |
| Fuel terminals | none | Unassigned |
| Industrial parks | none | Unassigned |
| Data centers | none | Unassigned |
| Hospitals | none | Unassigned |
| Agricultural land | none | Unassigned |

For every class, the proposed split of facts is the same:

- **Identity owner:** the asset's stable identifier, certified geometry, lifecycle and source-native bindings.
- **MoneySweep:** owners, operators, concessionaires, financiers, contracts, incentives and money flows that refer to the asset by the owner's identifier. It registers no asset and no geometry.
- **TheHub:** cross-producer identity equivalence and its lineage, as far as accepted policy already assigns it. The persistent identity authority in ADR 0009 remains proposed.

## What this would require

1. **New dependency edges.** `governance/federation_dependencies.yaml` declares no edge from an asset-owning producer into `moneysweep-pr`, and its policy fails undeclared cross-repository dependencies. Each ratified class needs a declared edge and a named contract before MoneySweep consumes anything.
2. **A consumable identity contract per class.** MoneySweep can bind only to a stable identifier that the owner publishes and certifies. Name or proximity is not a binding.
3. **A decision for the nine unassigned classes.** Until one is made, MoneySweep can hold financial relationships for those assets only against source-native identifiers and cannot claim a federated asset identity.

## Mandatory acceptance criteria before ratification

1. A named TheHub architecture owner decides the owner of each class, or decides that a class stays unassigned. This draft is not approval.
2. Each candidate owner confirms, in its own repository, that it can publish certified identities for the class. A producer role is not a registry.
3. The dependency edges and contracts in the section above are declared and pass the existing governance gates.
4. The decision is checked against accepted policy for duplicate controls, including the imagery boundary in [ADR 0006](0006-skywatcher-ai-imagery-centralization.md) and the status of ADR 0009 and ADR 0013.
5. Exact-head CI, qualified merge, merged-head replay, consumer pin reconciliation and TheHub LOCKSTEP precede any release claim.

## Explicit non-effects

This proposal does not approve `moneysweep-pr` PR #730, does not assign ownership of any asset class, does not add a `source_truth` declaration or a dependency edge, does not change `registry/producers.yaml`, any schema or any frozen manifest, does not authorize identity merges, and does not enable promotion, release or deployment. Every item above remains `OPEN`; certification remains **WITHHELD**.
