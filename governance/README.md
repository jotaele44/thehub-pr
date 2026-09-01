# Federation Governance

This directory is the canonical governance control plane for the seven-repository PRII federation.

Certification requires all of the following:

1. Exactly seven canonical repositories are present in the frozen baseline.
2. Dependency edges are declared centrally; impact uses transitive closure, not direct edges only.
3. Governed contracts are fingerprinted and versioned with SemVer.
4. Structural changes are classified conservatively: removals/type changes/new required fields/enum narrowing require MAJOR; additive optional fields require MINOR; metadata-only changes may use PATCH.
5. Every impacted repository has an explicit compatibility disposition; `BLOCKED`, missing, or unknown fails.
6. Central and repo-local receipts must agree before a synchronized baseline can be certified.
7. Documentation membership must agree with canonical membership.
8. Frozen repository SHAs identify the exact baseline under certification.
9. GitHub Actions checks must pass. Required-status branch protection is a separate repository setting and must be verified independently.

A green script or workflow is necessary but not sufficient for `CERTIFIED`; required status rules and seven-repo receipt reconciliation must also be evidenced.
