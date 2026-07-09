# MCP Project Capability Matrix

This matrix declares, per project, the role it plays in the federation and
the core MCP capabilities it is expected to use. It is the human-readable
counterpart to `mcp/registry/capability_registry.yaml` (the machine-readable
capability registry) and `mcp/manifests/*.mcp.yaml` (each project's declared
manifest).

| Project | Role | Core Capabilities |
|---|---|---|
| TheHub | Federation control plane | registry, provenance, governance, schemas, source-ledger, entity-ledger, version-pins |
| Skywatcher | Air/SATIM/RLSM | flight, ADS-B, weather, satellite, geospatial, terrain, provenance |
| Ovnis | Case archive | source-registry, citations, documents, archive-search, deduplication, provenance |
| Spiderweb | Infrastructure/GIS | geospatial, parcels, routing, USGS, EPA, FEMA, Federal Register, Regulations.gov |
| Centinelas | Field operations | GPS, maps, weather, offline-cache, observation-intake, TheHub sync |
| MoneySweep | Contracts/finance | SAM.gov, USAspending, FPDS, SEC, entity-resolution, procurement-alerts |
| AguaYLuz | Water/energy/utilities | PRASA, PREPA/LUMA, EPA, USGS, NOAA, FEMA, hydrology, terrain, weather |

## Mapping to the capability registry

Not every capability named above is a top-level registry capability —
several are external data sources reached *through* a registry capability,
and are tracked individually as scored candidates in
`mcp/registry/external_mcp_candidates.csv` (e.g. `SAM.gov Contracts MCP`
under `contracts`, `Federal Register MCP` / `Federal Regulations MCP` under
`regulations`, `Terrain Elevation MCP` under `terrain`). The registry
capability each project manifest actually declares is:

| Project | Registry capabilities (beyond the inherited `federation-core` / `github-bridge` / `provenance`) | Project-local capabilities |
|---|---|---|
| Skywatcher | geospatial, terrain, flight, weather | satellite |
| Ovnis | documents | source-registry, citations, archive-search, deduplication |
| Spiderweb | geospatial, regulations | parcels, routing |
| Centinelas | weather, field-ops | offline-cache |
| MoneySweep | contracts | entity-resolution |
| AguaYLuz | terrain, weather, utilities | (none) |

TheHub itself does not carry a `mcp/manifests/` file — it is the control
plane that defines and validates the registry, not a declarative client of
it.
