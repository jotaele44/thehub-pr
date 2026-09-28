import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import ProvenanceInspector from './ProvenanceInspector';
import EvidenceStateStrip from './EvidenceStateStrip';
import { OVNIS_YEAR_ONLY_CASE } from '@/test/fixtures/evidenceObject';

describe('ProvenanceInspector', () => {
  it('renders every axis as text, never colour alone', () => {
    const { container } = render(<EvidenceStateStrip evidence={OVNIS_YEAR_ONLY_CASE} />);
    const chips = container.querySelectorAll('[data-evidence-axis]');
    expect(chips).toHaveLength(8);
    expect(container.querySelector('[data-evidence-axis="epistemic_class"]').textContent).toContain('Curated');
    expect(container.querySelector('[data-evidence-axis="temporal_precision"]').dataset.evidenceValue).toBe('YEAR_ONLY');
  });

  it('shows the year-only date without an invented time and preserves both contradicting claims', () => {
    render(<ProvenanceInspector evidence={OVNIS_YEAR_ONLY_CASE} />);
    const timeAndPlace = within(screen.getByRole('region', { name: 'Time and place' }));
    expect(timeAndPlace.getByText('1929')).toBeInTheDocument();
    expect(timeAndPlace.queryByText(/1929-01-01T00:00/)).toBeNull();
    expect(screen.getByText('1931')).toBeInTheDocument();
    expect(screen.getByText(/Claim A \(src_1\)/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'https://example.gov/foia/1' })).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('declares a missing source instead of substituting one', () => {
    const evidence = {
      ...OVNIS_YEAR_ONLY_CASE,
      source_state: 'SOURCE_MISSING',
      citations: [],
      raw_source_ids: [],
      lineage: { nodes: [{ node_id: 'missing-source:x', kind: 'SOURCE_MISSING', label: 'no source reference' }], edges: [] },
    };
    render(<ProvenanceInspector evidence={evidence} />);
    expect(screen.getByText(/No source has been substituted/)).toBeInTheDocument();
    expect(screen.getByText('No source is cited by this record.')).toBeInTheDocument();
  });

  it('flags synthetic rows and rejected producer declarations', () => {
    const evidence = { ...OVNIS_YEAR_ONLY_CASE, synthetic: true, declaration_errors: ["epistemic_class: 'FACT' is not a valid value"] };
    const { container } = render(<ProvenanceInspector evidence={evidence} />);
    expect(container.querySelector('[data-evidence-axis="synthetic"]')).not.toBeNull();
    expect(screen.getByText(/'FACT' is not a valid value/)).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = render(<ProvenanceInspector evidence={OVNIS_YEAR_ONLY_CASE} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
