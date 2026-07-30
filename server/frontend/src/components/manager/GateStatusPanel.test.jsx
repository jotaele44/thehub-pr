import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import GateStatusPanel from '@/components/manager/GateStatusPanel';

// The panel's job is to report the evaluator's verdict without softening it.
// These tests mostly guard against the ways a gate list can mislead: showing
// gates without their scope, or letting a note read as evidence.
const evidence = {
  profile_id: 'hub_slice',
  profile_scope: "TheHub's 13 declared operations. Says nothing about the 55 producer operations.",
  additional_profiles: {
    federation_vector: {
      profile_scope: 'All 68 operations across all seven apps.',
      summary: { passed: 11, deferred: 6, blocked_not_certified: 4 },
      gates: [],
    },
  },
  gates: [
    {
      gate_id: 'G03_NO_ARBITRARY_SHELL',
      requirement: 'No shell=True, os.system, eval, or string command execution.',
      status: 'passed',
      blocking: true,
      derived_from: [],
      attested_by: [
        {
          attestation_id: 'static.no_arbitrary_shell',
          attestation_sha256: 'a'.repeat(64),
          kind: 'static_analysis',
          result: 'satisfied',
          signature_verified: true,
        },
      ],
    },
    {
      gate_id: 'G07_NATIVE_SECRETS',
      requirement: 'macOS Keychain provider certified.',
      status: 'not_run',
      blocking: true,
      derived_from: [],
      annotations: [
        { author: 'operator', note: 'works on my machine', recorded_at: '2026-07-27T00:00:00Z' },
      ],
    },
  ],
};

describe('GateStatusPanel', () => {
  it('states the profile the gates were measured against', () => {
    render(<GateStatusPanel evidence={evidence} />);
    expect(screen.getByTestId('gate-profile')).toHaveTextContent('hub_slice');
    expect(screen.getByTestId('gate-profile')).toHaveTextContent(/55 producer operations/);
  });

  it('publishes the wider profile so a narrowed scope cannot hide it', () => {
    render(<GateStatusPanel evidence={evidence} />);
    const profile = screen.getByTestId('gate-profile');
    expect(profile).toHaveTextContent(/federation_vector/);
    expect(profile).toHaveTextContent(/4 blocked not certified/);
  });

  it('shows attestations as the evidence behind an attested gate', () => {
    render(<GateStatusPanel evidence={evidence} />);
    expect(screen.getByText(/static\.no_arbitrary_shell \(satisfied\)/)).toBeInTheDocument();
  });

  it('renders a note as commentary and leaves the machine status untouched', () => {
    render(<GateStatusPanel evidence={evidence} />);
    expect(screen.getByText(/note, not evidence/)).toBeInTheDocument();
    // The annotated gate is still not_run; the note has not promoted it.
    const gate = document.querySelector('[data-gate-id="G07_NATIVE_SECRETS"]');
    expect(gate).toHaveTextContent('not_run');
    expect(gate).not.toHaveTextContent('passed');
  });

  it('falls back to an explicit empty state rather than an empty list', () => {
    render(<GateStatusPanel evidence={{ gates: [] }} />);
    expect(screen.getByText(/No gate evidence yet/)).toBeInTheDocument();
  });
});
