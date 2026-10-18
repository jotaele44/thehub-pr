import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, useLocation } from 'react-router-dom';
import reference from '@/sky/referenceEphemerides.json';
import samples from '@/sky/fixtures/swpc-samples.json';
import { loadSpaceWeather } from '@/sky/spaceWeather';
import { twilightClass } from '@/sky/astronomy';
import SkyWorkspace from './SkyWorkspace';

vi.mock('@/sky/spaceWeather', async (importOriginal) => ({ ...(await importOriginal()), loadSpaceWeather: vi.fn() }));

const ANSWER_TIME = new Date('2026-10-18T20:55:00Z');
const respond = (payload) => ({ ok: true, status: 200, json: async () => payload });
const realFetch = async (url) => {
  if (url.endsWith('noaa-planetary-k-index.json')) return respond(samples.kp.payload);
  if (url.endsWith('solar-wind-speed.json')) return respond(samples.solar_wind_speed.payload);
  return respond(samples.mag_field.payload);
};
async function realReadings(overrides = {}) {
  const { loadSpaceWeather: actual } = await vi.importActual('@/sky/spaceWeather');
  return { ...(await actual({ fetchImpl: realFetch, now: ANSWER_TIME })), ...overrides };
}

function Where() {
  const location = useLocation();
  // Decoded, so the assertions read the way the link reads (the browser encodes ":" as %3A).
  return <output data-testid="where">{decodeURIComponent(location.search)}</output>;
}
function renderSky(search = '?view=sky&t=2026-10-16T00:30:00Z') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/skywatcher${search}`]}><SkyWorkspace /><Where /></MemoryRouter>
    </QueryClientProvider>,
  );
}
const number = (element) => Number.parseFloat(element.textContent.replace('−', '-'));
const horizons = (body, observer, time) => reference.horizons.cases.find((c) => c.body === body && c.observer === observer && c.time === time);
// What the readout should show: Horizons' refracted altitude within a degree of the horizon or above, the geometric one below.
const shownAltitude = (c) => (c.airless.alt > -1 ? c.refracted.alt : c.airless.alt);

describe('Sky workspace', () => {
  beforeEach(async () => {
    loadSpaceWeather.mockReset();
    loadSpaceWeather.mockResolvedValue(await realReadings());
  });
  afterEach(() => { vi.useRealTimers(); });

  it('says the observer is a default and never asks the browser for a location', async () => {
    const { container } = renderSky();
    const note = container.querySelector('[data-sky-default-observer]');
    expect(note).toHaveTextContent('San Juan');
    expect(note).toHaveTextContent('18.4663');
    expect(note).toHaveTextContent('does not ask your browser for your location');
    expect(screen.getByLabelText('Latitude (°N)')).toHaveValue('18.4663');
    expect(screen.getByLabelText('UTC offset (hours)')).toHaveValue('-4');
  });

  it('reads the Sun where Horizons puts it, with its daylight class and convention', async () => {
    const { container } = renderSky();
    const ref = horizons('Sun', 'San Juan', '2026-10-16T00:30:00Z');
    const sun = container.querySelector('[data-sky-sun]');
    expect(Math.abs(number(within(sun).getByTestId('altitude')) - shownAltitude(ref))).toBeLessThan(0.06);
    expect(Math.abs(number(within(sun).getByTestId('azimuth')) - ref.refracted.az)).toBeLessThan(0.06);
    expect(container.querySelector('[data-sky-daylight]')).toHaveTextContent(twilightClass(ref.airless.alt).label);
    expect(container.querySelector('[data-sky-conventions]')).toHaveTextContent('standard atmospheric refraction');
    expect(container.querySelector('[data-sky-conventions]')).toHaveTextContent('astronomy-engine 2.1.19');
  });

  it('shows rise, transit and set at the stated UTC offset and in UTC, as USNO lists them for San Juan', async () => {
    const { container } = renderSky('?view=sky&t=2026-10-15T16:00:00Z');
    const day = reference.usno.days.find((d) => d.site === 'San Juan' && d.date === '2026-10-15');
    const sun = container.querySelector('[data-sky-sun]');
    const rise = within(sun).getByTestId('event-rise').textContent;
    const set = within(sun).getByTestId('event-set').textContent;
    const minutes = (text) => { const [h, m] = /(\d{2}):(\d{2})/.exec(text).slice(1).map(Number); return h * 60 + m; };
    expect(Math.abs(minutes(rise) - minutes(day.sun.Rise))).toBeLessThanOrEqual(1);
    expect(Math.abs(minutes(set) - minutes(day.sun.Set))).toBeLessThanOrEqual(1);
    expect(rise).toMatch(/UTC/);
  });

  it('describes the Moon with its phase, illuminated share, magnitude and next quarter', async () => {
    const { container } = renderSky('?view=sky&t=2026-10-16T16:00:00Z');
    const moon = container.querySelector('[data-sky-moon]');
    expect(within(moon).getByTestId('phase-name')).toHaveTextContent('Waxing Crescent');
    const ref = horizons('Moon', 'San Juan', '2026-10-16T00:30:00Z');
    expect(ref.illum_pct).toBeGreaterThan(20);
    expect(number(within(moon).getByTestId('illumination'))).toBeGreaterThan(25);
    expect(within(moon).getByTestId('next-quarter')).toHaveTextContent('First Quarter');
    expect(within(moon).getByTestId('next-quarter')).toHaveTextContent('2026-10-18');
  });

  it('lists the five naked-eye planets, each above or below the horizon', async () => {
    const { container } = renderSky();
    for (const name of ['Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn']) {
      const card = container.querySelector(`[data-sky-planet="${name}"]`);
      expect(card, name).toBeTruthy();
      expect(card.textContent).toMatch(/above the horizon|below the horizon/i);
      expect(within(card).getByTestId('magnitude')).toBeTruthy();
    }
    const ref = horizons('Venus', 'San Juan', '2026-10-16T00:30:00Z');
    expect(Math.abs(number(within(container.querySelector('[data-sky-planet="Venus"]')).getByTestId('altitude')) - shownAltitude(ref))).toBeLessThan(0.06);
  });

  it('says a day with no rise or set has none, rather than leaving a blank', async () => {
    const { container } = renderSky('?view=sky&lat=69.6492&lon=18.9553&tz=0&t=2026-06-21T12:00:00Z');
    expect(within(container.querySelector('[data-sky-sun]')).getByTestId('event-status')).toHaveTextContent('above the horizon all day');
    expect(container.querySelector('[data-sky-daylight]')).toHaveTextContent('Daylight');
  });

  it('draws the chart with the sky as seen looking up, the bodies above the horizon, and lists those below', async () => {
    const { container } = renderSky();
    const chart = container.querySelector('svg[data-sky-chart]');
    expect(chart).toHaveAttribute('role', 'img');
    expect(chart.getAttribute('aria-label')).toMatch(/north at the top, east at the left/i);
    const glyphs = [...container.querySelectorAll('[data-sky-glyph]')].map((el) => el.getAttribute('data-sky-glyph'));
    const below = container.querySelector('[data-sky-below]').textContent;
    for (const body of ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn']) {
      // Every body is either drawn or named as below the horizon, never missing.
      expect(glyphs.includes(body) || below.includes(body), body).toBe(true);
    }
    expect(glyphs.length + [...below.matchAll(/Sun|Moon|Mercury|Venus|Mars|Jupiter|Saturn/g)].length).toBe(7);
  });

  it('uses the observer in the link, and refuses an observer it cannot compute for instead of falling back', async () => {
    const { container } = renderSky('?view=sky&lat=95&lon=-66&t=2026-10-16T00:30:00Z');
    expect(await screen.findByRole('alert')).toHaveTextContent('Latitude must be between -90 and 90 degrees.');
    expect(container.querySelector('[data-sky-sun]')).toBeNull();
    expect(container.querySelector('[data-sky-default-observer]')).toBeNull();
  });

  it('refuses a coordinate that is not a number', async () => {
    renderSky('?view=sky&lat=north&lon=-66&t=2026-10-16T00:30:00Z');
    expect(await screen.findByRole('alert')).toHaveTextContent(/Latitude is not a number: north/);
  });

  it('refuses a link that names one coordinate without the other, rather than mixing it with the default', async () => {
    const { container } = renderSky('?view=sky&lat=18&t=2026-10-16T00:30:00Z');
    expect(await screen.findByRole('alert')).toHaveTextContent('Give both latitude and longitude, or neither.');
    expect(container.querySelector('[data-sky-sun]')).toBeNull();
  });

  it('refuses a time with no zone, which would be read in the viewer\'s own zone', async () => {
    renderSky('?view=sky&t=2026-10-16T00:30:00');
    expect(await screen.findByRole('alert')).toHaveTextContent(/UTC designator/);
  });

  it('applies a new observer to the link and recomputes for it', async () => {
    const { container } = renderSky();
    fireEvent.change(screen.getByLabelText('Latitude (°N)'), { target: { value: '-33.4489' } });
    fireEvent.change(screen.getByLabelText('Longitude (°E)'), { target: { value: '-70.6693' } });
    fireEvent.change(screen.getByLabelText('Elevation (m)'), { target: { value: '520' } });
    fireEvent.change(screen.getByLabelText('UTC offset (hours)'), { target: { value: '-3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply observer' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent(/lat=-33\.4489&lon=-70\.6693/));
    expect(screen.getByTestId('where')).toHaveTextContent('view=sky');
    expect(container.querySelector('[data-sky-default-observer]')).toBeNull();
    const ref = horizons('Mars', 'Santiago', '2026-10-16T00:30:00Z');
    expect(Math.abs(number(within(container.querySelector('[data-sky-planet="Mars"]')).getByTestId('altitude')) - shownAltitude(ref))).toBeLessThan(0.1);
  });

  it('steps the time by exact amounts and puts it in the link', async () => {
    renderSky();
    fireEvent.click(screen.getByRole('button', { name: 'Forward 1 hour' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('t=2026-10-16T01:30:00Z'));
    fireEvent.click(screen.getByRole('button', { name: 'Back 1 day' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('t=2026-10-15T01:30:00Z'));
    fireEvent.change(screen.getByLabelText('Time (UTC)'), { target: { value: '2026-12-21T18:00:00Z' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set time' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('t=2026-12-21T18:00:00Z'));
  });

  it('keeps the clock still unless asked to follow it, and follows it every 30 seconds when asked', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] });
    vi.setSystemTime(new Date('2026-10-16T00:30:10Z'));
    const { container } = renderSky('?view=sky');
    const shown = () => container.querySelector('[data-sky-time]').textContent;
    expect(shown()).toContain('2026-10-16T00:30:10Z');
    act(() => { vi.advanceTimersByTime(65000); });
    expect(shown()).toContain('2026-10-16T00:30:10Z');
    // Following takes the time to now at once (the clock has moved to 00:31:15), then every 30 seconds.
    fireEvent.click(screen.getByLabelText('Follow the clock'));
    expect(shown()).toContain('2026-10-16T00:31:15Z');
    act(() => { vi.advanceTimersByTime(30000); });
    expect(shown()).toContain('2026-10-16T00:31:45Z');
    // Following is not a fixed time, so the link carries none.
    expect(screen.getByTestId('where').textContent).not.toMatch(/t=/);
    // Turning it off keeps the moment it stopped on, in the link.
    fireEvent.click(screen.getByLabelText('Follow the clock'));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('t=2026-10-16T00:31:45Z'));
  });

  it('is accessible', async () => {
    const { container } = renderSky();
    await screen.findByText(/Planetary K-index/);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('Space weather', () => {
  beforeEach(() => loadSpaceWeather.mockReset());

  it('shows Kp, solar-wind speed and IMF Bz with their time, age, state and source, and says they are the latest readings', async () => {
    loadSpaceWeather.mockResolvedValue(await realReadings());
    const { container } = renderSky();
    const kp = await waitFor(() => { const el = container.querySelector('[data-sw="kp"]'); expect(el).toBeTruthy(); return el; });
    expect(within(kp).getByTestId('sw-value')).toHaveTextContent('1.67');
    expect(within(kp).getByTestId('sw-state')).toHaveTextContent('LIVE');
    expect(kp.textContent).toMatch(/8 stations/);
    expect(kp.querySelector('[data-sw-scale]')).toBeNull();
    const speed = container.querySelector('[data-sw="solar-wind-speed"]');
    expect(within(speed).getByTestId('sw-value')).toHaveTextContent('411');
    expect(speed).toHaveTextContent('km/s');
    expect(speed).toHaveTextContent('rounded by the provider');
    const imf = container.querySelector('[data-sw="imf-bz"]');
    expect(within(imf).getByTestId('sw-value')).toHaveTextContent('3');
    expect(imf).toHaveTextContent('northward');
    expect(container.querySelector('[data-sw-note]')).toHaveTextContent('not tied to the time above');
    const spark = container.querySelector('svg[data-sw-sparkline]');
    expect(spark).toHaveAttribute('role', 'img');
    expect(spark.getAttribute('aria-label')).toMatch(/Kp over 7\.8 days/);
  });

  it('marks a storm-level Kp with its NOAA scale, in words and not only colour', async () => {
    const readings = await realReadings();
    loadSpaceWeather.mockResolvedValue({ ...readings, kp: { ...readings.kp, value: 6.33, scale: 'G2' } });
    const { container } = renderSky();
    const scale = await waitFor(() => { const el = container.querySelector('[data-sw-scale]'); expect(el).toBeTruthy(); return el; });
    expect(scale).toHaveTextContent('G2');
    expect(scale).toHaveTextContent(/storm/i);
  });

  it('shows an old reading as STALE with its age, and a failed one as unavailable with the reason and no number', async () => {
    const readings = await realReadings();
    loadSpaceWeather.mockResolvedValue({
      ...readings,
      solarWind: { ...readings.solarWind, state: 'STALE', ageMinutes: 127 },
      imf: { id: 'imf-bz', label: 'IMF Bz (GSM)', state: 'FAILED', value: null, observedAt: null, ageMinutes: null, error: 'HTTP 503', source: readings.imf.source },
    });
    const { container } = renderSky();
    const speed = await waitFor(() => { const el = container.querySelector('[data-sw="solar-wind-speed"]'); expect(el).toBeTruthy(); return el; });
    expect(within(speed).getByTestId('sw-state')).toHaveTextContent('STALE');
    expect(speed).toHaveTextContent('2 h 7 min ago');
    const imf = container.querySelector('[data-sw="imf-bz"]');
    expect(within(imf).getByTestId('sw-state')).toHaveTextContent('FAILED');
    expect(imf).toHaveTextContent('Unavailable: HTTP 503');
    expect(within(imf).queryByTestId('sw-value')).toBeNull();
  });

  it('says so when the whole request fails, and offers a refresh that asks again', async () => {
    loadSpaceWeather.mockRejectedValueOnce(new Error('Failed to fetch'));
    renderSky();
    expect(await screen.findByText(/Space weather could not be read: Failed to fetch/)).toBeInTheDocument();
    loadSpaceWeather.mockResolvedValue(await realReadings());
    fireEvent.click(screen.getByRole('button', { name: 'Refresh space weather' }));
    await waitFor(() => expect(document.querySelector('[data-sw="kp"]')).toBeTruthy());
    expect(loadSpaceWeather).toHaveBeenCalledTimes(2);
  });
});
