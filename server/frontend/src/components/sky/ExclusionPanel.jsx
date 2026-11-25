import React, { useMemo, useRef, useState } from 'react';
import {
  DEFAULT_TERRAIN_DRAFT, EMPTY_DECLARATION_DRAFT, EMPTY_OBSERVATION_DRAFT, draftFromWorkspace,
} from '@/sky/exclusion/exclusionForm';
import { overlayGeometry } from '@/sky/exclusion/exclusionView';
import { BLIND_SPOTS, PRINCIPLE, receiptFileName, receiptJson } from '@/sky/exclusion/reconstruction';
import { runExclusion } from '@/sky/exclusion/runExclusion';
import { MAX_FILE_CHARACTERS } from '@/sky/exclusion/aircraftTracks';
import { ALTITUDE_RINGS, CARDINALS, CHART_RADIUS } from '@/sky/skyChart';
import { button, degrees, field, isoOf } from './format';

// "Rule out the ordinary" (Phase 6, P6-C; TWIN-118, FDX-032..040): a reported sight line, checked against the Sun, Moon,
// planets, bright stars, the three satellites the Sky workspace tracks, and aircraft tracks the person supplies, with the
// terrain if it can be read. Everything runs in this browser. The report, the tracks file and the result live in this page's
// memory only: nothing is stored, sent or made a case. The answer is a receipt that says what was checked, what was found
// in the sight line (each a geometric coincidence, never an identification), what could not be checked, and what this kind of
// check can never rule in or out. It is NOT_CERTIFIED and it is not a finding.
const TRUE_OR_MAGNETIC = [['', 'Choose…'], ['TRUE', 'From true north'], ['MAGNETIC', 'From magnetic north']];
const ALTITUDE_REFERENCES = [['', 'Choose…'], ['ELLIPSOID', 'Above the WGS84 ellipsoid'], ['MSL', 'Above mean sea level'], ['BAROMETRIC', 'Barometric (pressure) altitude']];

function readFileText(file) {
  if (typeof file.text === 'function') return file.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error('The file could not be read.'));
    reader.readAsText(file);
  });
}

