# Sky workspace v1 (candidate)

TheHub's Sky workspace is the `sky` view of the Skywatcher page, opened at `/skywatcher?view=sky`. It shows
what is above an observer at a chosen UTC instant (the Sun, the Moon and the five naked-eye planets, when they
rise and set, how dark it is, the Moon's phase), the International Space Station, Hubble and the Chinese space
station (where they are, and their passes in the next 24 hours), the latest space weather (Kp, solar-wind
speed, IMF Bz) and a "Rule out the ordinary" check: a reported sight line compared with all of that, with aircraft
tracks the person supplies and with the terrain.

Under ADR 0001 TheHub is the only product GUI, and under ADR 0006 the Hub, not Skywatcher, owns external
acquisition. So the sky is computed here, in the browser, and nothing is stored or sent to a producer. The page is
context for ruling out ordinary explanations. It is not an observation, a case or a finding: the principle is to
rule out the ordinary before promoting an unexplained result, and the absence of an identified ordinary
explanation is not evidence of an extraordinary one.

This document covers Phase 6, P6-A (the sky and space weather), P6-B (satellites) and P6-C (the exclusion check,
horizon, line of sight, field of view, clock alignment and the receipt).

## What is computed, and where

| Piece | Where | What it is |
|---|---|---|
| Astronomical state | `server/frontend/src/sky/astronomy.js` | `skyState` (contract `sky-state-v1`): Sun, Moon and Mercury, Venus, Mars, Jupiter and Saturn for an instant and an observer, built on astronomy-engine 2.1.19 (MIT, no dependencies, exactly pinned, loaded only when the Sky tab opens) |
| Space weather | `server/frontend/src/sky/spaceWeather.js` | `loadSpaceWeather`: Kp, solar-wind speed and IMF Bz read directly from NOAA SWPC |
| Satellite model | `server/frontend/src/sky/satellites.js` | `parseGp`, `elementAge`, `stateAt`, `lookAt`, `findPasses`, `skyTrack` (contract `sky-satellites-v1`): SGP4 from CelesTrak GP elements, built on satellite.js 7.1.0 (MIT, no dependencies, exactly pinned, in the same lazy chunk as the sky engine) |
| Element loader | `server/frontend/src/sky/satelliteElements.js` | `loadSatelliteElements`: one GET per object to CelesTrak, per-object `LOADED` or `FAILED` |
| Satellite view | `server/frontend/src/sky/satelliteView.js` | `satelliteSnapshot`, `chartSatellites`, `upcomingPasses`, `passTrack`: what the panel and the chart show, as pure functions |
| Chart geometry | `server/frontend/src/sky/skyChart.js` | The all-sky chart's projection, satellites and pass tracks on it, and the Kp sparkline, as pure functions |
| View | `server/frontend/src/components/sky/SkyWorkspace.jsx`, `SatellitesPanel.jsx`, `format.js` | Controls, readout, chart, satellites, space weather; mounted by `server/frontend/src/pages/Skywatcher.jsx` |
| Exclusion engines | `server/frontend/src/sky/exclusion/` | The "Rule out the ordinary" check (P6-C), below: `observation.js`, `geometry.js`, `frustum.js`, `refraction.js`, `stars.js` with `starCatalog.json`, `celestialExclusion.js`, `satelliteExclusion.js`, `aircraftTracks.js`, `aircraftExclusion.js`, `terrain.js`, `horizon.js`, `lineOfSight.js`, `clockAlignment.js`, `reconstruction.js` |
| Exclusion view | `server/frontend/src/sky/exclusion/exclusionForm.js`, `exclusionView.js`, `runExclusion.js`; `server/frontend/src/components/sky/ExclusionPanel.jsx` | The form as data, the chart's geometry, the run end to end, and the panel; the panel is its own lazy chunk |

The workspace has no backend endpoint and writes nothing, so its capability `sky-workspace` is classified
`client_only` in `.federation/gui-capabilities.json`.

## Observer and time

- **Observer.** Latitude, longitude, elevation (metres) and a fixed UTC offset (hours). With no coordinates in
  the link the observer is the labelled default, San Juan (18.4663, −66.1057), UTC−4 (Atlantic Standard Time, no
  daylight-saving time). A link that gives one coordinate without the other is refused, so a typed latitude is
  never mixed with the default longitude. **The page never asks the browser for a location.**
- **Time.** A UTC instant. The link carries it as `t` (`?view=sky&lat&lon&elev&tz&t`). A time with no `Z` or
  offset is refused, because it would be read in the viewer's own zone. "Follow the clock" is opt-in, moves the
  time to now every 30 seconds, and puts no `t` in the link; turning it off keeps the moment it stopped on.
- **Refusals.** An observer or time the engine cannot compute for is shown as an error, with no readout and no
  fallback to the default: latitude outside ±90°, longitude outside ±180°, elevation outside −500 to 10000 m, a
  UTC offset outside −12 to +14 hours, a non-number, an invalid instant.
- **The day.** Rise, transit, set and twilight times are for the local calendar day at the stated fixed offset.
  No daylight-saving rule is applied and the offset is never guessed from the longitude.

## Conventions

Every state carries its conventions (`conventions`), and the page prints them.

- **Position.** Apparent topocentric, aberration included; azimuth from north through east.
- **Altitude and refraction.** Standard atmospheric refraction is applied to a body above the horizon or within
  1° below it. Deeper below the horizon there is no apparent position to lift, so the geometric altitude is shown.
  `altitudeAirless` is always the geometric altitude. This is deliberate and measured: JPL Horizons' "refracted"
  altitude extends its value at −1° to every depth, a constant +0.6466°, so a refracted altitude for a body 35°
  below the horizon is an artifact of that model, not a position. The engine's `jplhor` refraction reproduces
  Horizons exactly and is used only to check against it.
- **Rise and set.** The upper limb at the horizon with standard refraction and the body's semidiameter (the Sun's
  centre at −0.833°). A day can have only a rise, only a set, or neither; the readout says which, and for a day
  with neither whether the body stays above or below the horizon (decided from its apparent altitude at the start
  of the window).
