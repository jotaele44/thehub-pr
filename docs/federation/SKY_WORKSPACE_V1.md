# Sky workspace v1 (candidate)

TheHub's Sky workspace is the `sky` view of the Skywatcher page, opened at `/skywatcher?view=sky`. It shows
what is above an observer at a chosen UTC instant (the Sun, the Moon and the five naked-eye planets, when they
rise and set, how dark it is, the Moon's phase) and the latest space weather (Kp, solar-wind speed, IMF Bz).

Under ADR 0001 TheHub is the only product GUI, and under ADR 0006 the Hub, not Skywatcher, owns external
acquisition. So the sky is computed here, in the browser, and nothing is stored or sent to a producer. The page is
context for ruling out ordinary explanations. It is not an observation, a case or a finding: the principle is to
rule out the ordinary before promoting an unexplained result, and the absence of an identified ordinary
explanation is not evidence of an extraordinary one.

This document covers Phase 6, P6-A. Satellites (P6-B) and the exclusion engine, horizon and line of sight (P6-C)
are separate changes.

## What is computed, and where

| Piece | Where | What it is |
|---|---|---|
| Astronomical state | `server/frontend/src/sky/astronomy.js` | `skyState` (contract `sky-state-v1`): Sun, Moon and Mercury, Venus, Mars, Jupiter and Saturn for an instant and an observer, built on astronomy-engine 2.1.19 (MIT, no dependencies, exactly pinned, loaded only when the Sky tab opens) |
| Space weather | `server/frontend/src/sky/spaceWeather.js` | `loadSpaceWeather`: Kp, solar-wind speed and IMF Bz read directly from NOAA SWPC |
| Chart geometry | `server/frontend/src/sky/skyChart.js` | The all-sky chart's projection and the Kp sparkline, as pure functions |
| View | `server/frontend/src/components/sky/SkyWorkspace.jsx` | Controls, readout, chart, space weather; mounted by `server/frontend/src/pages/Skywatcher.jsx` |

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
  with the start of its 3-hour interval, so it is `LIVE` for that interval plus 15 minutes (195 minutes); the
  one-minute summaries are `LIVE` within 15 minutes. These are policy constants, not physics. A reading
  timestamped more than 5 minutes in the future is `STALE` with a note.
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

## The chart

The all-sky chart (`svg[data-sky-chart]`) is the sky as seen looking up: north at the top, east at the left, the
zenith at the centre, the horizon at the rim, rings at 30° and 60° of altitude. Each body has its own shape and a
label, so meaning never rests on colour alone. Bodies below the horizon are not drawn and are named under the
chart, so all seven are always accounted for. The chart is a 2D view; there is no 3D dome.

## Not built

- **A 3D dome** (TWIN-120 is partial: the 2D chart above).
- **A live camera** (TWIN-121 stays blocked: no authoritative Puerto Rico sky-camera source has been identified).
- **Satellites** and visible passes (P6-B); **exclusion, horizon, line of sight, frustum and reconstruction**
  (P6-C); **aircraft** (Skywatcher's export is synthetic, OpenSky does not allow browser reads, and the Hub does
  not proxy it by decision).
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

## Tests

| Kind | Files |
|---|---|
| Unit | `server/frontend/src/sky/astronomy.test.js`, `server/frontend/src/sky/spaceWeather.test.js`, `server/frontend/src/sky/skyChart.test.js`, `server/frontend/src/components/sky/SkyWorkspace.test.jsx` |
| Frozen references | `server/frontend/src/sky/referenceEphemerides.json`, `server/frontend/src/sky/fixtures/swpc-samples.json` (real NOAA payloads) |
| Live | `server/frontend/src/gis/liveProviders.test.js` (NOAA SWPC, JPL Horizons and USNO, behind `GIS_LIVE_PROVIDER_TESTS=1`) |
| E2E | `server/frontend/tests/visual/gui-parity.spec.js` ("sky workspace") |

The E2E serves the real SWPC payloads with the CORS header the provider sends, fixes the page's clock, and holds
the Sun's altitude to the frozen Horizons value. The sandbox Chromium used in CI cannot reach NOAA.
