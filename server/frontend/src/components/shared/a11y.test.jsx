import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { Activity } from 'lucide-react';
import PageHeader from '@/components/shared/PageHeader';
import EmptyState from '@/components/shared/EmptyState';
import StatCard from '@/components/shared/StatCard';
import StatusChip from '@/components/shared/StatusChip';
import { SEVERITY } from '@/lib/chips';

describe('accessibility (axe)', () => {
  it('PageHeader has no violations', async () => {
    const { container } = render(<PageHeader icon={Activity} title="Sources" description="Unified sources" />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('EmptyState has no violations', async () => {
    const { container } = render(<EmptyState title="No records" description="Nothing yet" />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('a StatCard + chip row has no violations', async () => {
    const { container } = render(
      <div>
        <StatCard label="Open" value={3} icon={Activity} />
        <StatusChip map={SEVERITY} value="High" />
      </div>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