- **Daylight class.** From the geometric Sun centre: daylight above −0.833°, civil twilight to −6°, nautical to
  −12°, astronomical to −18°, night below.
- **Moon phase.** The elongation from the Sun and the illuminated fraction as seen from the Earth's centre. The
  four principal phases are named only within 1° of the exact phase; the next quarter is named with its UTC time.
- **Planets.** The five classical naked-eye planets. Uranus and Neptune are not shown.

## How it is held to independent references

The tests do not check the engine against itself. They check it against values frozen from two independent
services, retrieved 2026-10-18 and stored in `server/frontend/src/sky/referenceEphemerides.json` with their
parameters, conventions and the tolerances below. The tolerances were set from the differences measured when the
references were frozen, with margin.

**JPL Horizons** (84 cases: 7 bodies × 3 sites × 4 instants; San Juan, Cerro de Punta at 1322.7 m, and Santiago):

| Quantity | Largest difference | Tolerance |
|---|---|---|
| Apparent position, all bodies | 0.35 arcmin (Venus; mean 0.09) | 0.5 arcmin |
| Apparent magnitude (Moon and planets) | 0.13 (Mercury) | 0.2 |
| Moon illuminated fraction | 0.60 percentage points (geocentric here, topocentric in Horizons) | 1.0 |

By body, the largest position differences were Sun 0.035, Moon 0.043, Mercury 0.080, Venus 0.348, Mars 0.037,
Jupiter 0.071 and Saturn 0.198 arcmin.

**US Naval Observatory** (3 sites × 3 days):

| Quantity | Largest difference | Tolerance |
|---|---|---|
| Sun and Moon rise, upper transit and set; civil twilight begin and end (72 events) | 0.50 minute (USNO rounds to whole minutes) | 1 minute |
| Moon illuminated fraction against USNO's whole percent | 0.43 points | 1.0 |
| Moon quarter times | 1.32 minutes (First Quarter), 0.75 (Full Moon) | 2 minutes |
| Phase name against USNO's `curphase` | equal on all 9 site-days | exact |

The quarter-time difference is larger than USNO's rounding. It is a real difference between lunar theories worth
about 0.01° of lunar motion, so it has its own tolerance instead of loosening the event one.

**Days with no rise or set.** Tromsø (69.65°N), checked against Horizons' hourly Sun altitude: on 2026-06-21 the
Sun's altitude ranges from +3.1° to +43.7° (above the horizon all day), and on 2026-12-21 from −43.8° to −3.1°
(below the horizon all day, in civil twilight at noon).

**Live invariants.** `server/frontend/src/gis/liveProviders.test.js` repeats a subset against the real services
when `GIS_LIVE_PROVIDER_TESTS=1`. On 2026-10-18 the engine was within 0.034, 0.023 and 0.348 arcmin of Horizons for
the Sun, Moon and Venus and within 0.40 minute of USNO's rise, transit and set for San Juan. These public services
have no uptime guarantee, so a provider that cannot be reached is logged as unavailable; one that answers with data
the code cannot read, or outside the tolerance, fails.

## Space weather

All three products answer cross-origin reads, so the browser reads them directly (T1, 2026-10-15 and 2026-10-18).

