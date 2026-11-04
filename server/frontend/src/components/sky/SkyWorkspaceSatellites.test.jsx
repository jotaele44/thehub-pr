import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import elementsText from '@/sky/fixtures/satellite-elements.json?raw';
import reference from '@/sky/fixtures/satelliteReference.json';
import { loadSatelliteElements } from '@/sky/satelliteElements';
import { gpUrl } from '@/sky/satellites';
import { loadSpaceWeather } from '@/sky/spaceWeather';
import SkyWorkspace from './SkyWorkspace';

vi.mock('@/sky/spaceWeather', async (importOriginal) => ({ ...(await importOriginal()), loadSpaceWeather: vi.fn() }));
vi.mock('@/sky/satelliteElements', async (importOriginal) => ({ ...(await importOriginal()), loadSatelliteElements: vi.fn() }));

// All three objects are answered with their real CelesTrak records (src/sky/fixtures/satellite-elements.json).
const frozen = JSON.parse(elementsText).items;
const sanJuan = reference.satellites.ISS.observers['San Juan'];
const RETRIEVED = new Date('2026-11-04T07:00:00Z');
const respond = (payload) => ({ ok: true, status: 200, json: async () => payload });
const answers = {
  [gpUrl(25544)]: () => respond(frozen.ISS.payload),
  [gpUrl(20580)]: () => respond(frozen.HST.payload),
  [gpUrl(48274)]: () => respond(frozen.CSS.payload),
};
async function elements(overrides = {}) {
  const { loadSatelliteElements: actual } = await vi.importActual('@/sky/satelliteElements');
  return actual({ fetchImpl: async (url) => ({ ...answers, ...overrides })[url](), now: RETRIEVED });
}

