import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AguaYLuz from './AguaYLuz';

// Rows as `project_outdoor_conditions` (src/hub/ingest.py) writes them.
const OUTDOOR = [
  {
    id: 'ent_out_sj', municipality: 'San Juan', level: 'ELEVATED', driver_summary: 'High rip current risk today',
    rip_current_state: 'REPORTED', rip_current_risk: 'HIGH', surf_ft: '5–7',
    sea_state_state: 'REPORTED', buoy_station: '41053', buoy_distance_km: 4.2, wave_height_ft: 6.2, water_temp_f: 84.4,
    uv_state: 'REPORTED', uv_index: 11, uv_category: 'EXTREME',
    heat_state: 'REPORTED', heat_band: 'DANGER', heat_index_max_f: 106,
    air_quality_state: 'NOT_CONFIGURED',
    beach_water_quality_state: 'REPORTED', beach_advisories: 2, beach_advisory_names: 'Escambrón; Ocean Park',
    river_flood_state: 'REPORTED', rainfall_24h_state: 'REPORTED', rain_24h_max_in: 1.1, rain_24h_mean_in: 0.4,
    nws_alerts_state: 'REPORTED', nws_alerts: 'Heat Advisory', marine_alerts: 'Small Craft Advisory',
    as_of: '2026-10-19T12:00:00Z', _producers: ['aguayluz-pr'],
  },
  {
    id: 'ent_out_ut', municipality: 'Utuado', level: 'CAUTION',
    rip_current_state: 'NOT_COVERED', sea_state_state: 'STALE', buoy_station: '41056', wind_speed_kt: 11.7,
    uv_state: 'SOURCE_FAILED',
    heat_state: 'STALE', heat_band: 'CAUTION', air_quality_state: 'NOT_INGESTED',
    beach_water_quality_state: 'NOT_COVERED', river_flood_state: 'REPORTED', river_flood_category: 'minor',
    rainfall_24h_state: 'NOT_COVERED', nws_alerts_state: 'NONE_ACTIVE', closures: 1, closure_assets: 'El Portal',
    as_of: '2026-10-19T12:00:00Z', _producers: ['aguayluz-pr'],
  },
  // another producer's row in the same collection must not appear in the AguaYLuz tab
  { id: 'ent_out_x', municipality: 'Ponce', level: 'ELEVATED', _producers: ['skywatcher-pr'] },
];

vi.mock('@/hooks/useEntityData', () => ({
  useEntityData: (name) => ({
    rows: name === 'OutdoorConditions' ? OUTDOOR : [],
    create: vi.fn(), update: vi.fn(), saving: false,
  }),
}));
vi.mock('@/components/intelligence/IntelligenceWorkspace', () => ({ default: () => <p>workspace</p> }));
vi.mock('@/components/feed/AguaYLuzFeedTab', () => ({ default: () => <p>feed</p> }));

function openOutdoor() {
  render(<MemoryRouter><AguaYLuz /></MemoryRouter>);
  fireEvent.mouseDown(screen.getByRole('tab', { name: 'Outdoor Conditions' }), { button: 0 });
  return screen.getByRole('tabpanel');
}

const rowOf = (panel, municipio) => within(panel).getByText(municipio).closest('tr');

describe('AguaYLuz Outdoor Conditions tab', () => {
  it('lists only aguayluz-pr rows with their headline values', () => {
    const panel = openOutdoor();
    expect(within(panel).getByText(/Conditions context, not safety advice/)).toBeInTheDocument();
    expect(within(panel).queryByText('Ponce')).not.toBeInTheDocument();
    const sj = within(rowOf(panel, 'San Juan'));
    expect(sj.getByText('ELEVATED')).toBeInTheDocument();
    expect(sj.getByText('HIGH')).toBeInTheDocument();
    expect(sj.getByText('5–7 ft')).toBeInTheDocument();
    expect(sj.getByText('6.2 ft · 84.4 °F')).toBeInTheDocument();
    expect(sj.getByText('DANGER')).toBeInTheDocument();
    expect(sj.getByText('2 advisories')).toBeInTheDocument();
    expect(sj.getByText('No gauge in flood')).toBeInTheDocument();
    expect(sj.getByText('Heat Advisory · Small Craft Advisory')).toBeInTheDocument();
  });

  it('shows why a cell has no value instead of leaving it blank', () => {
    const panel = openOutdoor();
    const sj = within(rowOf(panel, 'San Juan'));
    expect(sj.getByText('NOT_CONFIGURED')).toBeInTheDocument(); // AirNow without its key
    const ut = within(rowOf(panel, 'Utuado'));
    expect(ut.getAllByText('NOT_COVERED').length).toBeGreaterThan(0);
    expect(ut.getByText('SOURCE_FAILED')).toBeInTheDocument();
    expect(ut.getByText('wind 11.7 kt, no waves')).toBeInTheDocument(); // a wind-only buoy
    expect(ut.getByText('NOT_INGESTED')).toBeInTheDocument();
    // a carried-forward value keeps a STALE chip beside it
    expect(ut.getAllByText('CAUTION')).toHaveLength(2); // the row's level and its heat band
    expect(ut.getAllByText('STALE')).toHaveLength(2); // the heat band and the buoy
    expect(ut.getByText('minor flood stage')).toBeInTheDocument();
    expect(ut.getByText('1 closure (El Portal)')).toBeInTheDocument();
  });
});