| Product | URL (under `https://services.swpc.noaa.gov/products/`) | Shape |
|---|---|---|
| Planetary K-index | `noaa-planetary-k-index.json` | 3-hourly rows `{time_tag, Kp, a_running, station_count}`, 63 rows over 7.75 days when measured; the time tags carry no `Z` and are UTC |
| Solar-wind speed | `summary/solar-wind-speed.json` | one row `{proton_speed, time_tag}`, whole km/s, rounded by the provider |
| IMF | `summary/solar-wind-mag-field.json` | one row `{bt, bz_gsm, time_tag}`, whole nT, rounded by the provider |

What was **not** used, and why: the older `/products/solar-wind/*` files return 404 (retired); the 1-minute
`/json/rtsw/rtsw_wind_1m.json` (2.4 MB) and `rtsw_mag_1m.json` (1.4 MB) series mix three sources (ACE, IMAP,
SOLAR1) with an `active` flag and arrive **newest-first**, so reading the first or last row would pick a stale or
inactive source.

- **State.** Each product is `LIVE`, `STALE` (with its age) or `FAILED` (with the reason). A Kp row is stamped
  with the start of its 3-hour interval, and the next interval's value appears some time after that interval
  begins: on 2026-10-18 the 21:00 row was still missing at 21:20, although the file had been rewritten a minute
  earlier. So Kp is `LIVE` while its latest interval is the one in progress or the one just ended (up to 6 hours
  from that interval's start), and once the interval has ended the card says the next one has not been published
  yet. It is `STALE` after that. The one-minute summaries are `LIVE` within 15 minutes. These are policy
  constants, not physics. A reading timestamped more than 5 minutes in the future is `STALE` with a note.
- **Never zero.** A product that cannot be read (network, HTTP error, timeout after 10 seconds, bad JSON, no
  usable row, a value that is not a number) is `FAILED` with no value. Malformed Kp rows are dropped and counted.
  The three products fail independently.
- **Storm scale.** Kp 5 and above is shown with the NOAA geomagnetic storm scale, G1 at Kp 5 up to G5 at Kp 9, by
  whole Kp (5− is 4.67, below G1; 9− is still G4), in words and not only colour. Bz is labelled northward or
  southward; southward is the geoeffective direction.
- **Not tied to the time.** Space weather is the latest NOAA reading. It does not change with the time above and
  is not computed for other times. It refreshes every 5 minutes and on a button.
- **Sparkline.** Kp over the span the data holds (7.75 days when measured; the reference showed about 3.5), with
  time on the x axis so a gap is a gap, and the Kp 5 line marked.

## Satellites (P6-B)

Three objects are checked, and the page says so: the International Space Station (NORAD 25544), the Hubble Space
Telescope (20580) and the Chinese space station, represented by the Tianhe core module (48274, 2021-035A; docked
modules are separate catalogue objects). It is not "all satellites". Space-Track is not used: it needs credentials.

- **Elements.** CelesTrak's GP element sets, in JSON, from
  `https://celestrak.org/NORAD/elements/gp.php?CATNR=<id>&FORMAT=json` (CORS-open, no key). The loader sends one
  GET per object with an `Accept` header and nothing else, no retry and a 10 second limit, and accepts only an
  answer that holds exactly one record carrying the requested NORAD number. CelesTrak resets connections after a
  few requests a minute, so the elements are read once, kept for two hours, never polled, and a reload inside a
  minute of the last read is refused in words. Each object is `LOADED` or `FAILED`, independently: one that failed
  is listed with the reason and is never placed, defaulted or assumed.
- **Validation of an element set.** Required numbers, value ranges (eccentricity below 1, mean motion above 0 up to
  20 rev/day, angles in degrees), SGP4 theory only, the epoch read as UTC (CelesTrak's epoch carries no zone), and a
  state at the epoch. A set that fails is refused with the field named. The NORAD number, international designator,
  name and epoch are kept and shown, and the record as CelesTrak sent it is kept beside the parsed element set.
- **Age policy** (a labelled policy, not physics: SGP4 error grows by kilometres a day for a low orbit). Within 3
  days of the element epoch, either side, confidence is normal; to 7 days, lower; to 14 days, low; beyond 14 days
  nothing is predicted and the page says why. The elements are current ones, so **a past event cannot be
  reproduced**: that needs element sets from its own time.
- **Where it is.** SGP4 gives a state in the TEME frame; azimuth (from north through east), geometric elevation (no
  refraction) and range come from the observer's geodetic position, with Earth rotation from GMST (UT1−UTC
  ignored).
- **Sunlit or in shadow.** The Sun's vector comes from astronomy-engine in J2000, rotated to the equator of date
  (about 0.375° of precession by 2026) so it can be compared with TEME; the two frames differ by the equation of the
  equinoxes, about 0.005°, which is stated as an approximation. A satellite is sunlit unless it is behind the Earth
  and inside a cylinder of the Earth's equatorial radius (6378.137 km) along the Sun direction: umbra only, no
  penumbra, no atmosphere.
- **Passes.** The passes above 10° in the 24 hours from the chosen instant (a pass already under way, or still going
  at the end, is followed to its ends), each with rise, culmination and set found to about 0.1 s, maximum
  elevation, the three azimuths, duration and the confidence of its element age. The search samples the elevation every 20
  seconds, so a pass that clears the minimum for less than one step could fall between two samples; the sampled peaks that sit
  just below the minimum are refined, so a pass is found even when it clears the minimum by a few thousandths of a degree
  (found by the automated review of #407 and reproduced: before the fix, a minimum 0.02° below a pass's peak lost the pass). The track of a pass can be drawn
  on the chart, from 30 seconds before it rises above 10° to 30 seconds after it falls below.
- **Visible-pass candidate.** A pass is labelled "Visible-pass candidate (geometry only; brightness not
  estimated)" when, at some moment of it, the satellite is above 10°, sunlit, and the observer's geometric Sun
  centre is at or below −6°. Otherwise the panel says which condition failed ("in the Earth's shadow for the whole
  pass", "the sky is too bright"). **It does not estimate brightness, weather or obstructions, and is not a
  prediction that anything will be seen.**

### How the satellite model is held to references

Two independent references, and what they prove:

**The Vallado verification set.** `SGP4-VER.TLE` and `tcppver.out` from Vallado, Crawford, Hujsak and Kelso,
"Revisiting Spacetrack Report #3" (AIAA 2006-6753), unmodified, in `server/frontend/src/sky/fixtures/vallado/`
with their sha256. They were taken from the `sgp4` Python package 2.27 (Brandon Rhodes, MIT), which ships them as
test data, not from CelesTrak (unreachable when captured), so byte-for-byte agreement with CelesTrak's copy is not
established here. 33 cases, 710 compared states: the largest difference from Vallado's C++ output is 1.2e-7 km
(0.12 mm) in position and 8.5e-10 km/s in velocity; the tests hold it to 1e-6 km and 1e-8 km/s. One case
(satellite 33334, a deliberately degenerate orbit) is refused by SGP4 with error code 3, and the test asserts that
the wrapper fails closed with that code instead of showing a state.

**An independent implementation.** `server/frontend/src/sky/fixtures/satelliteReference.json` holds values computed
from the frozen element sets of all three objects by Rhodes' `sgp4` 2.27 and Skyfield 1.55 with JPL DE421 (sha256
recorded; Skyfield's built-in timescale, no IERS download), for San Juan and Sydney over a two-day window that starts a
day after each element epoch, with the sha256 of the elements fixture it was computed from (the test checks it). The
tolerances were set from the differences measured when it was frozen, with margin:

| Quantity | Largest difference measured | Tolerance |
|---|---|---|
| SGP4 position and velocity (18 states) | 0.2 m (2.1e-4 km); 2.3e-7 km/s | 5 m; 1e-5 km/s |
| Look angles (174 instants) | azimuth 0.026°, elevation 0.003°, range 0.039 km | 0.1°, 0.02°, 0.2 km |
| Sunlit or in shadow at each look | 0 mismatches of 174 | exact |
| Pass rise, culmination, set (58 passes) | 0.22 s | 1 s |
| Pass maximum elevation, azimuths at rise and set | 0.003°, 0.05° | 0.02°, 0.1° |
| Azimuth at culmination | 0.48° (a near-zenith pass, where azimuth changes fast) | 1° |
| Range at culmination, Sun altitude | 0.031 km, 0.001° | 0.2 km, 0.02° |
| Sunlit seconds in a pass | 5 s (the 5-second sampling step) | 10 s |
| Shadow entry and exit (186 transitions) | 0.13 s | 1 s |

**What this does not prove.** Both references run the same SGP4 model, so they show that this implementation
agrees with two others, **not** that a forecast matches what anyone sees: no keyless source of real sightings exists
(Heavens-Above has no API, N2YO needs a key, Space-Track needs credentials). Historical element sets are
unavailable, so no past pass has been reproduced.

**Real element sets frozen.** All three are real CelesTrak answers, in `fixtures/satellite-elements.json`, and no test
uses a synthetic one except to build a wrong answer. The ISS's is the response as CelesTrak sent it (retrieved
2026-11-03T07:19:14Z, epoch 2026-11-02T18:09:49Z; the sha256 and byte count are of the raw response). Hubble's (epoch
2026-11-03T19:01:49Z) and the Chinese space station's (epoch 2026-11-03T18:08:45Z) were read by `loadSatelliteElements`
itself, in the live test's receipt, on 2026-11-04T01:33:00Z; the raw response bytes were not kept, so their
`record_sha256` is the hash of the record's JSON text as the loader read it (number formatting may differ from
CelesTrak's own text, for example `5.437e-5` against `0.00005437`), and a test checks that hash. Hubble's period on
that day was 93.98 minutes, the Chinese space station's 92.23 and the ISS's 92.95.

