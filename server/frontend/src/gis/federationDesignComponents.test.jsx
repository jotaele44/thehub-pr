import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FederationDatasetGrid, FederationMapWorkspace } from '@pr-federation/react';

const columns = [{ key: 'name', label: 'Name' }];

describe('federation GIS component interactions', () => {
  it.each(['Enter', ' '])('activates a dataset row with %j', (key) => {
    const onSelectRecord = vi.fn();
    render(<FederationDatasetGrid records={[{ id: 'A', name: 'Alpha' }]} columns={columns} getRecordId={(record) => record.id} onSelectRecord={onSelectRecord} />);

    const row = screen.getByText('Alpha').closest('tr');
    row.focus();
    fireEvent.keyDown(row, { key });

    expect(onSelectRecord).toHaveBeenCalledWith('A');
  });

  it('synchronizes a changed initial basemap without remounting the provider', () => {
    const unsubscribe = vi.fn();
    const bridge = {
      getSelection: () => ({ recordId: null, geometryId: null, source: null }),
      subscribe: () => unsubscribe,
      getFeaturesForRecord: () => [],
      selectFeature: vi.fn(),
      selectRecord: vi.fn(),
    };
    const destroy = vi.fn();
    const provider = { mount: vi.fn(() => ({ destroy })), setBasemap: vi.fn(), setSelection: vi.fn() };
    const basemaps = [{ id: 'streets', label: 'Streets' }, { id: 'satellite', label: 'Satellite' }];
    const props = { records: [], columns, getRecordId: (record) => record.id, bridge, provider, basemaps };
    const { rerender } = render(<FederationMapWorkspace {...props} initialBasemapId="streets" />);

    rerender(<FederationMapWorkspace {...props} initialBasemapId="satellite" />);

    expect(screen.getByRole('combobox', { name: 'Map' })).toHaveValue('satellite');
    expect(provider.setBasemap).toHaveBeenLastCalledWith('satellite');
    expect(provider.mount).toHaveBeenCalledTimes(1);
  });
});
