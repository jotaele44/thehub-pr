import React, { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { formatClock, instantFrom, makeObserver, skyState } from '@/sky/astronomy';
import { ALTITUDE_RINGS, CARDINALS, CHART_RADIUS, chartBodies, kpSparkline } from '@/sky/skyChart';
import { loadSpaceWeather } from '@/sky/spaceWeather';

// The Sky workspace (directive §9; TWIN-008, 111..131): what is above an observer at a chosen UTC instant (Sun,
// Moon, naked-eye planets, daylight class, rise and set), and the latest space weather. The observer, the time and
// the offset are explicit and live in the URL, so a view can be shared. This page never asks the browser for a
// location. It is context for ruling out ordinary explanations, not a finding of any kind.
const DEFAULT_OBSERVER = Object.freeze({ lat: 18.4663, lon: -66.1057, elevation: 0, tzHours: -4 });
const OBSERVER_KEYS = ['lat', 'lon', 'elev', 'tz'];
const FOLLOW_INTERVAL_MS = 30000;
const SPACE_WEATHER_REFRESH_MS = 300000;
const button = 'min-h-[44px] rounded-md border border-border px-3 text-sm font-medium hover:bg-muted disabled:opacity-50';
const field = 'min-h-[44px] w-full rounded-md border border-border bg-background px-2 text-sm';

const isoOf = (date) => date.toISOString().replace('.000Z', 'Z');
const degrees = (value) => `${value.toFixed(1)}°`;
const offsetLabel = (tz) => (tz === 0 ? 'UTC' : `UTC${tz > 0 ? '+' : '-'}${Math.abs(tz)}`);

function readNumber(label, raw, fallback) {
  if (raw === null || raw === '') return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new RangeError(`${label} is not a number: ${raw}`);
  return value;
}

// The observer in the link, or the labelled default. A link that names one coordinate without the other is
// refused: mixing a typed latitude with the default longitude would be a silent guess.
function readObserver(params) {
  const given = OBSERVER_KEYS.filter((key) => params.has(key));
  if (!given.length) return { ...DEFAULT_OBSERVER, isDefault: true };
  if (params.has('lat') !== params.has('lon')) throw new RangeError('Give both latitude and longitude, or neither.');
  const lat = readNumber('Latitude', params.get('lat'), DEFAULT_OBSERVER.lat);
  const lon = readNumber('Longitude', params.get('lon'), DEFAULT_OBSERVER.lon);
  const elevation = readNumber('Elevation', params.get('elev'), 0);
  const tzHours = readNumber('UTC offset', params.get('tz'), 0);
  return { lat, lon, elevation, tzHours, isDefault: false };
}

function formatAge(minutes) {
  if (minutes === null || minutes === undefined) return '';
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 1440) {
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return rest ? `${hours} h ${rest} min ago` : `${hours} h ago`;
  }
  return `${Math.floor(minutes / 1440)} d ${Math.floor((minutes % 1440) / 60)} h ago`;
}

const eventText = (date, tz) => `${formatClock(date, tz)} ${offsetLabel(tz)} (${formatClock(date, 0)} UTC)`;
const MISSING = Object.freeze({ rise: 'no rise this day', set: 'no set this day', transit: 'no upper transit this day', civilTwilightBegin: 'no civil twilight start this day', civilTwilightEnd: 'no civil twilight end this day' });
const ALL_DAY = Object.freeze({
  ABOVE_HORIZON_ALL_DAY: 'above the horizon all day (no rise or set)',
  BELOW_HORIZON_ALL_DAY: 'below the horizon all day (no rise or set)',
});

function Events({ item, tz, keys }) {
  return (
    <>
      {ALL_DAY[item.status] ? <p data-testid="event-status">{ALL_DAY[item.status]}</p> : null}
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        {keys.map(([key, label]) => (
          <React.Fragment key={key}>
            <dt className="text-muted-foreground">{label}</dt>
            <dd data-testid={`event-${key.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}`}>{item[key] ? eventText(item[key], tz) : MISSING[key]}</dd>
          </React.Fragment>
        ))}
      </dl>
    </>
  );
}

function Position({ item }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
      <dt className="text-muted-foreground">Altitude</dt><dd data-testid="altitude">{degrees(item.altitude)}</dd>
      <dt className="text-muted-foreground">Azimuth</dt><dd data-testid="azimuth">{degrees(item.azimuth)}</dd>
    </dl>
  );
}

