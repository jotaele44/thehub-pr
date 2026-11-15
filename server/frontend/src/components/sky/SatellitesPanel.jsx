import React from 'react';
import { ELEMENT_POLICY, SATELLITES, SATELLITE_CONVENTIONS, SATELLITE_ENGINE } from '@/sky/satellites';
import { PASS_HOURS, PASS_MIN_ELEVATION } from '@/sky/satelliteView';
import { button, degrees, duration, isoOf, preciseEventText } from './format';

// The satellites panel (TWIN-042..046, 054, 055, 116): where the International Space Station, Hubble and the Chinese
// space station are for the observer and instant above, and their passes in the next 24 hours. Orbits are propagated
// with SGP4 from CelesTrak's current element sets. This is geometry: it does not estimate brightness, and it is
// not an observation, a sighting or a finding.
const CONFIDENCE_TEXT = Object.freeze({
  NORMAL: `Normal confidence: within ${ELEMENT_POLICY.normalDays} days of the element epoch`,
  LOWER: `Lower confidence: ${ELEMENT_POLICY.normalDays} to ${ELEMENT_POLICY.lowerDays} days from the element epoch`,
  LOW: `Low confidence: ${ELEMENT_POLICY.lowerDays} to ${ELEMENT_POLICY.refuseDays} days from the element epoch`,
  NONE: `No prediction: more than ${ELEMENT_POLICY.refuseDays} days from the element epoch`,
});

const POSITION_TEXT = Object.freeze({ ABOVE_HORIZON: 'Above the horizon', BELOW_HORIZON: 'Below the horizon' });
const SATELLITE_NOTE = Object.fromEntries(SATELLITES.filter((s) => s.note).map((s) => [s.id, s.note]));

const ageText = (age) => `${age.days.toFixed(1)} days ${age.signedDays >= 0 ? 'after' : 'before'} the element epoch`;

function Fact({ label, testId, children }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd data-testid={testId}>{children}</dd>
    </>
  );
}

function Current({ item }) {
  if (!item.look) {
    return <p data-testid="sat-position">No position: {item.lookError}</p>;
  }
  const { look } = item;
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
      <Fact label="Position" testId="sat-position">{POSITION_TEXT[item.position]}</Fact>
      <Fact label="Elevation" testId="sat-elevation">{degrees(look.elevation)}</Fact>
      <Fact label="Azimuth" testId="sat-azimuth">{degrees(look.azimuth)}</Fact>
      <Fact label="Range" testId="sat-range">{Math.round(look.rangeKm).toLocaleString('en-US')} km</Fact>
      <Fact label="Lighting" testId="sat-lighting">{look.sunlit ? 'Sunlit' : 'In the Earth\'s shadow (cylindrical model)'}</Fact>
    </dl>
  );
}

