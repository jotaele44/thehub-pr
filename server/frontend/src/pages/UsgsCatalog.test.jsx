import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, afterEach } from 'vitest';
import UsgsCatalog from './UsgsCatalog';
import { federation } from '@/api/federationClient';

vi.mock('@/api/federationClient', () => ({ federation: { usgs: { catalog: vi.fn() } } }));
const catalog = {
  counts: { included: 174, excluded: 23 }, source: { sha256: 'a'.repeat(64) }, issues: [],
  catalog_state: 'PASS', payload_state: 'BLOCKED', acquisition_summary: { activated: 0 },
  repositories: [{ program_id: 'spiderweb-pr' }, { program_id: 'aguayluz-pr' }],
  records: [{ sciencebase_id: 'source1', raw: { Title: 'Karst DEM', Category: 'PR-specific', Year: '2022', 'ScienceBase URL': 'https://www.sciencebase.gov/catalog/item/source1' },
    consumer_candidates: [{ program_id: 'spiderweb-pr' }], activation_state: 'BLOCKED', acquisition: { state: 'BLOCKED', http_status: 403 } }],
};
afterEach(() => vi.clearAllMocks());
describe('USGS catalog viewer', () => {
  test('loads evidence and filters without activation', async () => {
    federation.usgs.catalog.mockResolvedValue(catalog);
    render(<UsgsCatalog />);
    expect(await screen.findByText('Karst DEM')).toBeVisible();
    expect(screen.getByText(/HTTP: 403/)).toBeVisible();
    fireEvent.change(screen.getByLabelText('Search releases'), { target: { value: 'absent' } });
    expect(screen.getByText('No releases match these filters.')).toBeVisible();
    fireEvent.change(screen.getByLabelText('Search releases'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Consumer'), { target: { value: 'aguayluz-pr' } });
    expect(screen.getByText('No releases match these filters.')).toBeVisible();
    fireEvent.change(screen.getByLabelText('Consumer'), { target: { value: 'spiderweb-pr' } });
    expect(screen.getByText('Karst DEM')).toBeVisible();
    expect(screen.queryByRole('button', { name: /activate/i })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Reload catalog' }));
    await waitFor(() => expect(federation.usgs.catalog).toHaveBeenCalledTimes(2));
  });
  test('reports an unavailable catalog and allows retry', async () => {
    federation.usgs.catalog.mockRejectedValue(new Error('Evidence unavailable'));
    render(<UsgsCatalog />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Evidence unavailable');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reload catalog' })).toBeEnabled());
  });
});
