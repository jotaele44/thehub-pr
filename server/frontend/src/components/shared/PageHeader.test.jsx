import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Activity } from 'lucide-react';
import PageHeader from '@/components/shared/PageHeader';
import ModulePageHeader from '@/components/shared/ModulePageHeader';
import { MODULES } from '@/lib/federation';

describe('PageHeader', () => {
  it('renders title, description and optional badge', () => {
    render(<PageHeader icon={Activity} title="Recent Activity" description="Latest signals" badge="Live" />);
    expect(screen.getByRole('heading', { name: 'Recent Activity' })).toBeInTheDocument();
    expect(screen.getByText('Latest signals')).toBeInTheDocument();
    expect(screen.getByText('Live')).toBeInTheDocument();
  });
});

describe('ModulePageHeader (preset over PageHeader)', () => {
  it('renders the module name, domain badge and legacy id', () => {
    const mod = MODULES[0];
    render(<ModulePageHeader module={mod} icon={Activity} />);
    expect(screen.getByRole('heading', { name: mod.name })).toBeInTheDocument();
    expect(screen.getByText(mod.domain)).toBeInTheDocument();
    expect(screen.getByText(mod.oldName)).toBeInTheDocument();
  });
});