function Glyph({ shape }) {
  switch (shape) {
    case 'sun': return <g><circle r="5" fill="currentColor" />{[0, 45, 90, 135, 180, 225, 270, 315].map((a) => <line key={a} x1="0" y1="-7" x2="0" y2="-10" stroke="currentColor" strokeWidth="1.5" transform={`rotate(${a})`} />)}</g>;
    case 'moon': return <circle r="5.5" fill="none" stroke="currentColor" strokeWidth="2" />;
    case 'triangle': return <path d="M0,-6 L6,5 L-6,5 Z" fill="currentColor" />;
    case 'diamond': return <path d="M0,-6.5 L6.5,0 L0,6.5 L-6.5,0 Z" fill="currentColor" />;
    case 'square': return <rect x="-5" y="-5" width="10" height="10" fill="currentColor" />;
    case 'cross': return <path d="M-6,0 H6 M0,-6 V6" stroke="currentColor" strokeWidth="2.5" />;
    case 'ringed': return <g><circle r="3.5" fill="currentColor" /><ellipse rx="8" ry="2.5" fill="none" stroke="currentColor" strokeWidth="1.2" /></g>;
    default: return <circle r="4" fill="currentColor" />;
  }
}

function SkyChart({ sky }) {
  const { plotted, below } = useMemo(() => chartBodies(sky), [sky]);
  const label = `Sky chart: north at the top, east at the left, zenith at the centre, horizon at the rim. ${plotted.length} of 7 bodies are above the horizon.`;
  return (
    <div>
      <svg data-sky-chart viewBox="-125 -125 250 250" role="img" aria-label={label} className="mx-auto h-auto w-full max-w-[26rem] text-foreground">
        <circle r={CHART_RADIUS} fill="none" stroke="currentColor" strokeWidth="1.5" />
        {ALTITUDE_RINGS.map((ring) => <circle key={ring.altitude} r={ring.radius} fill="none" stroke="currentColor" strokeWidth="0.5" strokeDasharray="2 3" opacity="0.6" />)}
        <line x1={-CHART_RADIUS} y1="0" x2={CHART_RADIUS} y2="0" stroke="currentColor" strokeWidth="0.4" opacity="0.5" />
        <line x1="0" y1={-CHART_RADIUS} x2="0" y2={CHART_RADIUS} stroke="currentColor" strokeWidth="0.4" opacity="0.5" />
        {CARDINALS.map((c) => <text key={c.label} x={c.x} y={c.y} textAnchor="middle" dominantBaseline="central" fontSize="9" fontWeight="600" fill="currentColor">{c.label}</text>)}
        {ALTITUDE_RINGS.map((ring) => <text key={`l${ring.altitude}`} x="3" y={-ring.radius + 8} fontSize="6" fill="currentColor" opacity="0.7">{ring.altitude}°</text>)}
        {plotted.map((body) => (
          <g key={body.body} data-sky-glyph={body.body} transform={`translate(${body.x.toFixed(2)} ${body.y.toFixed(2)})`} className="text-foreground">
            <Glyph shape={body.shape} />
            <text x={body.labelDx} y={body.labelDy} fontSize="8" fill="currentColor" className="stroke-background" strokeWidth="3" paintOrder="stroke">{body.label}</text>
          </g>
        ))}
      </svg>
      <p data-sky-below className="mt-2 text-xs text-muted-foreground">
        Below the horizon, not drawn: {below.length ? below.map((b) => `${b.label} (${degrees(b.altitude)})`).join(', ') : 'none'}.
      </p>
    </div>
  );
}

function BodyCard({ attribute, title, children }) {
  return (
    <section {...attribute} className="space-y-2 rounded-xl border border-border p-3 text-sm">
      <h4 className="font-semibold">{title}</h4>
      {children}
    </section>
  );
}

const SUN_EVENTS = [['civilTwilightBegin', 'Civil twilight begins'], ['rise', 'Sunrise'], ['transit', 'Upper transit'], ['set', 'Sunset'], ['civilTwilightEnd', 'Civil twilight ends']];
const BODY_EVENTS = [['rise', 'Rise'], ['transit', 'Upper transit'], ['set', 'Set']];

