# Instituto de Estadisticas de Puerto Rico -> PRII Federation Routing v1

Status: **PROVISIONAL / ARCHITECTURE PASS / ACQUISITION OPEN**

## Scope

This vector freezes the user-supplied 19-page Instituto de Estadisticas search/catalog PDF as the source snapshot for taxonomy and visible source-entity discovery. It does **not** claim the PDF is the complete machine-readable product denominator.

The canonical routing authority for this vector is:

- `.federation/statistical-routing-manifest.json`

The validation gate is:

- `scripts/validate_statistical_routing.py`

## Standing rules

1. Acquire once; consume many.
2. TheHub owns the federation product/source registry and provenance graph.
3. Domain repos own interpretation inside their bounded domains.
4. Category is routing metadata, not exclusive ownership.
5. RAW, NORMALIZED and CANONICAL strings remain separate.
6. A source-provided alias/equality string is a candidate binding, never identity proof by itself.
7. Preserve methodological discontinuities and superseded manifestations.
8. OVNIS consumes only case-relevant context.
9. Spiderweb consumes source/entity identity and relationships, not indiscriminate copies of numeric tables.
10. Ingestion is not certification.

## Repo ownership

| Repo | Primary statistical role |
|---|---|
| thehub-pr | catalog/provenance; shared geography/demography/context |
| moneysweep-pr | economy, finance, labor |
| aguayluz-pr | agriculture, environment, energy, utility/infrastructure context |
| centinelas-pr | violence/justice, public safety, emergency, telecom context |
| skywatcher-pr | transportation and mobility |
| ovnis-pr | contextual case feeds only |
| spiderweb-pr | source-entity identity and relationships |

## Current bounded evidence

The frozen PDF visibly exposes the following category labels: Agricultura; Ambiente y Energia; Demografia y Poblacion; Economia y Finanzas; Educacion; Geografia; Proteccion Social; Salud; Tecnologia y Telecomunicaciones; Trabajo; Transportacion; Turismo y Cultura; Violencia y Justicia; Vivienda y Construccion.

It also visibly exposes Puerto Rico government, federal, municipality, international-organization, university/NGO and other source-entity groupings. These are discovery surfaces and candidate entity aliases; they are not by themselves a canonical identity authority.

## Visible sample products routed in v1

- Asegurados y Elegibles por Region y Municipios -> TheHub primary.
- Registro de vehiculos de motor por municipios y por categorias -> Skywatcher primary; methodology break preserved.
- Produccion y ventas de cemento -> MoneySweep primary; AguaYLuz contextual consumer.
- Accidentes fatales -> Centinelas primary; Skywatcher secondary.
- Delitos Tipo I -> Centinelas primary; misconduct/causation inference prohibited.
- Incidentes reportados por el Cuerpo de Bomberos de Puerto Rico (2022-2025) -> Centinelas primary; AguaYLuz contextual consumer.

## Gates completed in this vector

- repository roles frozen
- N:N routing semantics frozen
- category routing matrix created
- raw-vs-canonical identity boundary frozen
- visible methodology discontinuity represented
- consumer contracts created for all currently connected federation repos
- deterministic manifest validator added

## Open acquisition gates

The following remain OPEN before any claim of complete product coverage or live feed certification:

1. Resolve the live Instituto endpoint(s) behind the search surface.
2. Determine pagination/result-count semantics and enumerate the complete product denominator.
3. Freeze stable product IDs where available.
4. Acquire raw downloadable artifacts once per manifestation.
5. Record retrieval UTC, raw bytes/SHA256, schema and row count.
6. Build revision/supersession graph.
7. Execute row/count/schema/time/geography conservation gates on acquired artifacts.
8. Crosswalk live products against pre-existing repo datasets to suppress duplication.
9. Promote only bounded, zero-residue subsets from PROVISIONAL to PASS/CERTIFIED.

Until these gates close, `.federation/statistical-routing-manifest.json` is a routing contract and discovery manifest, not proof of complete Instituto ingestion.
