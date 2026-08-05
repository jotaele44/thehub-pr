import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatusChip from '@/components/shared/StatusChip';
import { SEVERITY } from '@/lib/chips';

describe('StatusChip', () => {
  it('renders the value with its status-token classes', () => {
    render(<StatusChip map={SEVERITY} value="Critical" />);
    const chip = screen.getByText('Critical');
    expect(chip).toBeInTheDocument();
    expect(chip.className).toContain('status-danger');
  });

  it('renders an em-dash for empty values', () => {
    render(<StatusChip map={SEVERITY} value="" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