function Readout({ sky, tz }) {
  const { sun, moon, planets, daylight } = sky;
  const quarter = moon.phase.nextQuarter;
  return (
    <div className="space-y-3">
      <p data-sky-daylight className="rounded-md border border-border bg-muted/40 p-3 text-sm">
        <strong>{daylight.label}</strong> at this observer and time: the Sun is {degrees(sun.altitude)} {sun.aboveHorizon ? 'above' : 'below'} the horizon
        (geometric centre {degrees(sun.altitudeAirless)}).
      </p>
      <BodyCard attribute={{ 'data-sky-sun': true }} title="Sun">
        <Position item={sun} />
        <Events item={sun} tz={tz} keys={SUN_EVENTS} />
      </BodyCard>
      <BodyCard attribute={{ 'data-sky-moon': true }} title="Moon">
        <Position item={moon} />
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
          <dt className="text-muted-foreground">Phase</dt><dd data-testid="phase-name">{moon.phase.name}</dd>
          <dt className="text-muted-foreground">Illuminated</dt><dd data-testid="illumination">{(moon.illuminatedFraction * 100).toFixed(1)}%</dd>
          <dt className="text-muted-foreground">Magnitude</dt><dd data-testid="magnitude">{moon.magnitude.toFixed(1)}</dd>
          <dt className="text-muted-foreground">Next quarter</dt>
          <dd data-testid="next-quarter">{quarter.name} · {isoOf(quarter.time).slice(0, 10)} {formatClock(quarter.time, 0)} UTC</dd>
        </dl>
        <Events item={moon} tz={tz} keys={BODY_EVENTS} />
      </BodyCard>
      <div className="grid gap-3 sm:grid-cols-2">
        {planets.map((planet) => (
          <BodyCard key={planet.body} attribute={{ 'data-sky-planet': planet.body }} title={planet.body}>
            <p>{planet.aboveHorizon ? 'Above the horizon' : 'Below the horizon'}</p>
            <Position item={planet} />
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
              <dt className="text-muted-foreground">Magnitude</dt><dd data-testid="magnitude">{planet.magnitude.toFixed(1)}</dd>
              <dt className="text-muted-foreground">Elongation</dt><dd>{degrees(planet.elongation)} from the Sun</dd>
            </dl>
            <Events item={planet} tz={tz} keys={[['rise', 'Rise'], ['set', 'Set']]} />
          </BodyCard>
        ))}
      </div>
    </div>
  );
}

function ObserverAndTime({ draft, setDraft, apply, timeDraft, setTimeDraft, applyTime, step, now, follow, setFollowing, instant, formError }) {
  const set = (key) => (event) => setDraft((previous) => ({ ...previous, [key]: event.target.value }));
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <form className="space-y-2" onSubmit={(event) => { event.preventDefault(); apply(); }} aria-label="Observer">
        <h3 className="text-base font-semibold">Observer</h3>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-sm">Latitude (°N)<input className={field} inputMode="decimal" value={draft.lat} onChange={set('lat')} /></label>
          <label className="text-sm">Longitude (°E)<input className={field} inputMode="decimal" value={draft.lon} onChange={set('lon')} /></label>
          <label className="text-sm">Elevation (m)<input className={field} inputMode="decimal" value={draft.elevation} onChange={set('elevation')} /></label>
          <label className="text-sm">UTC offset (hours)<input className={field} inputMode="decimal" value={draft.tzHours} onChange={set('tzHours')} /></label>
        </div>
        <button type="submit" className={button}>Apply observer</button>
      </form>
      <div className="space-y-2">
        <h3 className="text-base font-semibold">Time</h3>
        <p data-sky-time className="text-sm">Instant (UTC): <span className="font-mono">{isoOf(instant)}</span></p>
        <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); applyTime(); }}>
          <label className="min-w-[14rem] flex-1 text-sm">Time (UTC)<input className={`${field} font-mono`} value={timeDraft} onChange={(event) => setTimeDraft(event.target.value)} /></label>
          <button type="submit" className={button}>Set time</button>
        </form>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Move the time">
          <button type="button" className={button} onClick={() => step(-86400e3)}>Back 1 day</button>
          <button type="button" className={button} onClick={() => step(-3600e3)}>Back 1 hour</button>
          <button type="button" className={button} onClick={() => step(3600e3)}>Forward 1 hour</button>
          <button type="button" className={button} onClick={() => step(86400e3)}>Forward 1 day</button>
          <button type="button" className={button} onClick={() => step(now() - instant.getTime())}>Now</button>
        </div>
        <label className="flex min-h-[44px] items-center gap-2 text-sm">
          <input type="checkbox" checked={follow} onChange={(event) => setFollowing(event.target.checked)} />
          Follow the clock
        </label>
        <p className="text-xs text-muted-foreground">Following moves the time to now every 30 seconds. Otherwise the time stays where it is.</p>
      </div>
      {formError ? <p role="alert" className="col-span-full rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm text-destructive">{formError}</p> : null}
    </div>
  );
}