**Live invariant.** `server/frontend/src/gis/liveProviders.test.js` asks CelesTrak for all three, one request
each, when `GIS_LIVE_PROVIDER_TESTS=1`, and checks each answer is the object asked for, with the inclination that
object has (the three are told apart by it) and the period of a low Earth orbit (90 to 98 minutes: the first version
of this test asserted 94 to 97 for Hubble from memory and failed on the real 93.98, so no band tighter than the
physics is asserted), and a usable position now. It prints each record with the hash of its text, so a real answer
can be frozen as a fixture. Throttling or an outage is logged as unavailable; an answer that arrives but cannot be
read, or is the wrong object, fails.

**Build note.** satellite.js 7 can load an optional WebAssembly bulk-propagation runtime. This page uses only the
plain JavaScript SGP4, so `vite.config.js` resolves the two specifiers that runtime is loaded through
(`#wasm-single-thread`, `#wasm-multi-thread`) to `server/frontend/src/sky/wasmNotUsed.js`, which throws if ever
called. Without that alias the build emits a 309 KB Emscripten module nothing loads. With it the main bundle is
unchanged (326,344 B) and the lazy Sky chunk grows from 85,180 B to 130,077 B; the E2E asserts no `.wasm` request.

## Rule out the ordinary (P6-C)

