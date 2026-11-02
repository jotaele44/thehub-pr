import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import OfflineReceipts, { validOfflineReceipts } from './OfflineReceipts';
import receipt from '../../../public/offline-receipts.json';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });
describe('offline receipt consumer', () => {
  it('requires all seven authoritative repository bindings', () => {
    expect(validOfflineReceipts(receipt)).toBe(true);
    expect(validOfflineReceipts({ ...receipt, rows: receipt.rows.slice(1) })).toBe(false);
    const rows = structuredClone(receipt.rows); rows[0].repositoryId = 'wrong';
    expect(validOfflineReceipts({ ...receipt, rows })).toBe(false);
    rows[0] = rows[1];
    expect(validOfflineReceipts({ ...receipt, rows })).toBe(false);
  });
  it('renders network evidence without claiming production certification', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => receipt })));
    render(<OfflineReceipts />);
    expect(await screen.findByText('jotaele44/spiderweb-pr')).toBeInTheDocument();
    expect(screen.getByText(/do not establish production/)).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
  it('retains a labeled historical snapshot when disconnected', async () => {
    localStorage.setItem('federation-offline-receipts-v1', JSON.stringify(receipt));
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline'); }));
    render(<OfflineReceipts />);
    expect(await screen.findByText(/current remote heads have not been revalidated/)).toBeInTheDocument();
    expect(screen.getByText('jotaele44/thehub-pr')).toBeInTheDocument();
  });
  it('does not promote malformed saved data into a receipt', async () => {
    localStorage.setItem('federation-offline-receipts-v1', '{broken');
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline'); }));
    render(<OfflineReceipts />);
    expect(await screen.findByText(/No verified receipt snapshot/)).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