function Spark({ kp }) {
  const line = useMemo(() => kpSparkline(kp.series, { width: 240, height: 60 }), [kp.series]);
  if (!line) return null;
  const first = kp.series[0].time.toISOString().slice(0, 10);
  const last = kp.series[kp.series.length - 1].time.toISOString().slice(0, 10);
  return (
    <svg data-sw-sparkline viewBox="-4 -6 248 72" role="img" className="h-auto w-full max-w-[20rem] text-foreground"
      aria-label={`Kp over ${kp.spanDays.toFixed(1)} days, ${first} to ${last} UTC; latest ${kp.value.toFixed(2)}; the dashed line is Kp 5, where the NOAA G1 storm scale begins`}>
      <line x1="0" x2="240" y1={line.thresholdY} y2={line.thresholdY} stroke="currentColor" strokeWidth="0.8" strokeDasharray="3 3" opacity="0.7" />
      <text x="2" y={line.thresholdY - 2} fontSize="6" fill="currentColor">G1 (Kp 5)</text>
      <path d={line.path} fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx={line.points[line.points.length - 1].x} cy={line.points[line.points.length - 1].y} r="2.5" fill="currentColor" />
    </svg>
  );
}

function Measure({ item, children }) {
  const failed = item.state === 'FAILED';
  return (
    <section data-sw={item.id} className="space-y-1 rounded-xl border border-border p-3 text-sm">
      <h4 className="font-semibold">{item.label}</h4>
      <p>
        <span data-testid="sw-state" className="rounded border border-border px-1.5 py-0.5 text-xs font-semibold">{item.state}</span>
        {!failed ? <span data-sw-age className="ml-2 text-muted-foreground">{formatAge(item.ageMinutes)}</span> : null}
      </p>
      {failed ? <p>Unavailable: {item.error}</p> : (
        <>
          <p className="text-lg font-semibold"><span data-testid="sw-value">{item.id === 'kp' ? item.value.toFixed(2) : item.value}</span> {item.unit === 'Kp' ? '' : item.unit}</p>
          {children}
          <p className="text-xs text-muted-foreground">As of {isoOf(item.observedAt)} UTC{item.precision ? ` · ${item.precision}` : ''}</p>
          {item.note ? <p className="text-xs text-muted-foreground">{item.note}</p> : null}
        </>
      )}
      <p className="text-xs text-muted-foreground">Source: {item.source.provider}</p>
    </section>
  );
}