The section "Rule out the ordinary" takes a reported sight line and says which ordinary things were in it. It is a
check, not a finding: it lists geometric coincidences, never identifications, and ends in one of three plain
statements.

**What is entered.** A UTC time with an uncertainty (left blank it is recorded as undeclared, and the check is for
that instant only), an observer (latitude, longitude, and a height above the WGS84 ellipsoid, blank recorded as
undeclared, 0 m used), a direction (an azimuth with a declared reference, true or magnetic with the declination, never
assumed, and an elevation), and how close counts: a tolerance in degrees, or a camera field of view (horizontal and
vertical field, roll), optionally moving along a great circle between a start and an end direction. The window checked
is the time plus or minus the uncertainty, up to six hours. Everything entered is held in the page: it is not stored,
not put in the link, not sent anywhere and not made a case. The page never asks the browser for a location, and the
"start from the observer and time above" button copies the time, latitude and longitude only: the workspace's
elevation is a height above sea level and the check takes a height above the ellipsoid (about 43 m lower in Puerto
Rico), so it is not copied.

**What is checked.**

| Check | What it compares | What it states about itself |
|---|---|---|
| Celestial (`celestialExclusion.js`) | The Sun, Moon, five naked-eye planets and 288 stars brighter than V 3.5 (d3-celestial, from Hipparcos, BSD-3-Clause, notice kept; J2000 with no proper motion, parallax or aberration) over the whole window, as an observer sees them (apparent, with standard refraction) | Not every star; not Uranus, Neptune, comets or asteroids; visibility against the sky is not judged (the daylight class is given) |
| Satellites (`satelliteExclusion.js`) | The ISS, Hubble and the Chinese space station from the current element sets, closest approach to 0.1 s, the moments inside the sight line, whether the Sun lit it and whether the sky was dark | Three objects, not all satellites; brightness is not estimated; an object whose elements did not load, or that is more than 14 days from an element epoch (so any past observation), is NOT_CHECKED with the reason |
| Aircraft (`aircraftTracks.js`, `aircraftExclusion.js`) | Tracks the person loads (CSV or GeoJSON, read in the browser, never uploaded) against the sight line over the whole window | See below |
| Terrain (`terrain.js`, `horizon.js`, `lineOfSight.js`) | NOAA CUDEM (Puerto Rico, 1/9 arc-second, PRVD02 heights, bare earth) read from NOAA's public tiles when the option is on: a horizon per azimuth and a line of sight, with the Earth's curvature and a declared refraction coefficient (0.13 by default) | Puerto Rico only; buildings and trees are not in it; a direction with no data is UNKNOWN, not clear |

**Aircraft tracks.** The source, the altitude reference (the WGS84 ellipsoid; mean sea level with a declared geoid
separation; or barometric with a declared uncertainty, because a pressure altitude is not a geometric height) and the
unit must be declared, and a row with no altitude is rejected, not read as ground level. A report is OBSERVED. A
position between two reports no more than the gap length apart (30 s by default) is INTERPOLATED on a straight line.
A longer interval, or one that would need more than 1,000 m/s, is a GAP and is never filled in, and nothing is
extrapolated before the first report or after the last. A track that has no data in the window is NOT_CHECKED
("no data is not the same as no aircraft"). Each track gets a quality in the vocabulary of the Skywatcher flight
session schema (`continuous`, `gapped`, `sparse_evidence`, `single_point`, with `gap_count`) and the Skywatcher
eligibility rule of at least two valid observations; Skywatcher assigns `track_quality` from the source and the point
count, so the gap length and the speed bound are this workspace's own declared policy, recorded in every result. The
quality is coverage and never a judgement of the flight. Optional position and altitude uncertainties are carried
through: an aircraft outside the sight line that could be inside it given the declared uncertainty is listed
separately and is not counted as a candidate; an undeclared uncertainty is not zero. A callsign is a label the file
carries, not an identity, and a track in a sight line is a geometric coincidence, not targeting. Terrain hides an
aircraft only if the terrain is nearer than the aircraft.