function Field({ id, label, hint, error, children }) {
  return (
    <div className="text-sm">
      <label htmlFor={id} className="block">{label}</label>
      {children}
      {hint ? <p id={`${id}-hint`} className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
      {error ? <p id={`${id}-error`} role="alert" className="mt-0.5 text-xs text-destructive">{error}</p> : null}
    </div>
  );
}

function Input({ id, error, hint, ...rest }) {
  const described = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') || undefined;
  return <input id={id} className={field} aria-invalid={error ? 'true' : undefined} aria-describedby={described} {...rest} />;
}

function Select({ id, error, options, ...rest }) {
  return (
    <select id={id} className={field} aria-invalid={error ? 'true' : undefined} aria-describedby={error ? `${id}-error` : undefined} {...rest}>
      {options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
    </select>
  );
}

const Mono = ({ children, ...rest }) => <span className="font-mono" {...rest}>{children}</span>;

function Overlay({ geometry, observation, candidates }) {
  const { sightline, objects, below, unavailable, horizon } = geometry;
  const label = `Sky at the reported instant, ${isoOf(observation.time)} UTC: north at the top, east at the left, zenith at the centre, horizon at the rim. `
    + `The reported sight line is at azimuth ${degrees(sightline.centre.azimuth)}, elevation ${degrees(sightline.centre.elevation)}${sightline.belowHorizon ? ', which is below the horizon' : ''}. `
    + `${objects.length} objects are above the horizon; ${candidates.length === 0 ? 'none is a candidate for the sight line' : (candidates.length === 1 ? 'one is a candidate for the sight line' : `${candidates.length} are candidates for the sight line`)}.`;
  return (
    <div data-exclusion-chart>
      <svg viewBox="-125 -125 250 250" role="img" aria-label={label} className="mx-auto h-auto w-full max-w-[26rem] text-foreground">
        <circle r={CHART_RADIUS} fill="none" stroke="currentColor" strokeWidth="1.5" />
        {ALTITUDE_RINGS.map((ring) => <circle key={ring.altitude} r={ring.radius} fill="none" stroke="currentColor" strokeWidth="0.5" strokeDasharray="2 3" opacity="0.6" />)}
        <line x1={-CHART_RADIUS} y1="0" x2={CHART_RADIUS} y2="0" stroke="currentColor" strokeWidth="0.4" opacity="0.5" />
        <line x1="0" y1={-CHART_RADIUS} x2="0" y2={CHART_RADIUS} stroke="currentColor" strokeWidth="0.4" opacity="0.5" />
        {CARDINALS.map((c) => <text key={c.label} x={c.x} y={c.y} textAnchor="middle" dominantBaseline="central" fontSize="9" fontWeight="600" fill="currentColor">{c.label}</text>)}
        {horizon ? (
          <g data-exclusion-horizon className="text-foreground">
            <path d={horizon.maskD} fillRule="evenodd" fill="currentColor" fillOpacity="0.25" stroke="none" />
            {horizon.noDataD ? <path data-exclusion-horizon-nodata d={horizon.noDataD} fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="1 2.5" /> : null}
          </g>
        ) : null}
        {objects.map((o) => (
          <g key={`${o.category}-${o.id ?? o.name}`} data-exclusion-object={o.name} data-category={o.category} data-candidate={o.candidate ? 'true' : undefined} transform={`translate(${o.x} ${o.y})`} className="text-foreground">
            {o.category === 'aircraft' ? <path d="M0,-4.5 L4,3.5 L-4,3.5 Z" fill="currentColor" />
              : (o.category === 'satellite' ? <rect x="-2.5" y="-2.5" width="5" height="5" fill="none" stroke="currentColor" strokeWidth="1.5" />
                : <circle r={o.kind === 'star' ? 1.6 : 3.2} fill={o.kind === 'moon' ? 'none' : 'currentColor'} stroke="currentColor" strokeWidth={o.kind === 'moon' ? 1.5 : 0} />)}
            {o.candidate ? <circle r="7" fill="none" stroke="currentColor" strokeWidth="1.2" /> : null}
            {o.labelled ? <text x={o.labelDx} y={o.labelDy} textAnchor={o.labelAnchor} fontSize="7" fontWeight={o.candidate ? 700 : 400} fill="currentColor" className="stroke-background" strokeWidth="2.5" paintOrder="stroke">{o.label}</text> : null}
          </g>
        ))}
        <g data-exclusion-sightline={sightline.kind} className="text-foreground">
          {sightline.trackD ? <path d={sightline.trackD} fill="none" stroke="currentColor" strokeWidth="0.8" strokeDasharray="1 2" /> : null}
          {sightline.shapes.map((s) => (s.d ? <path key={s.at} data-exclusion-outline={s.at} d={s.d} fill="currentColor" fillOpacity="0.08" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" /> : null))}
          {sightline.centreXY ? <path data-exclusion-centre d={`M${sightline.centreXY.x - 15} ${sightline.centreXY.y} H${sightline.centreXY.x - 10} M${sightline.centreXY.x + 10} ${sightline.centreXY.y} H${sightline.centreXY.x + 15} M${sightline.centreXY.x} ${sightline.centreXY.y - 15} V${sightline.centreXY.y - 10} M${sightline.centreXY.x} ${sightline.centreXY.y + 10} V${sightline.centreXY.y + 15}`} stroke="currentColor" strokeWidth="1.4" fill="none" /> : null}
        </g>
      </svg>
      <p className="mt-2 text-xs text-muted-foreground" data-exclusion-chart-key>
        Four ticks mark the centre of the reported sight line, and the dashed outline is its {sightline.kind === 'frustum' ? 'field of view' : 'tolerance'} (too small to see for a narrow one){sightline.trackD ? '; the dotted line is where it moved' : ''}. A ring marks a candidate; only candidates and the nearest Sun, Moon, planets, satellites and aircraft are named.
        {horizon ? ` Shaded band: ground that rises above the horizontal (bare earth; ${horizon.peak && horizon.peak.elevation > 0 ? `the highest is ${degrees(horizon.peak.elevation)} at azimuth ${degrees(horizon.peak.azimuth)}` : 'there is none here: the terrain horizon is at or below the horizontal in every direction that has data'}).${horizon.noDataRays ? ` Dotted arc outside the rim: ${horizon.noDataRays} of ${horizon.rays} directions where the terrain has no data, which is unknown, not clear.` : ''}` : ''}
        Dot: Sun, Moon, planet or star. Square: satellite. Triangle: aircraft. Positions are at the reported instant{observation.motion ? ' (the start of the movement)' : ''}.
      </p>
      <p data-exclusion-below className="mt-1 text-xs text-muted-foreground">
        Below the horizon, not drawn: {below.length ? `${below.length} objects (${below.slice(0, 8).map((b) => b.name).join(', ')}${below.length > 8 ? ', …' : ''})` : 'none'}.
        {unavailable.length ? ` No position at this instant, not drawn: ${unavailable.map((u) => `${u.name} (${u.reason})`).join(', ')}.` : ''}
      </p>
    </div>
  );
}

function Candidates({ receipt }) {
  if (!receipt.candidates.length) return <p data-testid="no-candidates">No candidate was found among the sets that were checked.</p>;
  return (
    <div className="overflow-x-auto">
      <table data-testid="candidates" className="w-full min-w-[44rem] border-collapse text-left text-xs">
        <caption className="mb-1 text-left text-xs text-muted-foreground">Inside the reported sight line at some moment of the window. Each is a geometric coincidence, not an identification.</caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className="py-1 pr-2 font-semibold">Object</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Basis</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Closest</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Inside the sight line</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Terrain</th>
            <th scope="col" className="py-1 font-semibold">Note</th>
          </tr>
        </thead>
        <tbody>
          {receipt.candidates.map((c) => (
            <tr key={`${c.category}-${c.id ?? c.name}`} data-candidate={c.name} className="border-b border-border align-top">
              <th scope="row" className="py-1 pr-2 text-left font-semibold">{c.name}<br /><span className="font-normal text-muted-foreground">{c.kind}</span></th>
              <td className="py-1 pr-2" data-testid="candidate-basis">{c.basis}</td>
              <td className="py-1 pr-2">{c.minSeparationDegrees.toFixed(3)}° at {String(c.closestAt).slice(11, 19)} UTC</td>
              <td className="py-1 pr-2">{c.firstInside ? <>{String(c.firstInside).slice(11, 23)} to {String(c.lastInside).slice(11, 23)} UTC</> : '—'}</td>
              <td className="py-1 pr-2">{c.terrain}</td>
              <td className="py-1">{c.note}{c.category === 'satellite' ? <> {c.visibleCandidate ? 'Lit by the Sun and the sky is dark: a visible-pass candidate (geometry only).' : 'Not a visible-pass candidate (not lit, or the sky is not dark).'}</> : null}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Tracks({ aircraft }) {
  if (!aircraft) return null;
  return (
    <div className="overflow-x-auto">
      <table data-testid="track-quality" className="w-full min-w-[36rem] border-collapse text-left text-xs">
        <caption className="mb-1 text-left text-xs text-muted-foreground">
          Tracks supplied ({aircraft.denominator.tracks}), {aircraft.denominator.checked} compared. Quality is coverage, never a judgement of the flight.
        </caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className="py-1 pr-2 font-semibold">Track</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Quality</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Reports</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Gaps</th>
            <th scope="col" className="py-1 font-semibold">Window coverage</th>
          </tr>
        </thead>
        <tbody>
          {aircraft.items.map((i) => (
            <tr key={i.id} data-track={i.id} className="border-b border-border align-top">
              <th scope="row" className="py-1 pr-2 text-left font-semibold">{i.id}{i.label ? <><br /><span className="font-normal text-muted-foreground">label: {i.label}</span></> : null}</th>
              <td className="py-1 pr-2">{i.quality.track_quality ?? 'none'}{i.quality.eligible ? '' : ' (not eligible)'}</td>
              <td className="py-1 pr-2">{i.quality.validObservations}</td>
              <td className="py-1 pr-2">{i.quality.gap_count}</td>
              <td className="py-1">{i.status === 'CHECKED' ? `${i.coverage.state}: ${i.coverage.interpolatedSeconds} s of ${i.coverage.windowSeconds} s${i.coverage.gapSeconds ? `, ${i.coverage.gapSeconds} s in gaps` : ''}${i.coverage.outsideTrackSeconds ? `, ${i.coverage.outsideTrackSeconds} s outside the track` : ''}` : `Not compared: ${i.message}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Result({ run, onDownload }) {
  const { receipt, observation, reconstruction } = run;
  const geometry = useMemo(() => overlayGeometry(observation, reconstruction, receipt.candidates, run.horizon), [observation, reconstruction, receipt, run.horizon]);
  const { conclusion } = receipt;
  return (
    <section data-exclusion-result className="space-y-3" aria-labelledby="exclusion-result-heading">
      <h4 id="exclusion-result-heading" className="text-base font-semibold">Result</h4>
      <div role="status" data-exclusion-conclusion={conclusion.kind} className="space-y-1 rounded-md border border-border bg-muted/40 p-3 text-sm">
        <p className="text-base font-bold" data-testid="conclusion-headline">{conclusion.headline}</p>
        <p data-testid="conclusion-text">{conclusion.text}</p>
        <p className="text-xs text-muted-foreground">
          <span data-testid="certification" className="rounded border border-border px-1.5 py-0.5 font-semibold">{receipt.certification.status}</span>{' '}
          {receipt.certification.meaning}
        </p>
      </div>
      <Candidates receipt={receipt} />
      {receipt.possibleWithinUncertainty.length ? (
        <div data-exclusion-possible className="rounded-md border border-border p-2 text-xs">
          <p className="font-semibold">Outside the sight line, but could be inside it given the position uncertainty declared (not counted as candidates)</p>
          <ul className="list-disc pl-4">{receipt.possibleWithinUncertainty.map((p) => <li key={p.id}>{p.name}: {p.minSeparationDegrees.toFixed(3)}° away, position uncertainty {p.angularUncertaintyDegrees.toFixed(2)}°.</li>)}</ul>
        </div>
      ) : null}
      <Tracks aircraft={run.aircraft} />
      <Overlay geometry={geometry} observation={observation} candidates={receipt.candidates} />
      <div data-exclusion-not-checked className="space-y-1 text-sm">
        <h5 className="font-semibold">Not checked, or only partly</h5>
        {receipt.notChecked.length ? (
          <ul className="list-disc space-y-0.5 pl-4 text-xs">
            {receipt.notChecked.map((n, i) => <li key={`${n.category}-${n.what}-${i}`}><strong>{n.what}</strong> ({n.category}): {n.message ?? n.reason}</li>)}
          </ul>
        ) : <p className="text-xs">Everything asked for was checked.</p>}
        {receipt.terrainNote ? <p className="text-xs" data-testid="terrain-note">{receipt.terrainNote}</p> : null}
      </div>
      <details data-exclusion-blind-spots className="rounded-md border border-border p-2 text-xs">
        <summary className="cursor-pointer text-sm font-semibold">What this check can never rule in or out ({BLIND_SPOTS.length})</summary>
        <ul className="mt-1 list-disc space-y-0.5 pl-4">{receipt.blindSpots.map((b) => <li key={b}>{b}</li>)}</ul>
        <p className="mt-1">{PRINCIPLE}</p>
      </details>
      <div className="space-y-1 rounded-md border border-border p-3 text-xs">
        <button type="button" className={button} onClick={onDownload}>Download the receipt (JSON)</button>
        <p>
          File <Mono>{receiptFileName(receipt)}</Mono>. SHA-256 of the receipt body: <Mono data-testid="digest">{receipt.contentDigest ?? 'not computed (no secure context)'}</Mono>.
        </p>
        <p className="text-muted-foreground">{receipt.privacy}</p>
      </div>
    </section>
  );
}

export default function ExclusionPanel({ observer, instant, satelliteData }) {
  const [draft, setDraft] = useState(EMPTY_OBSERVATION_DRAFT);
  const [declaration, setDeclaration] = useState(EMPTY_DECLARATION_DRAFT);
  const [terrain, setTerrain] = useState({ enabled: false, draft: DEFAULT_TERRAIN_DRAFT });
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [run, setRun] = useState(null);
  const formRef = useRef(null);

  const set = (key) => (event) => setDraft((previous) => ({ ...previous, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value }));
  const setDecl = (key) => (event) => setDeclaration((previous) => ({ ...previous, [key]: event.target.value }));
  const setTerr = (key) => (event) => setTerrain((previous) => ({ ...previous, draft: { ...previous.draft, [key]: event.target.value } }));
  const errorFor = (key) => (error && error.field === key ? error.message : undefined);
  const declFieldError = (key) => (error?.field === `declaration.${key}` ? error.message : undefined);

  const onFile = async (event) => {
    const picked = event.target.files?.[0];
    setFileError('');
    if (!picked) { setFile(null); return; }
    if (picked.size > MAX_FILE_CHARACTERS) { setFile(null); setFileError(`The file is ${(picked.size / 1048576).toFixed(1)} MB; this check takes at most ${MAX_FILE_CHARACTERS / 1048576} MB.`); return; }
    try {
      setFile({ name: picked.name, size: picked.size, text: await readFileText(picked) });
    } catch (e) {
      setFile(null);
      setFileError(`The file could not be read: ${e.message}`);
    }
  };

  const onRun = async (event) => {
    event.preventDefault();
    setStatus('running');
    setError(null);
    try {
      const result = await runExclusion({
        observationDraft: draft,
        tracks: file ? { text: file.text, name: file.name, declarationDraft: declaration } : null,
        satelliteData,
        terrain,
      });
      if (!result.ok) {
        setError({ field: result.field, message: result.message });
        setRun(null);
        setStatus('idle');
        const id = result.field === 'tracks' ? 'ex-file' : `ex-${String(result.field ?? '').replace('declaration.', 'decl-').replace('terrain.', 'terrain-')}`;
        setTimeout(() => document.getElementById(id)?.focus(), 0);
        return;
      }
      setRun(result);
      setStatus('done');
    } catch (e) {
      setError({ field: null, message: `The check could not be completed: ${e.message}` });
      setRun(null);
      setStatus('idle');
    }
  };

  const download = () => {
    const blob = new Blob([receiptJson(run.receipt)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = receiptFileName(run.receipt);
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  const clear = () => {
    setDraft(EMPTY_OBSERVATION_DRAFT);
    setDeclaration(EMPTY_DECLARATION_DRAFT);
    setTerrain({ enabled: false, draft: DEFAULT_TERRAIN_DRAFT });
    setFile(null);
    setFileError('');
    setError(null);
    setRun(null);
    setStatus('idle');
  };

  const satellitesReady = Boolean(satelliteData?.items?.some((i) => i.state === 'LOADED'));
  const reference = declaration.altitudeReference;
  return (
    <section className="space-y-3" aria-labelledby="sky-exclusion" data-sky-exclusion>
      <h3 id="sky-exclusion" className="text-base font-semibold">Rule out the ordinary</h3>
      <p data-exclusion-note className="text-xs text-muted-foreground">
        Enter a reported sight line and this checks it against the Sun, Moon, planets and bright stars, the three satellites above, and aircraft tracks you supply,
        with the terrain if it can be read. A body in the sight line is a geometric coincidence, not an identification. {PRINCIPLE} Nothing you type or load here is stored,
        sent anywhere or made a case: it stays in this page until you leave it. The result is not certified and is not a finding.
      </p>
      <form ref={formRef} className="space-y-4" onSubmit={onRun} aria-label="Reported observation" noValidate>
        <fieldset className="space-y-2 rounded-xl border border-border p-3">
          <legend className="px-1 text-sm font-semibold">Reported observation</legend>
          <button type="button" className={button} onClick={() => setDraft((d) => draftFromWorkspace(d, { observer, instant }))}>Start from the observer and time above</button>
          <p className="text-xs text-muted-foreground">Fills the time, latitude and longitude from the Sky workspace. The height is not copied: it is a height above the ellipsoid here, not above sea level.</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <Field id="ex-time" label="Reported at (UTC)" error={errorFor('time')} hint="With a zone, for example 2026-11-04T12:02:04Z"><Input id="ex-time" className={`${field} font-mono`} value={draft.time} onChange={set('time')} error={errorFor('time')} hint /></Field>
            <Field id="ex-timeUncertainty" label="Uncertainty in that time (± seconds)" error={errorFor('timeUncertainty')} hint="Blank is recorded as undeclared (the exact instant only)"><Input id="ex-timeUncertainty" inputMode="decimal" value={draft.timeUncertainty} onChange={set('timeUncertainty')} error={errorFor('timeUncertainty')} hint /></Field>
            <Field id="ex-lat" label="Observer latitude, degrees north" error={errorFor('lat')}><Input id="ex-lat" inputMode="decimal" value={draft.lat} onChange={set('lat')} error={errorFor('lat')} /></Field>
            <Field id="ex-lon" label="Observer longitude, degrees east" error={errorFor('lon')}><Input id="ex-lon" inputMode="decimal" value={draft.lon} onChange={set('lon')} error={errorFor('lon')} /></Field>
            <Field id="ex-height" label="Height above the WGS84 ellipsoid (m)" error={errorFor('height')} hint="Optional. Blank is recorded as undeclared (0 m). About 43 m higher than ellipsoidal in Puerto Rico when measured above sea level"><Input id="ex-height" inputMode="decimal" value={draft.height} onChange={set('height')} error={errorFor('height')} hint /></Field>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Field id="ex-azimuth" label="Sight line azimuth (°)" error={errorFor('azimuth')}><Input id="ex-azimuth" inputMode="decimal" value={draft.azimuth} onChange={set('azimuth')} error={errorFor('azimuth')} /></Field>
            <Field id="ex-elevation" label="Sight line elevation (°)" error={errorFor('elevation')}><Input id="ex-elevation" inputMode="decimal" value={draft.elevation} onChange={set('elevation')} error={errorFor('elevation')} /></Field>
            <Field id="ex-azimuthReference" label="Azimuth reference" error={errorFor('azimuthReference')}><Select id="ex-azimuthReference" options={TRUE_OR_MAGNETIC} value={draft.azimuthReference} onChange={set('azimuthReference')} error={errorFor('azimuthReference')} /></Field>
            {draft.azimuthReference === 'MAGNETIC' ? (
              <Field id="ex-declination" label="Magnetic declination (° east of true north)" error={errorFor('declination')} hint="For the place and date; it is not looked up or guessed"><Input id="ex-declination" inputMode="decimal" value={draft.declination} onChange={set('declination')} error={errorFor('declination')} hint /></Field>
            ) : null}
          </div>
          <div role="radiogroup" aria-label="How close counts" className="flex flex-wrap gap-4 text-sm">
            <label className="flex min-h-[44px] items-center gap-2"><input type="radio" name="ex-extent" checked={draft.extent === 'TOLERANCE'} onChange={() => setDraft((d) => ({ ...d, extent: 'TOLERANCE' }))} />A tolerance around the sight line</label>
            <label className="flex min-h-[44px] items-center gap-2"><input type="radio" name="ex-extent" checked={draft.extent === 'FRUSTUM'} onChange={() => setDraft((d) => ({ ...d, extent: 'FRUSTUM' }))} />A camera field of view</label>
          </div>
          {draft.extent === 'TOLERANCE' ? (
            <div className="grid gap-2 sm:grid-cols-2"><Field id="ex-tolerance" label="Tolerance (° from the sight line)" error={errorFor('tolerance')}><Input id="ex-tolerance" inputMode="decimal" value={draft.tolerance} onChange={set('tolerance')} error={errorFor('tolerance')} /></Field></div>
          ) : (
            <div className="grid gap-2 sm:grid-cols-3">
              <Field id="ex-hfov" label="Horizontal field of view (°)" error={errorFor('hfov')}><Input id="ex-hfov" inputMode="decimal" value={draft.hfov} onChange={set('hfov')} error={errorFor('hfov')} /></Field>
              <Field id="ex-vfov" label="Vertical field of view (°)" error={errorFor('vfov')}><Input id="ex-vfov" inputMode="decimal" value={draft.vfov} onChange={set('vfov')} error={errorFor('vfov')} /></Field>
              <Field id="ex-roll" label="Roll (°)" error={errorFor('roll')} hint="0 if the camera was level"><Input id="ex-roll" inputMode="decimal" value={draft.roll} onChange={set('roll')} error={errorFor('roll')} hint /></Field>
            </div>
          )}
          <label className="flex min-h-[44px] items-center gap-2 text-sm"><input type="checkbox" checked={draft.moving} onChange={set('moving')} />The sight line moved during the observation</label>
          {draft.moving ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <Field id="ex-endAzimuth" label="End azimuth (°)" error={errorFor('endAzimuth')}><Input id="ex-endAzimuth" inputMode="decimal" value={draft.endAzimuth} onChange={set('endAzimuth')} error={errorFor('endAzimuth')} /></Field>
              <Field id="ex-endElevation" label="End elevation (°)" error={errorFor('endElevation')}><Input id="ex-endElevation" inputMode="decimal" value={draft.endElevation} onChange={set('endElevation')} error={errorFor('endElevation')} /></Field>
              <Field id="ex-endTime" label="Ended at (UTC)" error={errorFor('endTime')}><Input id="ex-endTime" className={`${field} font-mono`} value={draft.endTime} onChange={set('endTime')} error={errorFor('endTime')} /></Field>
            </div>
          ) : null}
        </fieldset>

        <fieldset className="space-y-2 rounded-xl border border-border p-3">
          <legend className="px-1 text-sm font-semibold">Aircraft tracks (optional)</legend>
          <p className="text-xs text-muted-foreground">
            A CSV with the columns time, lat, lon, altitude (and optionally id, callsign) or a GeoJSON file. It is read in this browser and never uploaded. Say where it came from and what its altitudes are:
            a height is not guessed, and a row without one is rejected. A callsign is a label, not an identity.
          </p>
          <Field id="ex-file" label="Tracks file" error={fileError || errorFor('tracks')}><input id="ex-file" type="file" accept=".csv,.geojson,.json,text/csv,application/json,application/geo+json" className={field} onChange={onFile} aria-describedby={fileError ? 'ex-file-error' : undefined} /></Field>
          {file ? <p data-exclusion-file className="text-xs">Loaded <Mono>{file.name}</Mono>, {(file.size / 1024).toFixed(1)} KB, held in memory only.</p> : null}
          {file ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <Field id="ex-decl-source" label="Where the tracks came from" error={declFieldError('source')}><Input id="ex-decl-source" value={declaration.source} onChange={setDecl('source')} error={declFieldError('source')} /></Field>
              <Field id="ex-decl-altitudeReference" label="Altitude reference" error={declFieldError('altitudeReference')}><Select id="ex-decl-altitudeReference" options={ALTITUDE_REFERENCES} value={declaration.altitudeReference} onChange={setDecl('altitudeReference')} error={declFieldError('altitudeReference')} /></Field>
              <Field id="ex-decl-altitudeUnits" label="Altitude unit" error={declFieldError('altitudeUnits')}><Select id="ex-decl-altitudeUnits" options={[['', 'Choose…'], ['m', 'Metres'], ['ft', 'Feet']]} value={declaration.altitudeUnits} onChange={setDecl('altitudeUnits')} error={declFieldError('altitudeUnits')} /></Field>
              {reference === 'MSL' || reference === 'BAROMETRIC' ? (
                <Field id="ex-decl-geoidSeparation" label="Geoid separation (m)" error={declFieldError('geoidSeparation')} hint="About −43 m at San Juan. Needed for heights above sea level"><Input id="ex-decl-geoidSeparation" inputMode="decimal" value={declaration.geoidSeparation} onChange={setDecl('geoidSeparation')} error={declFieldError('geoidSeparation')} hint /></Field>
              ) : null}
              <Field id="ex-decl-altitudeUncertainty" label="Altitude uncertainty (m)" error={declFieldError('altitudeUncertainty')} hint={reference === 'BAROMETRIC' ? 'Required for a barometric altitude' : 'Optional'}><Input id="ex-decl-altitudeUncertainty" inputMode="decimal" value={declaration.altitudeUncertainty} onChange={setDecl('altitudeUncertainty')} error={declFieldError('altitudeUncertainty')} hint /></Field>
              <Field id="ex-decl-horizontalUncertainty" label="Horizontal position uncertainty (m)" error={declFieldError('horizontalUncertainty')} hint="Optional"><Input id="ex-decl-horizontalUncertainty" inputMode="decimal" value={declaration.horizontalUncertainty} onChange={setDecl('horizontalUncertainty')} error={declFieldError('horizontalUncertainty')} hint /></Field>
              <Field id="ex-decl-clockOffset" label="Clock offset (s to add to reach UTC)" error={declFieldError('clockOffset')} hint="Optional. Blank means the times are UTC as written"><Input id="ex-decl-clockOffset" inputMode="decimal" value={declaration.clockOffset} onChange={setDecl('clockOffset')} error={declFieldError('clockOffset')} hint /></Field>
              <Field id="ex-decl-gapSeconds" label="Gap length (s)" error={declFieldError('gapSeconds')} hint="Optional. Default 30: a longer interval between reports is a gap and is not filled in"><Input id="ex-decl-gapSeconds" inputMode="decimal" value={declaration.gapSeconds} onChange={setDecl('gapSeconds')} error={declFieldError('gapSeconds')} hint /></Field>
            </div>
          ) : null}
        </fieldset>

        <fieldset className="space-y-2 rounded-xl border border-border p-3">
          <legend className="px-1 text-sm font-semibold">Terrain (optional)</legend>
          <label className="flex min-h-[44px] items-center gap-2 text-sm">
            <input type="checkbox" checked={terrain.enabled} onChange={(e) => setTerrain((t) => ({ ...t, enabled: e.target.checked }))} />
            Use the terrain horizon (NOAA CUDEM, Puerto Rico only)
          </label>
          <p className="text-xs text-muted-foreground">Reads elevation tiles from NOAA in this browser. Bare earth: buildings and trees are not in it. Where it has no data a direction is UNKNOWN, not clear.</p>
          {terrain.enabled ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <Field id="ex-terrain-aboveGround" label="Eye height above the ground (m)" error={errorFor('terrain.aboveGround')}><Input id="ex-terrain-aboveGround" inputMode="decimal" value={terrain.draft.aboveGround} onChange={setTerr('aboveGround')} error={errorFor('terrain.aboveGround')} /></Field>
              <Field id="ex-terrain-refractionK" label="Refraction coefficient" error={errorFor('terrain.refractionK')} hint="0.13 is the standard"><Input id="ex-terrain-refractionK" inputMode="decimal" value={terrain.draft.refractionK} onChange={setTerr('refractionK')} error={errorFor('terrain.refractionK')} hint /></Field>
              <Field id="ex-terrain-radiusKm" label="Terrain range (km)" error={errorFor('terrain.radiusKm')}><Input id="ex-terrain-radiusKm" inputMode="decimal" value={terrain.draft.radiusKm} onChange={setTerr('radiusKm')} error={errorFor('terrain.radiusKm')} /></Field>
            </div>
          ) : null}
        </fieldset>

        <p data-exclusion-satellites className="text-xs text-muted-foreground">
          Satellites: {satellitesReady ? `uses the ${satelliteData.items.filter((i) => i.state === 'LOADED').length} of ${satelliteData.items.length} element sets loaded above (the ISS, Hubble and the Chinese space station — not all satellites). A past time cannot be checked.` : 'the element sets are not loaded, so no satellite will be checked (see Satellites above).'}
        </p>
        {error ? (
          <p role="alert" data-exclusion-error className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm text-destructive">
            {error.field ? 'The check was not run. The problem is in the field marked below; its message is under it.' : error.message}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <button type="submit" className={button} disabled={status === 'running'}>{status === 'running' ? 'Checking…' : 'Check against ordinary explanations'}</button>
          <button type="button" className={button} onClick={clear}>Clear everything</button>
        </div>
      </form>
      {run ? <Result run={run} onDownload={download} /> : null}
    </section>
  );
}