function PassTable({ item, result, tz, shown, onShowTrack }) {
  if (!result) return null;
  if (!result.ok) return <p data-testid="sat-passes-none">No passes shown: {result.message}</p>;
  if (!result.passes.length) {
    return <p data-testid="sat-passes-none">No pass above {result.minElevation}° in the {PASS_HOURS} hours from the chosen instant.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table data-testid="sat-passes" className="w-full min-w-[40rem] border-collapse text-left text-xs">
        <caption className="mb-1 text-left text-xs text-muted-foreground">
          Passes above {result.minElevation}° in the {PASS_HOURS} hours from the chosen instant ({result.passes.length}).
        </caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className="py-1 pr-2 font-semibold">Rise</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Highest</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Set</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Duration</th>
            <th scope="col" className="py-1 pr-2 font-semibold">Visibility</th>
            <th scope="col" className="py-1 font-semibold">Track</th>
          </tr>
        </thead>
        <tbody>
          {result.passes.map((pass) => {
            const key = pass.aos.toISOString();
            const isShown = shown?.id === item.id && shown.pass.aos.getTime() === pass.aos.getTime();
            return (
              <tr key={key} data-sat-pass={key} className="border-b border-border align-top">
                <td className="py-1 pr-2">{preciseEventText(pass.aos, tz)}<br />azimuth {degrees(pass.aosAzimuth)}</td>
                <td className="py-1 pr-2">{preciseEventText(pass.tca, tz)}<br /><span data-testid="sat-max-elevation">{degrees(pass.maxElevation)}</span> at azimuth {degrees(pass.tcaAzimuth)}</td>
                <td className="py-1 pr-2">{preciseEventText(pass.los, tz)}<br />azimuth {degrees(pass.losAzimuth)}</td>
                <td className="py-1 pr-2">{duration(pass.durationSeconds)}</td>
                <td className="py-1 pr-2" data-testid="sat-visibility">
                  <strong>{pass.visibility.label}</strong>
                  {pass.visibility.candidate
                    ? <><br />between {preciseEventText(pass.visibility.from, 0)} and {preciseEventText(pass.visibility.to, 0)}</>
                    : <><br />{pass.visibility.reason}</>}
                  {pass.confidence !== 'NORMAL' ? <><br />{CONFIDENCE_TEXT[pass.confidence]}</> : null}
                </td>
                <td className="py-1">
                  <button
                    type="button" className={button} aria-pressed={isShown}
                    aria-label={`${isShown ? 'Hide' : 'Show'} the ${item.id} track for the pass rising at ${isoOf(pass.aos)}`}
                    onClick={() => onShowTrack(isShown ? null : { id: item.id, pass })}
                  >
                    {isShown ? 'Hide track' : 'Show track'}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SatelliteCard({ item, result, tz, shown, onShowTrack }) {
  const failed = item.state === 'FAILED';
  return (
    <section data-sat={item.id} className="space-y-2 rounded-xl border border-border p-3 text-sm">
      <h4 className="font-semibold">{item.label}</h4>
      <p>
        <span data-testid="sat-state" className="rounded border border-border px-1.5 py-0.5 text-xs font-semibold">{item.state}</span>
        <span className="ml-2 text-muted-foreground">NORAD {item.noradId}</span>
      </p>
      {failed ? <p data-testid="sat-error">Unavailable: {item.error}. No position or pass is shown for this object.</p> : (
        <>
          <p className="text-xs text-muted-foreground" data-testid="sat-identity">
            {item.name}{item.element.objectId ? ` · international designator ${item.element.objectId}` : ''}
          </p>
          {SATELLITE_NOTE[item.id] ? <p className="text-xs text-muted-foreground">{SATELLITE_NOTE[item.id]}</p> : null}
          <p className="text-xs" data-testid="sat-epoch">
            Element epoch <span className="font-mono">{isoOf(item.element.epoch)}</span> UTC, {ageText(item.age)}.{' '}
            <strong data-testid="sat-confidence">{CONFIDENCE_TEXT[item.age.confidence]}.</strong>
          </p>
          <Current item={item} />
          <PassTable item={item} result={result} tz={tz} shown={shown} onShowTrack={onShowTrack} />
        </>
      )}
    </section>
  );
}

export default function SatellitesPanel({ status, snapshot, passes, tz, shown, onShowTrack, onReload, reloadNote }) {
  return (
    <section className="space-y-3" aria-labelledby="sky-sat" data-sky-satellites>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="sky-sat" className="text-base font-semibold">Satellites</h3>
        <button type="button" className={button} onClick={onReload} disabled={status.isFetching}>Reload satellite elements</button>
      </div>
      <p data-sat-note className="text-xs text-muted-foreground">
        {SATELLITES.length} objects are checked ({SATELLITES.map((s) => s.id).join(', ')}), not all satellites. Their positions are computed here with
        SGP4 ({SATELLITE_ENGINE.name} {SATELLITE_ENGINE.version}) from CelesTrak's current element sets, which are read once and kept for two hours.
        The elements are current, so this cannot reproduce a past event, and a time more than {ELEMENT_POLICY.refuseDays} days from an element epoch
        is refused. It is geometry only: brightness is not estimated. It is context for ruling out ordinary explanations, not an observation or a finding.
      </p>
      {status.isLoading ? <p role="status" className="text-sm text-muted-foreground">Reading CelesTrak…</p> : null}
      {status.isError ? <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm text-destructive">Satellite elements could not be read: {status.error?.message}</p> : null}
      {reloadNote ? <p role="status" data-sat-reload-note className="rounded-md border border-border bg-muted/40 p-2 text-xs">{reloadNote}</p> : null}
      {snapshot ? (
        <>
          <p data-sat-summary className="text-xs text-muted-foreground">
            {snapshot.loaded} of {snapshot.requested} element sets loaded, retrieved {isoOf(snapshot.retrievedAt)} UTC from CelesTrak (GP, JSON). An object whose
            elements did not load is listed as failed, never placed or assumed.
          </p>
          <div className="space-y-3">
            {snapshot.items.map((item) => (
              <SatelliteCard key={item.id} item={item} result={passes?.[item.id]} tz={tz} shown={shown} onShowTrack={onShowTrack} />
            ))}
          </div>
          <section data-sat-conventions className="rounded-md border border-border p-3 text-xs text-muted-foreground">
            <h4 className="mb-1 text-sm font-semibold text-foreground">Satellite conventions</h4>
            <ul className="list-disc space-y-0.5 pl-4">
              {Object.entries(SATELLITE_CONVENTIONS).map(([key, text]) => <li key={key}>{text}</li>)}
              <li>Passes use a minimum elevation of {PASS_MIN_ELEVATION}° above the geometric horizon.</li>
            </ul>
          </section>
        </>
      ) : null}
    </section>
  );
}