**The terrain horizon.** For every 0.5 degrees of azimuth the ground is walked outward (20 to 100 m steps, to 40 km by
default in the page) and the highest elevation angle is kept, with a running maximum by distance so that a target with a distance
is hidden only by terrain nearer than it. Heights stay in CUDEM's own datum (PRVD02), so no ellipsoidal conversion is
needed for the horizon; water is the water surface, not the sea floor. A ray that meets a cell with no data is
incomplete, and a body above its terrain angle is then UNKNOWN: only terrain that is there can make a body OBSTRUCTED.
The horizon is drawn on the chart as a shaded band, with a dotted arc outside the rim where the data runs out.

**Clock alignment (`clockAlignment.js`).** Events from several sources go on one UTC timeline as
`skywatcher-multisensor-replay-v1` does: the union of the timestamps, no interpolation, gaps declared with a reason,
overlapping gaps refused. Clock offsets are declared with their basis (a non-zero offset with no basis is refused) and
are never inferred, and a source with nothing at a timestamp is NO_REPORT, which is missing data and not zero. The page
applies only the clock offset declared for the tracks file; aligning further sources has no form yet (FDX-038 is
partial). Its digest is not a Skywatcher replay digest.

**The receipt (`reconstruction.js`).** Contract `sky-exclusion-v1`, `NOT_CERTIFIED`. It holds the observation as entered,
the candidates (each with its basis: MODELLED for a body or satellite computed from an ephemeris or elements, OBSERVED
or INTERPOLATED for an aircraft), everything that was not checked or only partly (including terrain, when no horizon was
used), eight ordinary explanations this kind of check can never rule in or out (aircraft not in the data, other
satellites, balloons and drones, meteors and atmospheric light, optical effects, birds and insects, objects beyond the
checked sets, and error in the report), the terrain horizon and the alignment summary, and a reconstruction of the sky at
the reported instant. The conclusion is one of: `NO_ORDINARY_CANDIDATE_IDENTIFIED` (the sentence "NO ORDINARY CANDIDATE
IDENTIFIED among the sets that were checked", the sets, and the reminder that the absence of an identified ordinary
explanation is not evidence of an extraordinary one); `ORDINARY_CANDIDATES_LISTED` (each a geometric coincidence, not an
identification, with nothing said about intent); or `NOT_ASSESSED` (nothing could be checked, so nothing is ruled out). No
text in it claims an anomaly or says what was seen. It is downloaded as JSON under a name carrying the time and the first
12 hex digits of its SHA-256, which is of the body as stable JSON (sorted keys, compact) without `generatedAt`, so the same
inputs give the same digest and anyone can recompute it from the file; where the browser offers no SHA-256 the digest is
null and says so.

### How the exclusion engines are held to references

