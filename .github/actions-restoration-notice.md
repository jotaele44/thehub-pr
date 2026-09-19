# GitHub Actions Restoration Notice

**Date:** 2026-09-19  
**Status:** RESTORED

## Summary

GitHub Actions runners were unavailable from approximately 2026-09-06 through
2026-09-19. Workflows triggered during that window completed as `failure`
immediately with `runner_id: 0`, `steps: []`, and no usable logs.

## Affected window

Commits merged while Actions was unavailable used local verification in place
of CI. These commits now need to be re-verified against live runners.

## Required re-runs

The following workflow classes should be re-run on the current `main` head
now that runners are assigned:

- Hub CI / core test suite
- HAF Contract Gate
- Federation Governance / federation-governance-certify
- Federation Completion Gate
- CodeQL Python analysis
- Admin Control Plane
- GIS live source certification

## Exit criteria

Close this notice once at least one representative workflow on the current
`main` head allocates a real runner (`runner_id != 0`), executes its steps,
and publishes usable logs.

## Related issues

- #255 Federation CI runner plane blocked before step execution
- #283 Actions startup blocker on HTR validator follow-up PR #282
