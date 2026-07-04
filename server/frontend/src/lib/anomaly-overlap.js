import { MODULES } from '@/lib/federation';

export const MODULE_OPTIONS = MODULES.map((m) => ({ value: m.module || m.label, label: m.label }));

const same = (a, b) => a && b && String(a).trim().toLowerCase() === String(b).trim().toLowerCase();

export function buildOverlaps(cases = [], sources = [], contracts = [], assets = []) {
  const out = [];
  for (const c of cases) {
    for (const a of assets) {
      if (same(c.municipality, a.municipality)) out.push({ id: `case-asset-${c.id}-${a.id}`, type: 'Geography', case: c, target: a, module: 'AguaYLuz-PR', confidence: 'Medium' });
    }
    for (const k of contracts) {
      if (same(c.municipality, k.municipality)) out.push({ id: `case-contract-${c.id}-${k.id}`, type: 'Geography', case: c, target: k, module: 'MoneySweep-PR', confidence: 'Medium' });
    }
  }
  return out;
}
