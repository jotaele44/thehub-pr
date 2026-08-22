# Ontology Term Lifecycle Policy

The normative lifecycle is:

```text
observed → candidate → proposed → canonical → deprecated → retired
```

## Transition gates

| From | To | Required evidence |
|---|---|---|
| observed | candidate | Exact commit, repository, path, symbol/line, context hash, and evidence tier |
| candidate | proposed | Definition, semantic owner, scope, examples, non-examples, competency question, contradiction review |
| proposed | canonical | Required owner approvals, compatibility classification, tests, and generated-artifact verification |
| canonical | deprecated | Replacement or explicit no-replacement decision, migration window, affected-consumer inventory |
| deprecated | retired | No active producer or consumer dependency; historical resolver retained |

A term MUST NOT move directly from `observed` to `canonical`.

## Versioning

- PATCH: editorial clarification without semantic or validation change.
- MINOR: additive term, relation, optional property, mapping, or competency question.
- MAJOR: changed meaning, identity, authority, scale, unit, cardinality, required property, relationship direction, removal, merge, or split.

Every breaking change requires a machine-readable change record with `classification: breaking`, affected repositories, migration, and owner approval.
