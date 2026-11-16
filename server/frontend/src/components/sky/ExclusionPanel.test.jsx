import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import elementsText from '@/sky/fixtures/satellite-elements.json?raw';
import aircraftReference from '@/sky/exclusion/fixtures/aircraftReference.json';
import { aircraftLookAt } from '@/sky/exclusion/aircraftExclusion';
import { parseTrackCsv } from '@/sky/exclusion/aircraftTracks';
import { loadSatelliteElements } from '@/sky/satelliteElements';
import { gpUrl } from '@/sky/satellites';
import ExclusionPanel from './ExclusionPanel';

// The terrain reader is the one network dependency of the panel; it is replaced here and exercised live in liveProviders.test.js.
const terrainFromCudem = vi.fn();
vi.mock('@/sky/exclusion/terrain', async (importOriginal) => ({ ...(await importOriginal()), terrainFromCudem: (...args) => terrainFromCudem(...args) }));

const frozen = JSON.parse(elementsText).items;
const respond = (payload) => ({ ok: true, status: 200, json: async () => payload });
const answers = { [gpUrl(25544)]: frozen.ISS.payload, [gpUrl(20580)]: frozen.HST.payload, [gpUrl(48274)]: frozen.CSS.payload };
const loaded = () => loadSatelliteElements({ fetchImpl: async (url) => respond(answers[url]), now: new Date('2026-11-04T08:00:00Z') });
const EPOCH = Date.parse(aircraftReference.generated_by.epoch);
const OBSERVER = aircraftReference.observer;
const csvText = ['time,lat,lon,altitude,id', ...Object.values(aircraftReference.tracks).flatMap((t) => t.rows.map((r) => `${r.time},${r.lat},${r.lon},${r.altitude_m},${t.id}`))].join('\n');
const trackA = () => parseTrackCsv(csvText, { source: 'x', altitudeReference: 'ELLIPSOID', altitudeUnits: 'm' }).tracks.find((t) => t.id === 'A');
const workspace = { observer: { lat: OBSERVER.lat, lon: OBSERVER.lon, elevation: 30, tzHours: -4 }, instant: new Date(EPOCH + 300000) };

const fill = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
function fillObservation({ time = new Date(EPOCH + 300000).toISOString(), azimuth = '200', elevation = '60', tolerance = '0.5', uncertainty = '5' } = {}) {
  fill('Reported at (UTC)', time);
  fill(/Uncertainty in that time/, uncertainty);
  fill(/Observer latitude/, String(OBSERVER.lat));
  fill(/Observer longitude/, String(OBSERVER.lon));
  fill(/Height above the WGS84 ellipsoid/, String(OBSERVER.height));
  fill('Sight line azimuth (°)', azimuth);
  fill('Sight line elevation (°)', elevation);
  fireEvent.change(screen.getByLabelText('Azimuth reference'), { target: { value: 'TRUE' } });
  fill(/Tolerance/, tolerance);
}
async function uploadTracks(text = csvText, name = 'tracks.csv') {
  const file = new File([text], name, { type: 'text/csv' });
  fireEvent.change(screen.getByLabelText('Tracks file'), { target: { files: [file] } });
  await waitFor(() => expect(document.querySelector('[data-exclusion-file]')).toHaveTextContent(name));
}
function declareTracks({ source = 'reference tracks', reference = 'ELLIPSOID', unit = 'm' } = {}) {
  fill('Where the tracks came from', source);
  fireEvent.change(screen.getByLabelText('Altitude reference'), { target: { value: reference } });
  fireEvent.change(screen.getByLabelText('Altitude unit'), { target: { value: unit } });
}
const run = () => fireEvent.click(screen.getByRole('button', { name: 'Check against ordinary explanations' }));

let satelliteData;
beforeEach(async () => {
  terrainFromCudem.mockReset();
  satelliteData = await loaded();
});
afterEach(() => { vi.restoreAllMocks(); });