function SpaceWeather() {
  const query = useQuery({
    queryKey: ['sky-space-weather'], queryFn: () => loadSpaceWeather(), staleTime: 60000, refetchInterval: SPACE_WEATHER_REFRESH_MS, retry: false,
  });
  const data = query.data;
  return (
    <section className="space-y-3" aria-labelledby="sky-sw">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="sky-sw" className="text-base font-semibold">Space weather</h3>
        <button type="button" className={button} onClick={() => query.refetch()} disabled={query.isFetching}>Refresh space weather</button>
      </div>
      <p data-sw-note className="text-xs text-muted-foreground">
        The latest NOAA SWPC readings, not tied to the time above: space weather is not computed for other times. A product that cannot be read
        is shown as unavailable, never as zero.
      </p>
      {query.isLoading ? <p role="status" className="text-sm text-muted-foreground">Reading NOAA SWPC…</p> : null}
      {query.isError ? <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm text-destructive">Space weather could not be read: {query.error?.message}</p> : null}
      {data ? (
        <div className="grid gap-3 md:grid-cols-3">
          <Measure item={data.kp}>
            {data.kp.state !== 'FAILED' ? (
              <>
                {data.kp.scale ? <p data-sw-scale className="font-semibold">{data.kp.scale} — geomagnetic storm (NOAA scale)</p> : null}
                <p className="text-xs">{data.kp.stationCount === null ? 'Station count not given' : `${data.kp.stationCount} stations`}</p>
                <Spark kp={data.kp} />
              </>
            ) : null}
          </Measure>
          <Measure item={data.solarWind} />
          <Measure item={data.imf}>
            {data.imf.state !== 'FAILED' ? <p className="text-xs">Bz points {data.imf.direction}{data.imf.bt === null ? '' : `; total field ${data.imf.bt} nT`}</p> : null}
          </Measure>
        </div>
      ) : null}
    </section>
  );
}

export default function SkyWorkspace() {
  const [params, setParams] = useSearchParams();
  const [loadedAt] = useState(() => new Date());
  const [now, setNow] = useState(() => new Date());
  const [follow, setFollow] = useState(false);
  const [formError, setFormError] = useState('');

  const timeParam = params.get('t');
  const computed = useMemo(() => {
    try {
      const observer = readObserver(params);
      const instant = timeParam ? instantFrom(timeParam) : (follow ? now : loadedAt);
      return { observer, instant, sky: skyState({ time: instant, lat: observer.lat, lon: observer.lon, elevation: observer.elevation, tzHours: observer.tzHours }) };
    } catch (error) {
      return { error: error.message, instant: (() => { try { return timeParam ? instantFrom(timeParam) : (follow ? now : loadedAt); } catch { return loadedAt; } })() };
    }
  }, [params, timeParam, follow, now, loadedAt]);
  const { observer, instant, sky } = computed;

  const draftOf = (o) => ({ lat: String(o.lat), lon: String(o.lon), elevation: String(o.elevation), tzHours: String(o.tzHours) });
  const [draft, setDraft] = useState(() => (computed.observer ? draftOf(computed.observer) : draftOf(DEFAULT_OBSERVER)));
  const observerKey = OBSERVER_KEYS.map((key) => params.get(key) ?? '').join('|');
  useEffect(() => { if (computed.observer) setDraft(draftOf(computed.observer)); }, [observerKey]);
  const [timeDraft, setTimeDraft] = useState(() => isoOf(instant));
  useEffect(() => { setTimeDraft(isoOf(instant)); }, [timeParam]);

  useEffect(() => {
    if (!follow) return undefined;
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), FOLLOW_INTERVAL_MS);
    return () => clearInterval(id);
  }, [follow]);

  const write = (change) => {
    const next = new URLSearchParams(params);
    change(next);
    setParams(next, { replace: true });
  };
  const applyObserver = () => {
    try {
      const lat = readNumber('Latitude', draft.lat.trim(), Number.NaN);
      const lon = readNumber('Longitude', draft.lon.trim(), Number.NaN);
      const elevation = readNumber('Elevation', draft.elevation.trim(), 0);
      const tzHours = readNumber('UTC offset', draft.tzHours.trim(), 0);
      makeObserver({ lat, lon, elevation });
      skyState({ time: instant, lat, lon, elevation, tzHours });
      setFormError('');
      write((next) => { next.set('lat', draft.lat.trim()); next.set('lon', draft.lon.trim()); next.set('elev', draft.elevation.trim() || '0'); next.set('tz', draft.tzHours.trim() || '0'); });
    } catch (error) {
      setFormError(error.message);
    }
  };
  const setTime = (date) => { setFollow(false); write((next) => next.set('t', isoOf(date))); };
  const applyTime = () => {
    try {
      setTime(instantFrom(timeDraft.trim()));
      setFormError('');
    } catch (error) {
      setFormError(error.message);
    }
  };
  const step = (ms) => setTime(new Date(instant.getTime() + ms));
  const setFollowing = (on) => {
    setFollow(on);
    if (on) write((next) => next.delete('t'));
    else write((next) => next.set('t', isoOf(instant)));
  };

  const tz = observer?.tzHours ?? DEFAULT_OBSERVER.tzHours;
  return (
    <div className="space-y-4" data-sky-workspace>
      <div>
        <h2 className="text-lg font-semibold">Sky</h2>
        <p className="text-sm text-muted-foreground">
          What is above an observer at a chosen UTC instant, computed here, in the browser, with astronomy-engine and checked in tests against JPL
          Horizons and the US Naval Observatory. It is context for ruling out ordinary explanations: it is not an observation, a case or a finding.
        </p>
      </div>
      {observer?.isDefault ? (
        <p role="note" data-sky-default-observer className="rounded-md border border-amber-500/60 bg-amber-500/10 p-2 text-sm">
          Default observer: San Juan, Puerto Rico ({DEFAULT_OBSERVER.lat}, {DEFAULT_OBSERVER.lon}), UTC−4 (Atlantic Standard Time, no daylight-saving time).
          Change the coordinates to compute for another place. This page does not ask your browser for your location.
        </p>
      ) : null}
      <ObserverAndTime
        draft={draft} setDraft={setDraft} apply={applyObserver} timeDraft={timeDraft} setTimeDraft={setTimeDraft} applyTime={applyTime}
        step={step} now={() => Date.now()} follow={follow} setFollowing={setFollowing} instant={instant} formError={computed.error || formError}
      />
      {sky ? (
        <>
          <h3 className="text-base font-semibold">Readout</h3>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
            <SkyChart sky={sky} />
            <Readout sky={sky} tz={tz} />
          </div>
          <section data-sky-conventions className="rounded-md border border-border p-3 text-xs text-muted-foreground">
            <h4 className="mb-1 text-sm font-semibold text-foreground">Conventions</h4>
            <ul className="list-disc space-y-0.5 pl-4">
              {Object.entries(sky.conventions).map(([key, text]) => <li key={key}>{text}</li>)}
            </ul>
          </section>
        </>
      ) : null}
      <SpaceWeather />
    </div>
  );
}
