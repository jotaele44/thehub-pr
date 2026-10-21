# Federation Build Observatory — isolated V0.1

## Scope and status
This branch adds a read-only, lazy-loaded route at `/build-observatory`, local reviewed JSON snapshot loading, a component illumination grid, state filtering, an evidence inspector, and fail-closed status derivation. This is **not** a certified full architecture graph, and is not connected to live GitHub data. There are no inferred completion percentages.

### Snapshot V0.1 input contract
```json
{
  "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "components": [
    {
      "id": "example-ui",
      "name": "Example UI",
      "source_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "requirement_ids": ["REQ-001"],
      "gates": [
        {"id": "unit", "required": true, "state": "PASS", "evidence_id": "run-123", "evidence_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
      ],
      "blocker_ids": []
    }
  ],
  "edges": []
}
```

**Warning:** This format is a prototype UI contract. It checks formal evidence fields but cannot establish that an evidence ID corresponds to an authentic run. Do not treat local supplied data as trusted certification authority. Future certification must verify signed/pinned manifests and authoritative CI provenance server-side.

## Local verification (repository root)
```sh
cd server/frontend
npm ci
npm run lint
npm run typecheck
npm run test -- --run src/features/observatory/status.test.js
npm run build
```
Deployment and promotion remain blocked until exact-head tests pass, evidence provenance has been hardened, production data adapters are integrated, and browser/mobile gates pass.

## Next phases
1. Audit and freeze complete federation repo inventory. Existing registry membership is not proof of complete GitHub inventory.
2. Implement server-side trusted GitHub and CI ingestion, freeze source and manifest hashes, and preserve identity/contradiction records.
3. Render graph edges and dependency topology with repository-aware component grouping.
4. Integrate historical snapshots, exact-commit verification, role-appropriate access control, and performance limits.
5. Complete positive/negative browser tests, responsive and accessibility checks, deployment/rollback, and reusable skill promotion only after passing gates.

## Constraints
Maintain existing artifact-based producer boundary (see ARCHITECTURE.md). Do not assume folder existence, stub code or stale test records imply completion. Source-code and runtime verification are distinct.