function renderSky(search) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/skywatcher?view=sky${search}`]}><SkyWorkspace /></MemoryRouter>
    </QueryClientProvider>,
  );
}
const number = (element) => Number.parseFloat(element.textContent.replace('−', '-').replace(/,/g, ''));
const card = (container, id) => waitFor(() => { const el = container.querySelector(`[data-sat="${id}"]`); expect(el, id).toBeTruthy(); return el; });
const secondOfDay = (isoOrText) => {
  const [h, m, s] = /(\d{2}):(\d{2}):(\d{2})/.exec(isoOrText).slice(1).map(Number);
  return h * 3600 + m * 60 + s;
};

beforeEach(async () => {
  loadSpaceWeather.mockReset();
  loadSpaceWeather.mockRejectedValue(new Error('offline'));
  loadSatelliteElements.mockReset();
  loadSatelliteElements.mockResolvedValue(await elements());
});
afterEach(() => { vi.useRealTimers(); });

describe('Satellites panel', () => {
  it('lists the three objects with their identity, element epoch, age and confidence, and says what it is not', async () => {
    const { container } = renderSky('&t=2026-11-03T18:10:00Z');
    const iss = await card(container, 'ISS');
    expect(within(iss).getByTestId('sat-state')).toHaveTextContent('LOADED');
    expect(iss).toHaveTextContent('NORAD 25544');
    expect(within(iss).getByTestId('sat-identity')).toHaveTextContent('ISS (ZARYA) · international designator 1998-067A');
    expect(within(iss).getByTestId('sat-epoch')).toHaveTextContent('2026-11-02T18:09:49');
    expect(within(iss).getByTestId('sat-epoch')).toHaveTextContent('1.0 days after the element epoch');
    expect(within(iss).getByTestId('sat-confidence')).toHaveTextContent('Normal confidence');
    for (const id of ['HST', 'CSS']) expect(container.querySelector(`[data-sat="${id}"] [data-testid="sat-state"]`)).toHaveTextContent('LOADED');
    expect(container.querySelector('[data-sat="CSS"]')).toHaveTextContent('Tianhe core module');
    const note = container.querySelector('[data-sat-note]');
    expect(note).toHaveTextContent('3 objects are checked (ISS, HST, CSS), not all satellites');
    expect(note).toHaveTextContent('cannot reproduce a past event');
    expect(note).toHaveTextContent('brightness is not estimated');
    expect(note).toHaveTextContent('not an observation or a finding');
    expect(container.querySelector('[data-sat-summary]')).toHaveTextContent('3 of 3 element sets loaded, retrieved 2026-11-04T07:00:00Z UTC');
  });

  it.each([
    { label: 'in the Earth\'s shadow', look: sanJuan.looks[1] },
    { label: 'sunlit', look: sanJuan.looks.find((candidate) => candidate.sunlit && candidate.elevation > 20) },
  ])('puts the station where the independent reference puts it, $label', async ({ look }) => {
    const { container } = renderSky(`&t=${look.time}`);
    const iss = await card(container, 'ISS');
    expect(Math.abs(number(within(iss).getByTestId('sat-elevation')) - look.elevation)).toBeLessThan(0.08);
    expect(Math.abs(number(within(iss).getByTestId('sat-azimuth')) - look.azimuth)).toBeLessThan(0.08);
    expect(Math.abs(number(within(iss).getByTestId('sat-range')) - look.range_km)).toBeLessThan(1);
    expect(within(iss).getByTestId('sat-position')).toHaveTextContent('Above the horizon');
    expect(within(iss).getByTestId('sat-lighting')).toHaveTextContent(look.sunlit ? 'Sunlit' : 'In the Earth\'s shadow');
  });

  it('lists the passes in the next 24 hours as the reference has them, with the time at the observer\'s offset and in UTC', async () => {
    const start = Date.parse('2026-11-03T18:10:00Z');
    const expected = sanJuan.passes.filter((pass) => Date.parse(pass.aos) < start + 86400e3 && Date.parse(pass.los) > start);
    expect(expected).toHaveLength(4);
    const { container } = renderSky('&t=2026-11-03T18:10:00Z');
    const iss = await card(container, 'ISS');
    const rows = [...iss.querySelectorAll('[data-sat-pass]')];
    expect(rows).toHaveLength(expected.length);
    rows.forEach((row, index) => {
      const pass = expected[index];
      const cells = row.querySelectorAll('td');
      const [rise, , set, length] = [...cells].map((cell) => cell.textContent);
      // "19:36:47 UTC-4 (23:36:47 UTC)": the local clock is UTC-4, the UTC clock is the reference's.
      expect(Math.abs(secondOfDay(/\((.*?) UTC\)/.exec(rise)[1]) - secondOfDay(pass.aos.slice(11, 19)))).toBeLessThanOrEqual(2);
      expect(Math.abs(secondOfDay(/\((.*?) UTC\)/.exec(set)[1]) - secondOfDay(pass.los.slice(11, 19)))).toBeLessThanOrEqual(2);
      expect(rise).toContain('UTC-4');
      expect(Math.abs(secondOfDay(rise) - ((secondOfDay(pass.aos.slice(11, 19)) - 4 * 3600 + 86400) % 86400))).toBeLessThanOrEqual(2);
      expect(Math.abs(number(within(row).getByTestId('sat-max-elevation')) - pass.max_elevation)).toBeLessThan(0.08);
      const [minutes, seconds] = /(\d+) min (\d{2}) s/.exec(length).slice(1).map(Number);
      expect(Math.abs(minutes * 60 + seconds - pass.duration_seconds)).toBeLessThanOrEqual(2);
    });
    expect(iss.querySelector('table caption')).toHaveTextContent('Passes above 10° in the 24 hours from the chosen instant (4)');
  });

  it('calls a pass a visible-pass candidate only when the station is lit and the sky is dark, and says why not otherwise', async () => {
    const { container } = renderSky('&t=2026-11-03T18:10:00Z');
    const iss = await card(container, 'ISS');
    const visibility = [...iss.querySelectorAll('[data-sat-pass] [data-testid="sat-visibility"]')].map((cell) => cell.textContent);
    // 23:36Z and 01:13Z: in shadow for the whole pass. 09:27Z: lit, Sun 13 degrees down. 11:05Z: lit, but the Sun is up.
    expect(visibility[0]).toContain('Not a visible-pass candidate');
    expect(visibility[0]).toContain('in the Earth\'s shadow for the whole pass');
    expect(visibility[1]).toContain('in the Earth\'s shadow for the whole pass');
    expect(visibility[2]).toContain('Visible-pass candidate (geometry only; brightness not estimated)');
    expect(visibility[2]).toMatch(/between \d{2}:\d{2}:\d{2} UTC \(\d{2}:\d{2}:\d{2} UTC\) and /);
    expect(visibility[3]).toContain('Not a visible-pass candidate');
    expect(visibility[3]).toContain('The sky is too bright');
  });

  it('draws the satellites on the chart with a shape of their own, filled when sunlit and hollow in shadow, and names every one', async () => {
    const lit = sanJuan.looks.find((look) => look.sunlit && look.elevation > 20);
    const { container } = renderSky(`&t=${lit.time}`);
    await card(container, 'ISS');
    const glyph = await waitFor(() => { const el = container.querySelector('[data-sky-glyph="ISS"]'); expect(el).toBeTruthy(); return el; });
    expect(glyph).toHaveAttribute('data-sky-kind', 'satellite');
    expect(glyph).toHaveAttribute('data-sunlit', 'true');
    expect(glyph.querySelector('rect')).toHaveAttribute('fill', 'currentColor');
    const drawn = [...container.querySelectorAll('[data-sky-glyph]')].map((el) => el.getAttribute('data-sky-glyph'));
    const below = container.querySelector('[data-sky-below]').textContent;
    for (const id of ['ISS', 'HST', 'CSS']) expect(drawn.includes(id) || below.includes(id), id).toBe(true);
    expect(container.querySelector('svg[data-sky-chart]').getAttribute('aria-label')).toMatch(/of 7 bodies are above the horizon\. \d of 3 satellites are above the horizon\./);
    expect(container.querySelector('[data-sky-satellite-key]')).toHaveTextContent('not a brightness');
  });

  it('draws a satellite in the Earth\'s shadow hollow', async () => {
    const dark = sanJuan.looks[1];
    const { container } = renderSky(`&t=${dark.time}`);
    await card(container, 'ISS');
    const glyph = await waitFor(() => { const el = container.querySelector('[data-sky-glyph="ISS"]'); expect(el).toBeTruthy(); return el; });
    expect(glyph).toHaveAttribute('data-sunlit', 'false');
    expect(glyph.querySelector('rect')).toHaveAttribute('fill', 'none');
  });

  it('shows and hides the track of a pass across the sky', async () => {
    const { container } = renderSky('&t=2026-11-03T18:10:00Z');
    const iss = await card(container, 'ISS');
    expect(container.querySelector('[data-sky-track]')).toBeNull();
    const show = within(iss).getAllByRole('button', { name: /^Show the ISS track for the pass rising at 2026-11-04T09:27:5/ })[0];
    expect(show).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(show);
    const track = await waitFor(() => { const el = container.querySelector('[data-sky-track="ISS"]'); expect(el).toBeTruthy(); return el; });
    expect(track.querySelector('path').getAttribute('d')).toMatch(/^M[-\d.]+,[-\d.]+( L[-\d.]+,[-\d.]+){5,}$/);
    expect(container.querySelector('[data-sky-track-key]')).toHaveTextContent('Hollow dot: rise. Filled dot: set.');
    const hide = within(iss).getByRole('button', { name: /^Hide the ISS track/ });
    expect(hide).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(hide);
    await waitFor(() => expect(container.querySelector('[data-sky-track]')).toBeNull());
    expect(container.querySelector('[data-sky-track-key]')).toBeNull();
  });

  it('drops a shown track when the observer changes, rather than drawing it for a place it was not computed for', async () => {
    const { container } = renderSky('&t=2026-11-03T18:10:00Z');
    const iss = await card(container, 'ISS');
    fireEvent.click(within(iss).getAllByRole('button', { name: /^Show the ISS track/ })[0]);
    await waitFor(() => expect(container.querySelector('[data-sky-track="ISS"]')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Latitude (°N)'), { target: { value: '-33.8688' } });
    fireEvent.change(screen.getByLabelText('Longitude (°E)'), { target: { value: '151.2093' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply observer' }));
    await waitFor(() => expect(container.querySelector('[data-sky-default-observer]')).toBeNull());
    expect(container.querySelector('[data-sky-track]')).toBeNull();
  });

  it('lists an object whose elements did not load as failed, with the reason, and places nothing for it', async () => {
    loadSatelliteElements.mockResolvedValue(await elements({ [gpUrl(20580)]: () => ({ ok: false, status: 503, json: async () => ({}) }) }));
    const { container } = renderSky(`&t=${sanJuan.looks[1].time}`);
    const hubble = await card(container, 'HST');
    expect(within(hubble).getByTestId('sat-state')).toHaveTextContent('FAILED');
    expect(within(hubble).getByTestId('sat-error')).toHaveTextContent('Unavailable: CelesTrak answered HTTP 503');
    expect(hubble).toHaveTextContent('NORAD 20580');
    expect(within(hubble).queryByTestId('sat-position')).toBeNull();
    expect(hubble.querySelector('table')).toBeNull();
    expect(container.querySelector('[data-sky-glyph="HST"]')).toBeNull();
    expect(container.querySelector('[data-sky-below]').textContent).not.toContain('HST');
    expect(container.querySelector('[data-sat-summary]')).toHaveTextContent('2 of 3 element sets loaded');
    expect(container.querySelector('[data-sat="ISS"] [data-testid="sat-state"]')).toHaveTextContent('LOADED');
  });

  it('gives no position and no pass, with the reason, when the elements are too far from the chosen time', async () => {
    const { container } = renderSky('&t=2026-12-25T00:00:00Z');
    const iss = await card(container, 'ISS');
    expect(within(iss).getByTestId('sat-position')).toHaveTextContent(/No position: .*14 days/);
    expect(within(iss).getByTestId('sat-confidence')).toHaveTextContent('No prediction: more than 14 days');
    expect(within(iss).getByTestId('sat-passes-none')).toHaveTextContent(/No passes shown: .*14 days/);
    expect(container.querySelector('[data-sky-glyph="ISS"]')).toBeNull();
    expect(container.querySelector('[data-sky-below]').textContent).not.toContain('ISS');
  });

  it('says so when the whole request fails', async () => {
    loadSatelliteElements.mockReset();
    loadSatelliteElements.mockRejectedValue(new Error('boom'));
    renderSky('&t=2026-11-03T18:10:00Z');
    expect(await screen.findByText(/Satellite elements could not be read: boom/)).toBeInTheDocument();
  });

  it('asks CelesTrak once, and refuses a reload inside a minute of the last read', async () => {
    const { container } = renderSky('&t=2026-11-03T18:10:00Z');
    await card(container, 'ISS');
    expect(loadSatelliteElements).toHaveBeenCalledTimes(1);
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(RETRIEVED.getTime() + 30000));
    fireEvent.click(screen.getByRole('button', { name: 'Reload satellite elements' }));
    expect(container.querySelector('[data-sat-reload-note]')).toHaveTextContent('ask again after 2026-11-04T07:01:00Z UTC');
    expect(loadSatelliteElements).toHaveBeenCalledTimes(1);
    vi.setSystemTime(new Date(RETRIEVED.getTime() + 90000));
    fireEvent.click(screen.getByRole('button', { name: 'Reload satellite elements' }));
    await waitFor(() => expect(loadSatelliteElements).toHaveBeenCalledTimes(2));
    expect(container.querySelector('[data-sat-reload-note]')).toBeNull();
  });

  it('does not change what the Sky workspace shows when the satellites are unavailable', async () => {
    loadSatelliteElements.mockResolvedValue(await elements({
      [gpUrl(25544)]: () => ({ ok: false, status: 503, json: async () => ({}) }),
      [gpUrl(20580)]: () => ({ ok: false, status: 503, json: async () => ({}) }),
      [gpUrl(48274)]: () => ({ ok: false, status: 503, json: async () => ({}) }),
    }));
    const { container } = renderSky('&t=2026-10-16T00:30:00Z');
    await card(container, 'ISS');
    expect(container.querySelector('svg[data-sky-chart]').getAttribute('aria-label')).toMatch(/of 7 bodies are above the horizon\.$/);
    expect(container.querySelector('[data-sky-satellite-key]')).toBeNull();
    expect(container.querySelector('[data-sky-sun]')).toBeTruthy();
  });

  it('is accessible, with a track shown', async () => {
    const { container } = renderSky('&t=2026-11-03T18:10:00Z');
    const iss = await card(container, 'ISS');
    fireEvent.click(within(iss).getAllByRole('button', { name: /^Show the ISS track/ })[0]);
    await waitFor(() => expect(container.querySelector('[data-sky-track="ISS"]')).toBeTruthy());
    expect(await axe(container)).toHaveNoViolations();
  });
});
