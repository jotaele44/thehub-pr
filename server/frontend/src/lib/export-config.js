export const EXPORTS_STATUS = { Generated: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', Downloaded: 'bg-blue-500/15 text-blue-300 border-blue-500/30', Archived: 'bg-slate-500/15 text-slate-300 border-slate-500/30', Failed: 'bg-red-500/15 text-red-300 border-red-500/30' };
export const EXPORT_LEDGERS = [
  { key: 'UnifiedCases', label: 'Unified Cases', module: 'Hub', formats: ['CSV'] },
  { key: 'UnifiedSources', label: 'Unified Sources', module: 'Hub', formats: ['CSV'] },
  { key: 'Contracts', label: 'Contracts', module: 'MoneySweep-PR', formats: ['CSV', 'GeoJSON'] },
  { key: 'InfrastructureAssets', label: 'Infrastructure Assets', module: 'AguaYLuz-PR', formats: ['CSV', 'GeoJSON'] },
  { key: 'CrossoverLinks', label: 'Crossover Links', module: 'Hub', formats: ['CSV'] },
];