const renderPanel = (props = {}) => render(<ExclusionPanel {...workspace} satelliteData={satelliteData} {...props} />);

describe('the form', () => {
  it('says what it is and is not, and that nothing is stored or sent, before anything is entered', () => {
    const { container } = renderPanel();
    const note = container.querySelector('[data-exclusion-note]');
    expect(note).toHaveTextContent('a geometric coincidence, not an identification');
    expect(note).toHaveTextContent('Absence of an identified ordinary explanation is not evidence of an extraordinary one.');
    expect(note).toHaveTextContent('Nothing you type or load here is stored, sent anywhere or made a case');
    expect(note).toHaveTextContent('not certified and is not a finding');
    expect(container.querySelector('[data-exclusion-satellites]')).toHaveTextContent('3 of 3 element sets loaded above');
    expect(container.querySelector('[data-exclusion-satellites]')).toHaveTextContent('not all satellites');
    expect(screen.queryByTestId('conclusion-headline')).toBeNull();
  });

  it('starts from the workspace\'s observer and time on request, without copying the elevation as an ellipsoidal height', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Start from the observer and time above' }));
    expect(screen.getByLabelText('Reported at (UTC)')).toHaveValue(new Date(EPOCH + 300000).toISOString().replace('.000Z', 'Z'));
    expect(screen.getByLabelText(/Observer latitude/)).toHaveValue(String(OBSERVER.lat));
    expect(screen.getByLabelText(/Height above the WGS84 ellipsoid/)).toHaveValue('');
  });

  it('refuses to run with the time missing, names the field, marks it invalid and moves focus to it', async () => {
    renderPanel();
    run();
    const alert = await screen.findByText(/The time \(UTC\) is required/, { selector: 'p' });
    expect(alert).toBeInTheDocument();
    const time = screen.getByLabelText('Reported at (UTC)');
    expect(time).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(time).toHaveFocus());
    expect(screen.queryByTestId('conclusion-headline')).toBeNull();
  });

  it('does not assume the azimuth reference, and asks for the magnetic declination when the bearing is magnetic', async () => {
    renderPanel();
    fillObservation();
    fireEvent.change(screen.getByLabelText('Azimuth reference'), { target: { value: '' } });
    run();
    expect(await screen.findByText(/Say whether the azimuth is from true north or from magnetic north/, { selector: 'p' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Azimuth reference'), { target: { value: 'MAGNETIC' } });
    expect(screen.getByLabelText(/Magnetic declination/)).toBeInTheDocument();
    run();
    expect(await screen.findByText('Magnetic declination is required.', { selector: 'p' })).toBeInTheDocument();
  });

  it('switches between a tolerance and a camera field of view', () => {
    renderPanel();
    expect(screen.getByLabelText(/Tolerance/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('A camera field of view'));
    expect(screen.queryByLabelText(/Tolerance/)).toBeNull();
    for (const name of [/Horizontal field of view/, /Vertical field of view/, /Roll/]) expect(screen.getByLabelText(name)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('The sight line moved during the observation'));
    for (const name of ['End azimuth (°)', 'End elevation (°)', 'Ended at (UTC)']) expect(screen.getByLabelText(name)).toBeInTheDocument();
  });

  it('says so when the satellite elements are not loaded', () => {
    const { container } = renderPanel({ satelliteData: null });
    expect(container.querySelector('[data-exclusion-satellites]')).toHaveTextContent('the element sets are not loaded, so no satellite will be checked');
  });
});

describe('a run with nothing in the sight line', () => {
  it('says NO ORDINARY CANDIDATE IDENTIFIED with what was checked, the reminder and NOT_CERTIFIED', async () => {
    const { container } = renderPanel();
    fillObservation();
    await uploadTracks();
    declareTracks();
    run();
    expect(await screen.findByTestId('conclusion-headline')).toHaveTextContent('NO ORDINARY CANDIDATE IDENTIFIED');
    expect(screen.getByTestId('conclusion-text')).toHaveTextContent('3 of 3 satellites (ISS, HST, CSS)');
    expect(screen.getByTestId('conclusion-text')).toHaveTextContent('2 of 2 supplied aircraft tracks');
    expect(screen.getByTestId('conclusion-text')).toHaveTextContent('Absence of an identified ordinary explanation is not evidence of an extraordinary one.');
    expect(screen.getByTestId('certification')).toHaveTextContent('NOT_CERTIFIED');
    expect(screen.getByTestId('no-candidates')).toBeInTheDocument();
    expect(container.querySelector('[data-exclusion-conclusion="NO_ORDINARY_CANDIDATE_IDENTIFIED"]')).toBeTruthy();
    // the tracks, in the Skywatcher vocabulary, with their coverage
    const quality = screen.getByTestId('track-quality');
    expect(within(quality).getByText('continuous')).toBeInTheDocument();
    expect(quality.querySelector('[data-track="B"]')).toHaveTextContent('gapped');
    expect(quality.querySelector('[data-track="B"]')).toHaveTextContent('1');
    // terrain was not asked for, and the receipt says it was not checked
    expect(container.querySelector('[data-exclusion-not-checked]')).toHaveTextContent('The terrain option was not turned on.');
    expect(container.querySelector('[data-exclusion-blind-spots]')).toHaveTextContent('What this check can never rule in or out (8)');
    expect(screen.getByTestId('digest').textContent).toMatch(/^[0-9a-f]{64}$/);
  });

  it('draws the sky at the reported instant with the sight line, and describes it in words', async () => {
    const { container } = renderPanel();
    fillObservation();
    run();
    await screen.findByTestId('conclusion-headline');
    const svg = container.querySelector('[data-exclusion-chart] svg');
    expect(svg).toHaveAttribute('role', 'img');
    expect(svg.getAttribute('aria-label')).toMatch(/Sky at the reported instant, .*UTC: north at the top, east at the left, zenith at the centre/);
    expect(svg.getAttribute('aria-label')).toMatch(/The reported sight line is at azimuth 200\.0°, elevation 60\.0°/);
    expect(svg.querySelector('[data-exclusion-sightline="cone"] [data-exclusion-outline="start"]')).toBeTruthy();
    expect(svg.querySelector('[data-exclusion-sightline="cone"] [data-exclusion-centre]')).toBeTruthy();
    expect(svg.querySelectorAll('[data-exclusion-object]').length).toBeGreaterThan(10);
    expect(container.querySelector('[data-exclusion-chart-key]')).toHaveTextContent('Four ticks mark the centre of the reported sight line, and the dashed outline is its tolerance');
    expect(container.querySelector('[data-exclusion-chart-key]')).toHaveTextContent('only candidates and the nearest Sun, Moon, planets, satellites and aircraft are named');
    expect(container.querySelector('[data-exclusion-below]')).toHaveTextContent('Below the horizon, not drawn');
  });

  it('lists what was not checked and why when no tracks and no satellites are available', async () => {
    const { container } = renderPanel({ satelliteData: null });
    fillObservation();
    run();
    await screen.findByTestId('conclusion-headline');
    const list = container.querySelector('[data-exclusion-not-checked]');
    expect(list).toHaveTextContent('The satellite element sets are not loaded (see Satellites above).');
    expect(list).toHaveTextContent('No aircraft tracks were supplied.');
    expect(screen.getByTestId('conclusion-text')).toHaveTextContent('3 items were not checked or only partly checked');
  });
});

describe('a run with a candidate in the sight line', () => {
  it('lists it as a geometric coincidence with its basis, rings it on the chart and never calls it an identification', async () => {
    const look = aircraftLookAt(OBSERVER, trackA(), EPOCH + 124000);
    const { container } = renderPanel();
    fillObservation({ time: new Date(EPOCH + 124000).toISOString(), azimuth: String(look.azimuth), elevation: String(look.elevation), tolerance: '1', uncertainty: '10' });
    await uploadTracks();
    declareTracks();
    run();
    expect(await screen.findByTestId('conclusion-headline')).toHaveTextContent(/^\d+ ORDINARY CANDIDATES? LISTED$/);
    const row = screen.getByTestId('candidates').querySelector('[data-candidate="A"]');
    expect(row).toBeTruthy();
    expect(within(row).getByTestId('candidate-basis')).toHaveTextContent(/OBSERVED|INTERPOLATED/);
    expect(row).toHaveTextContent('not evidence of intent');
    expect(row).toHaveTextContent('aircraft track');
    expect(container.querySelector('[data-exclusion-object="A"][data-candidate="true"]')).toBeTruthy();
    expect(screen.getByTestId('conclusion-text')).toHaveTextContent('geometric coincidence, not an identification');
    expect(container.textContent).not.toMatch(/anomal|UFO|UAP|extraterrestrial|unexplained/i);
  });
});

describe('the tracks file and its declaration', () => {
  it('refuses a file with no declared source, naming the field, and does not run', async () => {
    renderPanel();
    fillObservation();
    await uploadTracks();
    fireEvent.change(screen.getByLabelText('Altitude reference'), { target: { value: 'ELLIPSOID' } });
    fireEvent.change(screen.getByLabelText('Altitude unit'), { target: { value: 'm' } });
    run();
    expect(await screen.findByText(/Say where the tracks came from/, { selector: 'p' })).toBeInTheDocument();
    expect(screen.getByLabelText('Where the tracks came from')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.queryByTestId('conclusion-headline')).toBeNull();
  });

  it('asks for the geoid separation for a height above sea level and for an uncertainty for a barometric altitude', async () => {
    renderPanel();
    fillObservation();
    await uploadTracks();
    declareTracks({ reference: 'MSL', unit: 'ft' });
    run();
    expect(await screen.findByText(/needs the geoid separation at the place/, { selector: 'p' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Altitude reference'), { target: { value: 'BAROMETRIC' } });
    run();
    expect(await screen.findByText(/barometric \(pressure\) altitude is not a geometric height/, { selector: 'p' })).toBeInTheDocument();
  });

  it('shows the reason a file cannot be read, and a file that is too large', async () => {
    renderPanel();
    fillObservation();
    await uploadTracks('time,lat,lon\n1,2,3');
    declareTracks();
    run();
    expect(await screen.findByText(/"altitude" is missing/, { selector: 'p' })).toBeInTheDocument();
    const big = new File(['x'], 'big.csv');
    Object.defineProperty(big, 'size', { value: 9 * 1048576 });
    fireEvent.change(screen.getByLabelText('Tracks file'), { target: { files: [big] } });
    expect(await screen.findByText(/this check takes at most 8 MB/)).toBeInTheDocument();
    expect(document.querySelector('[data-exclusion-file]')).toBeNull();
  });
});

describe('terrain', () => {
  const sea = { datum: 'TEST', label: 'flat sea', heightAt: () => 0, caveats: ['test caveat'], tilesRead: ['a.tif'] };

  it('reads the terrain when asked and uses it', async () => {
    terrainFromCudem.mockResolvedValue(sea);
    const { container } = renderPanel();
    fillObservation();
    fireEvent.click(screen.getByLabelText(/Use the terrain horizon/));
    expect(screen.getByLabelText(/Eye height above the ground/)).toHaveValue('2');
    expect(screen.getByLabelText('Refraction coefficient')).toHaveValue('0.13');
    run();
    await screen.findByTestId('conclusion-headline');
    expect(terrainFromCudem).toHaveBeenCalledTimes(1);
    expect(container.querySelector('[data-exclusion-not-checked]')).not.toHaveTextContent('terrain horizon and line of sight');
    // the horizon is drawn on the chart and described in words; over flat sea there is no band above the horizontal
    expect(container.querySelector('[data-exclusion-chart] [data-exclusion-horizon]')).toBeTruthy();
    expect(container.querySelector('[data-exclusion-chart-key]')).toHaveTextContent('Shaded band: ground that rises above the horizontal (bare earth; there is none here');
    expect(container.querySelector('[data-exclusion-horizon-nodata]')).toBeNull();
  });

  it('goes on without terrain when it cannot be read, and says so', async () => {
    terrainFromCudem.mockRejectedValue(new Error('NOAA did not answer'));
    const { container } = renderPanel();
    fillObservation();
    fireEvent.click(screen.getByLabelText(/Use the terrain horizon/));
    run();
    await screen.findByTestId('conclusion-headline');
    expect(container.querySelector('[data-exclusion-not-checked]')).toHaveTextContent('The terrain could not be used: NOAA did not answer');
  });

  it('refuses a blank terrain option by name', async () => {
    renderPanel();
    fillObservation();
    fireEvent.click(screen.getByLabelText(/Use the terrain horizon/));
    fill('Refraction coefficient', '');
    run();
    expect(await screen.findByText('Refraction coefficient is required.', { selector: 'p' })).toBeInTheDocument();
    expect(terrainFromCudem).not.toHaveBeenCalled();
  });
});

describe('the receipt and the page\'s memory', () => {
  it('downloads the receipt as JSON under its own name, and the digest can be checked from the file', async () => {
    renderPanel();
    fillObservation();
    run();
    await screen.findByTestId('conclusion-headline');
    let blob;
    const created = vi.fn((b) => { blob = b; return 'blob:test'; });
    const revoked = vi.fn();
    Object.defineProperty(URL, 'createObjectURL', { value: created, configurable: true });
    Object.defineProperty(URL, 'revokeObjectURL', { value: revoked, configurable: true });
    const clicked = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function click() { clicked.push({ href: this.href, download: this.download }); });
    fireEvent.click(screen.getByRole('button', { name: 'Download the receipt (JSON)' }));
    expect(created).toHaveBeenCalledTimes(1);
    expect(blob.type).toBe('application/json');
    expect(clicked).toHaveLength(1);
    expect(clicked[0].download).toMatch(/^sky-exclusion-\d{8}T\d{6}Z-[0-9a-f]{12}\.json$/);
    const text = await new Promise((resolve) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.readAsText(blob); });
    const receipt = JSON.parse(text);
    expect(receipt).toMatchObject({ contract: 'sky-exclusion-v1', certification: { status: 'NOT_CERTIFIED' } });
    expect(receipt.contentDigest).toBe(screen.getByTestId('digest').textContent);
    expect(clicked[0].download).toContain(receipt.contentDigest.slice(0, 12));
  });

  it('stores nothing and sends nothing: no storage write, no request, and the tracks file stays in memory', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('no network in this test'));
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    renderPanel();
    fillObservation();
    await uploadTracks();
    declareTracks();
    run();
    await screen.findByTestId('conclusion-headline');
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
    expect(new URLSearchParams(window.location.search).toString()).toBe('');
  });

  it('clears everything on request: the form, the file and the result', async () => {
    renderPanel();
    fillObservation();
    await uploadTracks();
    declareTracks();
    run();
    await screen.findByTestId('conclusion-headline');
    fireEvent.click(screen.getByRole('button', { name: 'Clear everything' }));
    expect(screen.queryByTestId('conclusion-headline')).toBeNull();
    expect(screen.getByLabelText('Reported at (UTC)')).toHaveValue('');
    expect(document.querySelector('[data-exclusion-file]')).toBeNull();
  });
});

describe('accessibility', () => {
  it('has no detectable violations in the empty form or in a result', async () => {
    const { container } = renderPanel();
    expect(await axe(container)).toHaveNoViolations();
    fillObservation();
    await uploadTracks();
    declareTracks();
    run();
    await screen.findByTestId('conclusion-headline');
    expect(await axe(container)).toHaveNoViolations();
  });
});
