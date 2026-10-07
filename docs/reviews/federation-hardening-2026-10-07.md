# Federation code review — 2026-10-07

Review base: `d765bb0bd02adee985bb38a9d8839f291a472a7a`.

Scope: repository API and data boundaries, federation metadata, existing regression tests, GUI capability gates, and shared infrastructure where applicable. This is a targeted review with automated validation, not a claim that every possible defect has been eliminated.

## Changes

- **P2:** Export hashing loaded entire artifacts into memory. Stream in 1 MiB chunks with byte-identical SHA-256 output.
- **P2:** The shipped ASG leaderboard consumer was absent from GUI capability bindings. Bind its endpoints and module to the existing MoneySweep leaderboard UI and consumer tests.

## Validation

Validation results are recorded in the pull request description. Regression cases include invalid inputs and preservation of normal behavior. GUI parity baselines were not regenerated.

The review uses isolated local checkouts and synthetic regression fixtures. Existing frozen-source receipts retain their original scope and date; they do not establish live source freshness. Shared-package consumer pins remain immutable until a separate release/pin update.
