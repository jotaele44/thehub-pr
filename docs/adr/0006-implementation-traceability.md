# ADR 0006 implementation traceability

This document maps ADR 0006 decisions to the atomic publication and implementation sequence. It is planning metadata only.

| Decision or invariant | Contract or artifact | Initial PR | Retirement gate |
|---|---|---|---|
| Authoritative ADR lives in TheHub | ADR 0006 + Skywatcher pointer | A01 / S01 | ADR and pointer agree |
| Query-triggered acquisition cannot answer before certification | `AcquisitionReceipt`, `SourceArtifact`, snapshot state | H01, later H04 | Pre-certification answer/citation denial |
| Skywatcher worker is isolated and artifact-only | `bounded_producer_job.v1` | H01, later H06 | No DB, secret readback or outbound network |
| External model egress is policy-controlled | classification + egress decision references | H01, later H05 | Restricted classes fail closed |
| Model fields retain complete provenance | `model_field_provenance.v1` | H01 / S02 | Zero missing provenance fields |
| SATIM imagery output is provisional | `satim_provisional_signal.v1` | H01 / later S03 | No direct evidentiary conclusion |
| Legacy local state is fully dispositioned | `legacy_artifact_disposition.v1` | H01 / later R01 | 100% object and record-set accounting |
| No premature retirement | parity matrix and retirement checklist | later D01–R04 | Two dual runs, rollback, GUI and zero old consumers |
| No producer RPC | signed job artifact and producer package | H01 / S02 | Static and runtime boundary tests |
| Retained aviation capability is preserved | aviation extraction and package schemas | S02 | Capability matrix has no regression |

## Publication sequence

1. **A01:** authoritative accepted ADR 0006 and ADR 0005 reservation.
2. **S01:** Skywatcher pointer and terminology correction.
3. **H01:** additive TheHub AI/imagery contract namespace and tests.
4. **S02:** Skywatcher aviation extraction and producer-package contracts and tests.

Runtime migration, direct-provider removal and retirement remain outside these PRs.
