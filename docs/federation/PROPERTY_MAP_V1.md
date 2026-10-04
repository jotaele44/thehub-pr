# Property Map v1 (candidate)

TheHub's Property Map is the `property-map` view of the GIS workspace, opened at
`/gis?view=property-map`. It places the records the Hub store holds on a map, but only where a
producer declared how the position was obtained. It answers "what does the Hub hold here" through
Location Intel. Each layer states its provenance.

Under ADR 0001 TheHub is the only product GUI. The spatial records are owned by their producers
(Spiderweb, AguaYLuz, Skywatcher, OVNIS…), and the Hub reads them as ingested. It never calls a
producer at runtime, and it never geocodes or infers a position.

Contract id: `federation-spatial-features-v1` (CANDIDATE, Hub-only read model).

## API

| Endpoint | Returns |
|---|---|
| `GET /api/spatial/features` | A GeoJSON FeatureCollection of drawable records, plus an account of every record that is not drawn. Parameters: `bbox` (minLon,minLat,maxLon,maxLat), `category`, `producer`, `include_synthetic`, `limit`. A malformed `bbox` returns 422 |
| `GET /api/spatial/intel` | Records within `radius_m` (10–50000) of `lat`,`lon`, nearest first, each with its distance and distance basis. With `municipality`, it also returns the records that name that municipality |

The code is in `src/hub/spatial_features.py` (pure) and `server/backend/spatial_api.py`.

## Which records are drawn

A record from the entities, observations or alerts stream becomes a point **only** when two things
hold:

- its `evidence_state.geometry_precision` is a point precision: `OBSERVED_POINT`,
  `INTERPRETED_POINT` or `REPRESENTATIVE_POINT`;
- it carries valid WGS84 coordinates.

Every other record is accounted for, never dropped:

```
loaded = matched + outside_bbox + excluded_synthetic + Σ not_drawn[*].count
```

`not_drawn`, `categories` and `area_references` are keyed by producer, **stream** and category. A
case entity and its observation, or two producers, are therefore never summed together.

| Count | Meaning |
|---|---|
| `not_drawn[*].count` | Records of that kind that are not drawn |
| `coordinates_without_point_precision` | Records that carry coordinates but declare no point precision (none, `UNKNOWN` or `AREA_REFERENCE`). Drawing them would imply a precision nobody declared |
| `municipality_recorded` | Records that name a municipality. The value is passed through in `area_references` exactly as recorded |
| `object_type_counts` | The producer's own `object_type` (for example OVNIS's UAP, Lights or Mutilation), counted as recorded |

Categories are the record types the producers exported (`entity_type`, `observation_type`, or an
alert's `module`), never labels from a reference application.

## How precision is shown

| Declared precision | Marker | Meaning shown to the reader |
|---|---|---|
| `OBSERVED_POINT` | solid | recorded as observed or authoritative |
| `INTERPRETED_POINT` | ringed (translucent fill, heavy ring) | derived: geocoded, inferred or linked to an asset |
| `REPRESENTATIVE_POINT` | hollow ring | a stand-in such as a municipio centroid; the record is not at this point |
| `AREA_REFERENCE` | dashed outline of the municipio | names an area; no point is placed |

Category colours are assigned from the categories in view, in sorted order (Okabe-Ito first).
Colour never carries meaning on its own: the legend names every category and precision, and every
mapped record also appears in the accessible "Mapped records" list. Location Intel states, for each
representative point, that the distance is to a stand-in.

## Municipality-level records

Per the 2026-10-03 decision ("Municipality only"), OVNIS cases get no points. Records that name a
municipality are outlined on the TIGERweb municipios 2025 layer (`census-tigerweb-pr-municipios-2025`
in `server/frontend/src/gis/sourceRegistry.js`), with a count per municipio. The layer is acquired
through the workbench's existing acquisition path, with its count, geometry and identity gates and
its snapshot and query-receipt hashes.

- **Joining.** A recorded value joins a municipio only on an exact name match, after folding
  accents, case and the "Municipio" suffix (`foldPlaceName` in
  `server/frontend/src/gis/propertyMap.js`).
- **Everything else is listed as recorded.** Regions ("southwest"), compound values
  ("Barceloneta/Arecibo") and "Puerto Rico" are never split, geocoded or guessed.
- **The counter.** It states how many records of the chosen kind name no municipality and are not
  mapped. It can be narrowed to one `object_type`.
- **Without the boundary layer.** Until the layer is loaded, nothing is joined, and the panel says
  the outlines need it.

What the committed store holds (T1, 2026-10-04):

- **OVNIS:** 298 `uap_case` observations; 65 record a place value. Only 2 ("vieques") name a
  municipio; the other 63 are regions (southwest, northwest, north, island-wide, east, central,
  maritime, airspace, northeast). OVNIS records the place value on the case **observation**,
  never on the case entity. Both Mutilation cases record no place value.
- **AguaYLuz `utility_asset`:** 40 records name a place and 16 name a municipio. The rest are
  compound values or "Puerto Rico".

## Location Intel

Location Intel runs at a point, which can come from any of these:

- clicking the map;
- selecting a record;
- typing "lat, lon";
- opening `/gis?view=property-map&lat=…&lon=…`.

It reports:

- the point in WGS84;
- the municipio, by point in polygon on the loaded TIGERweb layer. Otherwise it says "not
  determined" (layer not loaded) or "outside every municipio boundary";
- the radius area in acres, hectares and km², as a spherical cap on the reference sphere;
- the mapped records within the radius;
- the records that name that municipio, which are not placed at the point.

The AOI (a bbox) filters the map through `bbox` and reports its area the same way.

## Layer provenance

The provenance panel names each layer.

| Layer | What the panel shows |
|---|---|
| Hub records | Contract and counts |
| Basemap | Provider, attribution and coverage note. A basemap is display context, never an evidence layer |
| Municipio boundaries | Provider and authority, registry certification, this acquisition's gate status, CRS, retrieval time, and the SHA-256 snapshot and query-receipt hashes |
| Elevation | "No elevation model is used in this view." Terrain and its DEM provenance arrive with the Digital Twin view |

Basemaps (`server/frontend/src/gis/basemaps.js`):

- **CARTO Dark and OpenStreetMap**, shared with the workbench.
- **USGS orthoimagery** (USGS The National Map, public domain, no key). Its tile cache has no
  Puerto Rico tiles at zoom 9–10 (HTTP 404, checked 2026-10-03). It is therefore drawn from zoom 11
  over the CARTO base, and the panel says so.

The frontend sets no Content-Security-Policy, so no tile host needs allow-listing.

## Not built in this view

- **Findings on the map.** No finding record carries geometry; the OVNIS findings ledger is empty.
- **Uncertainty radii.** No producer declares a numeric positional error, so no uncertainty radius
  is drawn. Precision classes are styled instead.
- **A live cursor-coordinate readout.**
- **Barrio names.** The barrio boundary source is not live-certified in the registry.
- **Elevation, terrain and the 3D view.** These are Phase 5, P5-B.
- **Interpretive and subsurface layers, and AOI comparison.** These are Phase 5, P5-C.

## Tests

| Kind | Files |
|---|---|
| Backend | `tests/test_spatial_features.py`, `tests/test_spatial_api.py` |
| Unit | `server/frontend/src/gis/propertyMap.test.js`, `server/frontend/src/components/gis/PropertyMap.test.jsx` |
| E2E | `server/frontend/tests/visual/gui-parity.spec.js` ("property map") |

The E2E drives the real MapLibre canvas against a mocked API and a mocked TIGERweb.
