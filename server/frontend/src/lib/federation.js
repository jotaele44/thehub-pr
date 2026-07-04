export const HUB_REPO = 'thehub-pr';

export const REGIONS = ['North', 'South', 'East', 'West', 'Central', 'Metro', 'Offshore', 'IslandWide', 'Unknown'];

export const MODULES = [
  { key: 'prog-control', id: 'prog-control', label: 'INTSYS-PR', name: 'INTSYS-PR', module: 'Hub', domain: 'ControlPlane', route: '/hub' },
  { key: 'prog-spiderweb', id: 'prog-spiderweb', label: 'Spiderweb-PR', name: 'Spiderweb-PR', module: 'Spiderweb-PR', domain: 'NetworkGraph', route: '/spiderweb' },
  { key: 'prog-ovnis', id: 'prog-ovnis', label: 'Ovnis-PR', name: 'Ovnis-PR', module: 'Ovnis-PR', domain: 'UAP', route: '/ovnis' },
  { key: 'prog-aguayluz', id: 'prog-aguayluz', label: 'AguaYLuz-PR', name: 'AguaYLuz-PR', module: 'AguaYLuz-PR', domain: 'Infrastructure', route: '/aguayluz' },
  { key: 'prog-moneysweep', id: 'prog-moneysweep', label: 'MoneySweep-PR', name: 'MoneySweep-PR', module: 'MoneySweep-PR', domain: 'Contracts', route: '/moneysweep' },
  { key: 'prog-skywatcher', id: 'prog-skywatcher', label: 'Skywatcher-PR', name: 'Skywatcher-PR', module: 'Skywatcher-PR', domain: 'Airspace', route: '/skywatcher' },
];

export const GATE_NAMES = {
  gate_control_1: 'Schema alignment',
  gate_control_2: 'Source provenance',
  gate_control_3: 'Review workflow',
  gate_control_4: 'Export readiness',
  gate_control_5: 'GitHub sync',
};

const DOMAIN_ACCENTS = {
  ControlPlane: 'border-slate-500/30 bg-slate-500/10 text-slate-200',
  NetworkGraph: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-200',
  UAP: 'border-violet-500/30 bg-violet-500/10 text-violet-200',
  Infrastructure: 'border-teal-500/30 bg-teal-500/10 text-teal-200',
  Contracts: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  Airspace: 'border-sky-500/30 bg-sky-500/10 text-sky-200',
};

export function domainAccent(domain) {
  return DOMAIN_ACCENTS[domain] || DOMAIN_ACCENTS.ControlPlane;
}
