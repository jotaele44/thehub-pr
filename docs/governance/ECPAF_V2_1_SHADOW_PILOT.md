# ECPAF-V2.1 shadow policy pilot

This additive internal governance pilot evaluates frozen checkpoint ledgers. It
does not implement an operator feature, activate Mucaro or Claude, or change any
production, merge, deployment, secret, protection, or canonical-data authority.
TheHub remains the cross-repository control plane and each producer retains its
domain authority. Seven canonical core repositories and adjacent Mucaro AI make
the explicitly declared eight-repository execution portfolio. Existing seven-node
governance contracts are preserved.

## Milestones and evidence

| Milestone | Threshold | Required additional condition |
| --- | ---: | --- |
| Build | 80% | Every applicable mandatory build checkpoint PASS |
| Integration | 90% | Every mandatory build and integration checkpoint PASS |
| Operational readiness | 95% | Every mandatory checkpoint through operations PASS |

Percentages use the cumulative frozen phase denominator and declared positive
integer weights. Unknown, skipped, provisional, blocked and never-emitted results
do not contribute PASS weight. The unrounded integer ratio decides thresholds.
All mandatory security, integrity, identity, provenance and authorization leaves
remain required. This pilot does not implement exclusions or NOT_APPLICABLE;
every declared checkpoint must have exactly one observation. Changing the
requirement population or policy requires a new contract hash and new evidence
bindings, with explicit reviewed scope reconciliation before future adoption.

`structurally_eligible` means only that declared evidence passes byte/hash and
ledger-consistency checks. It does not prove the truth, completeness, or
independence of the evidence producer. The result always withholds certification,
authorizes no protected operations, and records independent review OPEN.
Self-declared reviewer fields cannot authorize release.

## Execution and recovery

Every checkpoint declares one of AI_AUTO, AI_CONDITIONAL, HUMAN_REQUIRED,
EXTERNAL_BLOCKED, or INDEPENDENT_REVIEW independently of its evidence state.
Missing permissions block only the dependent action. Other safe work continues.
Epochs are bounded to two authority snapshots, three repairs per candidate, and
one identical no-delta retry. A source change requires a successor snapshot;
historical receipts remain intact. The evaluator is stateless and read-only,
so replaying the same frozen inputs has no repository side effects.

Use `scripts/ecpaf_v21.py --policy POLICY --contract CONTRACT --observations
OBSERVATIONS --evidence-root ROOT --expected-contract-sha256 FROZEN_DIGEST`.
Acquire FROZEN_DIGEST from the separate frozen execution baseline; do not
recompute it from an unreviewed incoming contract to bypass scope reconciliation.
Standard output is an audit result; exit zero
means structurally valid input, even when readiness leaves are OPEN. Exit two
means malformed, contradictory, stale, or missing evidence. Consumers must read
the result rather than converting exit zero to release permission.

The checkpoint contract pins exact heads for all eight repositories. PASS rows
must bind the contract's policy and authority tuple and reference a matching
SHA-256 file under the evidence root. Absolute paths, parent traversal, and
symlink evidence are prohibited. Only byte binding is asserted; original API
wire bytes are not claimed when the connector supplied decoded JSON/text.

## Qualification before adoption

1. Run positive, negative, boundary, dependency, drift, duplicate, and tamper
   regressions with `python -m unittest discover -s tests -p test_ecpaf_v21.py -v`.
2. Inspect the independently computed arithmetic oracle over 216 combinations,
   covering all three cumulative milestones (648 assertions of threshold logic).
3. Review the exact candidate in hosted full TheHub CI/security. Existing red
   federation gates remain red until their own governed fixes qualify.
4. Obtain a distinct policy-owner/security review. Same-agent oracle tests are
   automated cross-checks, not an independent human approval.
5. Reconcile producer compatibility and local receipts using
   `governance/federation_dependencies.yaml`,
   `governance/reconciliation_policy.json`, and
   `federation/lockstep-bindings.json`. Missing binding or current certification
   blocks promotion. Mucaro's adjacent adapter needs a separately reviewed
   contract; its execution is not inferred from repository access.
6. Only after all applicable gates and authorization pass, qualify merge and
   replay the exact merged head, followed by deployed-version proof if applicable.
   A separate reviewed change is required to alter protected release behavior.

Rollback of this candidate removes only the additive pilot files and its
internal capability declaration. No current certificate is superseded by the
pilot. Reusable workflow learning remains a candidate pending independent review.
