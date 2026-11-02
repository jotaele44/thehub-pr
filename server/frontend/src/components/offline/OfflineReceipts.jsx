import React, { useEffect, useState } from 'react';

const storageKey = 'federation-offline-receipts-v1';
const repositories = {
  'jotaele44/spiderweb-pr': '1111911635', 'jotaele44/moneysweep-pr': '1197338153',
  'jotaele44/aguayluz-pr': '1257600730', 'jotaele44/skywatcher-pr': '1261399537',
  'jotaele44/ovnis-pr': '1252871400', 'jotaele44/centinelas-pr': '1284431262',
  'jotaele44/thehub-pr': '1258897469',
};
export function validOfflineReceipts(value) {
  return value?.schema === 'federation-offline-receipts/v1' && Array.isArray(value.rows)
    && value.rows.length === 7 && new Set(value.rows.map(row => row?.repository)).size === 7
    && value.rows.every(row => row && repositories[row.repository] === row.repositoryId
      && /^[0-9a-f]{40}$/.test(row.sourceHead)
      && ['PASS', 'OPEN', 'FAIL', 'BLOCKED'].includes(row.shell)
      && ['PASS', 'OPEN', 'FAIL', 'BLOCKED'].includes(row.data)
      && ['PASS', 'OPEN', 'FAIL', 'BLOCKED'].includes(row.sync));
}

export default function OfflineReceipts() {
  const [receipt, setReceipt] = useState(null);
  const [state, setState] = useState('Loading federation offline receipts…');
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    async function load() {
      try {
        const response = await fetch(`${import.meta.env.BASE_URL}offline-receipts.json`, { signal: controller.signal, cache: 'no-store', credentials: 'omit' });
        if (!response.ok) throw new Error('Receipt unavailable');
        const value = await response.json();
        if (!validOfflineReceipts(value)) throw new Error('Invalid receipt');
        if (!active) return;
        setReceipt(value);
        setState('Recorded candidate evidence. These results do not establish production or federation certification.');
        try { localStorage.setItem(storageKey, JSON.stringify(value)); } catch { setState('Receipt loaded; browser storage unavailable for offline retention.'); }
      } catch {
        if (!active) return;
        try {
          const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
          if (validOfflineReceipts(saved)) {
            setReceipt(saved);
            setState('Saved receipt snapshot; current remote heads have not been revalidated.');
            return;
          }
        } catch { /* Invalid or unavailable local storage is not evidence. */ }
        setState('No verified receipt snapshot available. Connect to load candidate evidence.');
      } finally { clearTimeout(timeout); }
    }
    void load();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, []);
  return <section aria-labelledby="offline-receipts-heading" className="xl:col-span-2 rounded-lg border p-4 space-y-3">
    <h2 id="offline-receipts-heading" className="font-semibold">Federation offline readiness</h2>
    <p role="status" className="text-sm text-muted-foreground">{state}</p>
    {receipt && <>
      <p className="text-xs">Snapshot: {receipt.observedAt} · Shell, domain data, and synchronization are independent gates.</p>
      <div className="overflow-x-auto"><table className="w-full text-sm">
        <thead><tr>{['Repository', 'Base head', 'Shell', 'Domain data', 'Sync'].map(label => <th key={label} scope="col" className="text-left p-2">{label}</th>)}</tr></thead>
        <tbody>{receipt.rows.map(row => <tr key={row.repository}>
          <th scope="row" className="text-left p-2">{row.repository}</th><td title={row.sourceHead}>{row.sourceHead.slice(0, 12)}</td>
          <td>{row.shell}</td><td>{row.data}</td><td>{row.sync}</td>
        </tr>)}</tbody>
      </table></div>
    </>}
  </section>;
}