| Piece | Held to | Measured |
|---|---|---|
| Geodetic to look angles (`geometry.js`) | Skyfield 1.55's WGS84 model, 40 cases at five observers and heights from -100 m to 15 km | 9e-12 degrees, 1e-9 m; asserted to 1e-9 degrees and 1e-6 m |
| Stars (`stars.js`) | The US Naval Observatory celestial navigation service, 12 site-instants and 336 star observations | Altitude and direction within 0.04 degrees, largest 0.026 (Alpha Centauri's proper motion, which the catalogue does not apply), mean 0.0036 |
| Aircraft look angles and passes | Skyfield for reports and for straight-line positions between them (to 9e-12 degrees), and a dense 1 ms scan for the closest approach and the moments inside the sight line | Minimum separation within 6e-7 degrees (the scan's own resolution), entry and exit within 1 ms; asserted to 2e-6 degrees and 3 ms |
| Satellites in a sight line | The independent Skyfield reference for the ISS look at San Juan | The station is found within 0.05 degrees of where the reference puts it |
| Sea horizon, ridge | Closed forms: minus acos(R_eff / (R_eff + h)) for the sea; the elevation of a ridge's near edge over the curve | Within 0.003 degrees (sea) and the sampling step (ridge) |
| Horizon | A second algorithm that scans every cell of a height grid instead of walking rays | Within 0.1 degrees everywhere, mean under 0.02 |
| Line of sight | The sea-horizon sum of two eyes, a ridge over the curve, and the horizon engine on 600 random targets over synthetic hills | The threshold within half a percent; no disagreement with the horizon on 600 targets |
| Live CUDEM (outage tolerant, `GIS_LIVE_PROVIDER_TESTS=1`) | Real tiles at San Juan and at Puerto Rico's highest point | See below |

Every one of these was also checked the other way: a change that fills a gap, drops the interpolation, ignores the
curvature, treats missing data as clear, or lets a nearer ridge hide nothing makes a test fail.

What the live CUDEM check showed, on 2026-11-04. At San Juan (18.4663, -66.1057) CUDEM puts the ground at 7.4 m
(PRVD02). Due north is the open Atlantic, but the horizon there is +1.24 degrees, not near zero: the terrain within 100 m
of that coastal point rises above the 9.4 m eye (shoreline relief; the highest horizon in any direction is 3.05 degrees,
0.22 km away). Beyond about 4 km offshore CUDEM has no data, so the rays over the sea are incomplete and a body above them
is UNKNOWN, not clear. At the island's summit (CUDEM ground 1,330.7 m) the horizon is below the horizontal in every
direction that has data (at most -0.56 degrees). The profile-based line of sight and the horizon engine disagreed on 6 of 1,572 real-terrain targets with data in a
probe of 2,000 while this was written, all within 3.1 m (0.008 degrees) of the boundary and the same at 0.25 and 0.5
degree azimuth steps: the profile is sampled every 25 m, the horizon every 20 to 100 m, and 3 m terrain changes by metres
between samples. The live test over 400 targets allows a band of 0.02 degrees around the boundary, counts what falls in
it, and requires no disagreement outside it. No keyless independent horizon exists to hold this to: PVGIS's horizon service was tried
and reports 3.4 to 4.2 degrees over open sea, which is not physical, so it is not used.

Bundle: the main bundle is 326,377 B against 326,344 B on main (the preload map names one more shared chunk); the lazy Sky
chunk is 132,182 B; the exclusion panel and its engines are their own lazy chunk of 110,552 B, loaded when the Sky tab
opens, and the CUDEM reader and the GeoTIFF library come only when the terrain option is used (a 3,052 B terrain chunk over
the 58,722 B `cudem` chunk).

## The chart

The all-sky chart (`svg[data-sky-chart]`) is the sky as seen looking up: north at the top, east at the left, the
zenith at the centre, the horizon at the rim, rings at 30° and 60° of altitude. Each body has its own shape and a
label, so meaning never rests on colour alone. A satellite has a shape of its own (a body with two panels), filled when
the Sun lights it and hollow when it is in the Earth's shadow, and a pass track can be drawn as a dashed line with a
hollow dot at the rise and a filled one at the set; the symbol is not a brightness. Labels sit beside their glyphs (on the inner side when the outer side would run off the chart, as the Moon on the
western rim did) and are nudged so that no label overlaps another label or another body's glyph, even when bodies crowd together (the Sun, Mercury and Venus a few
degrees apart low in the west is the case that prompted it). Bodies and satellites below the horizon are not drawn and are named
under the chart, so all seven bodies and every satellite with a position are always accounted for. The chart is a 2D view; there is no 3D dome.

## Not built

- **A 3D dome** (TWIN-120 is partial: the 2D chart above).
- **A live camera** (TWIN-121 stays blocked: no authoritative Puerto Rico sky-camera source has been identified).
- **Satellite brightness**, and any prediction that a satellite will be seen: a visible-pass candidate is geometry
  only. **All satellites**, other than the three named; **past passes** (no historical element sets).
- **Live aircraft and Skywatcher's tracks.** The aircraft check takes tracks the person loads (TWIN-117 is partial). OpenSky
  answers cross-origin reads only for its own origin (asked with a foreign `Origin` it replies
  `access-control-allow-origin: https://opensky-network.org`), and the Hub does not proxy it by decision. Skywatcher's
  federation export is not consumed: in the repository as read for this change it holds three observations, each one point
  at a single instant, georeferenced from a screenshot icon with a 7 km uncertainty, which is not a trajectory. An ADS-B
  contact census (TWIN-041, TWIN-107) needs the live feed and a stated coverage denominator.
- **A standalone point-to-point line-of-sight tool** (FDX-032 is partial: the engine exists and adjudicates terrain in the
  check, but the page has no tool for it), **a time scrubber or animation** (FDX-040 is partial: the page shows the
  instant and the window result), **aligning sources other than the tracks file** (FDX-038 is partial), **satellite
  brightness and past passes** (FDX-035 is partial).
- **Terrain outside Puerto Rico**, and anything above bare earth.
- **Space weather history or a time machine.** Only the latest reading is shown.
- **Daylight-saving or named time zones.** A fixed offset only.

## Blind spots

- No real reported observation exists in the Federation, so nothing here has been run on a real case: the engine is
  held to frozen reference values, not to an event.
- The reference set covers 2026-10-15, 2026-10-16 and 2026-12-21 and four instants; agreement far from those dates
  is not measured here.
- astronomy-engine's own accuracy statement (about 1 arcminute) is the author's claim; the measured numbers above
  are what this repository relies on.
- The frozen references are what the services returned on 2026-10-18 and could be revised.
- Satellites: the real element sets are those of 2026-11-02 and 2026-11-03, so agreement was measured for orbits at
  those epochs and windows, not for other dates or for a degraded orbit; Hubble's and the Chinese space station's raw
  response bytes were not kept (see above). Skyfield and the model under test both implement SGP4, so
  their agreement is not a check of the SGP4 model against reality. The shadow is a cylinder (no penumbra), and the
  Sun is rotated to the equator of date rather than to TEME exactly. The Chinese space station is the Tianhe core
  module's element set, used for the station.
- The exclusion check has not been run on a real reported observation, because none exists in the Federation: its
  scenarios are built from computed positions and held to independent references, not to an event. Both Skyfield and the
  engines implement the same straight-line interpolation and SGP4 model, so agreement shows the arithmetic and the
  scanning are right, not that an aircraft flies straight between reports or that SGP4 matches reality.
- The checked sets are small next to what can be in a sky (see the eight blind spots in every receipt), and a body in a
  sight line is a coincidence: the check cannot say what was seen.
- Terrain: bare earth, a 3 m DEM read as a 33 m grid within 5 km of the observer and a 223 m grid beyond, no keyless independent horizon to hold it to, and CUDEM's
  bathymetry ends a few kilometres offshore. The refraction coefficient (0.13) is the standard value; real air varies from
  about 0 to 0.25 and more over water.
- The star catalogue has no proper motion (up to 0.026 degrees for the worst case), and its names come from the catalogue's
  own name table.
- Element sets are retrieved when the page opens and are two hours old at most before a reload; the age policy is a
  stated policy, and a pass near the 14-day limit is low confidence, not wrong or right.

## Tests

| Kind | Files |
|---|---|
| Unit | `server/frontend/src/sky/astronomy.test.js`, `server/frontend/src/sky/spaceWeather.test.js`, `server/frontend/src/sky/skyChart.test.js`, `server/frontend/src/sky/satellites.test.js`, `server/frontend/src/sky/satelliteElements.test.js`, `server/frontend/src/sky/satelliteView.test.js`, `server/frontend/src/components/sky/SkyWorkspace.test.jsx`, `server/frontend/src/components/sky/SkyWorkspaceSatellites.test.jsx`, `server/frontend/src/components/sky/ExclusionPanel.test.jsx`, and one test file for each engine in `server/frontend/src/sky/exclusion/` (`observation`, `geometry`, `frustum`, `refraction`, `stars`, `celestialExclusion`, `satelliteExclusion`, `aircraftTracks`, `aircraftExclusion`, `terrain`, `horizon`, `lineOfSight`, `terrainIntegration`, `clockAlignment`, `reconstruction`, `exclusionForm`, `exclusionView`, `runExclusion`) |
| Frozen references | `server/frontend/src/sky/referenceEphemerides.json`, `server/frontend/src/sky/fixtures/swpc-samples.json` (real NOAA payloads), `server/frontend/src/sky/fixtures/satellite-elements.json` (a real CelesTrak answer), `server/frontend/src/sky/fixtures/satelliteReference.json` (Skyfield and sgp4), `server/frontend/src/sky/fixtures/vallado/` (the Vallado verification set), `server/frontend/src/sky/exclusion/fixtures/` (Skyfield geometry, USNO celestial navigation, Skyfield and a dense scan for aircraft), `server/frontend/src/sky/exclusion/starCatalog.json` (d3-celestial, BSD-3-Clause, with its notice) |
| Live | `server/frontend/src/gis/liveProviders.test.js` (NOAA SWPC, JPL Horizons, USNO, CelesTrak and NOAA CUDEM, behind `GIS_LIVE_PROVIDER_TESTS=1`) |
| E2E | `server/frontend/tests/visual/gui-parity.spec.js` ("sky workspace") |

The E2E also aims a sight line at the station and at a supplied track, refuses a tracks file with no declaration, downloads the
receipt and asserts that nothing typed or loaded left the browser. It serves the real SWPC payloads and the CelesTrak element sets with the CORS header the providers send, fixes
the page's clock, holds the Sun's altitude to the frozen Horizons value, holds the station's passes to the Skyfield
reference, and asserts one request per satellite and no WebAssembly request. The sandbox Chromium used in CI cannot
reach NOAA or CelesTrak.
