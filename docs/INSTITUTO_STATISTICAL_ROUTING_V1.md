# Instituto de Estadisticas de Puerto Rico -> PRII Federation Routing v1

Status: **PROVISIONAL / ARCHITECTURE PASS / ACQUISITION PARTIAL**

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
11. CKAN package/resource identity is source-manifestation identity, not automatically canonical product identity.
12. Search ordering or first-match resolution is discovery only and must not be the sole identity proof.

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

## Live portal discovery

Public web discovery confirms that `datos.estadisticas.pr` exposes a CKAN Data API. Observed API actions include:

- `package_search`
- `datastore_search`
- `datastore_search_sql`

Multiple UUID-style resource IDs are publicly exposed through CKAN API-info pages. These prove a machine-readable datastore surface exists, but they do **not** prove the complete package/product denominator or a one-to-one relationship between catalog products and resources.

Current state:

- CKAN platform: **FACT**
- datastore query surface: **FACT**
- resource UUIDs exist: **FACT**
- complete package denominator: **UNKNOWN / OPEN**
- package -> resource revision/version graph: **UNKNOWN / OPEN**
- product-page -> CKAN-package binding for all visible products: **UNKNOWN / OPEN**

## Existing federation crosswalk

### MoneySweep

`moneysweep-pr/scripts/download_estadisticas_pr.py` already implements a CKAN adapter against `https://datos.estadisticas.pr` using `package_search`, `datastore_search`, CSV fallback, pagination and three configured source queries:

- `pr_general_fund_revenues`
- `pr_income_tax_collections`
- `estadisticas_pr_external_trade`

This is an **EXISTING_ADAPTER_REUSE_CANDIDATE**, not a second adapter to duplicate.

Hardening required before it can satisfy the federation certification contract:

- preserve the full package candidate set;
- do not treat the first fetchable `package_search` result as canonical identity;
- freeze package ID + resource ID;
- freeze raw bytes/SHA256 before normalization;
- record raw schema + raw row count;
- fail closed on ambiguous top candidates;
- preserve RAW fields separately from canonical projection.

### AguaYLuz

`aguayluz-pr/research/resource_balance/pilots/patillas_guayama_v0_5/public_source_receipts.json` already records an AAA raw-water extraction/production source through the Instituto portal. That receipt is retained as **EXISTING_SOURCE_REFERENCE** and must not be mistaken for successful machine-readable acquisition.

No existing Instituto-specific adapter was identified in the bounded code search of the other connected federation repos during this pass.

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
- CKAN portal family identified
- existing MoneySweep CKAN adapter discovered and marked for reuse rather than duplication
- existing AguaYLuz Instituto source receipt discovered and preserved as contextual provenance

## Open acquisition gates

The following remain OPEN before any claim of complete product coverage or live feed certification:

1. Enumerate the complete CKAN package denominator with proven pagination/count closure.
2. Bind product/search-surface records to CKAN packages/resources without NAME_ONLY identity.
3. Freeze stable package and resource IDs where available.
4. Acquire raw downloadable artifacts once per manifestation.
5. Record retrieval UTC, raw bytes/SHA256, schema and row count.
6. Build package/resource revision and supersession graph.
7. Execute row/count/schema/time/geography conservation gates on acquired artifacts.
8. Crosswalk live products against pre-existing repo datasets to suppress duplication.
9. Harden/reuse the MoneySweep CKAN adapter rather than introducing a duplicate resolver.
10. Promote only bounded, zero-residue subsets from PROVISIONAL to PASS/CERTIFIED.

Until these gates close, `.federation/statistical-routing-manifest.json` is a routing/discovery contract, not proof of complete Instituto ingestion.
