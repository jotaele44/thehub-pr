# Apple imagery provider binding — TheHub

Status: **PROVISIONAL / CONTROL-PLANE ONLY**

TheHub registers Apple MapKit only as a noncanonical external-render provider. Spiderweb remains the bounded spatial runtime authority. TheHub may expose provider availability, provenance/rights state, renderer discovery, and handoff into Spiderweb views; it must not become geometry authority, imagery authority, a provider-pixel store, or an independent Apple Maps data plane.

The GIS workspace now includes an imagery provider provenance inspector backed by `server/frontend/src/gis/imageryProviderRegistry.js`. The inspector keeps `RENDER_MANIFESTATION` and `SOURCE_MANIFESTATION` records separate and surfaces authority, availability, temporal/resolution semantics, retention/download constraints, attribution, and provider endpoint/runtime identity.

Apple remains:

- `RENDER_MANIFESTATION`;
- `CURRENT` / `COMMERCIAL_RENDER`;
- authority `NONE`;
- provider pixels nonpersistent;
- tile harvesting/secondary database prohibited by federation contract;
- credentials deferred;
- live enablement blocked on Spiderweb renderer-neutral parity, live attribution/fallback tests, and final authorization.

Retainable historical imagery is represented independently through bound source manifestations such as Landsat, Sentinel-2, and the exact NOAA Digital Coast Puerto Rico/USVI NAIP STAC manifestation where applicable. Render providers never substitute for those retained sources.

No TheHub certification or Apple live enablement is implied by registry/inspector presence alone.
