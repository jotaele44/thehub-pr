import { describe, it, expect } from 'vitest';
import { EVIDENCE_AXES, axisValue, canonicalEvidenceRef, contradictionState, edgeState, evidenceHref } from '@/lib/evidenceState';

const axis = (key) => EVIDENCE_AXES.find((a) => a.key === key);

describe('evidenceState', () => {
  it('renders every declared axis value with a text label', () => {
    for (const a of EVIDENCE_AXES) {
      for (const [value, def] of Object.entries(a.values)) {
        expect(axisValue(a, value)).toMatchObject({ value, label: def.label });
        expect(def.label.length).toBeGreaterThan(0);
      }
    }
  });

  it('fails closed to the axis sentinel for missing or unknown values', () => {
    expect(axisValue(axis('epistemic_class'), undefined).value).toBe('UNCLASSIFIED');
    expect(axisValue(axis('epistemic_class'), 'FACT').value).toBe('UNCLASSIFIED');
    expect(axisValue(axis('identity_state'), null).value).toBe('UNRESOLVED');
    expect(axisValue(axis('geometry_precision'), 'EXACT').value).toBe('UNKNOWN');
    expect(edgeState('PROBABLE').value).toBe('UNKNOWN');
    expect(contradictionState(undefined).value).toBe('OPEN');
  });

  it('keeps representative points distinct from observed points', () => {
    const geometry = axis('geometry_precision');
    expect(axisValue(geometry, 'REPRESENTATIVE_POINT').label).toBe('Representative point');
    expect(axisValue(geometry, 'REPRESENTATIVE_POINT').label).not.toBe(axisValue(geometry, 'OBSERVED_POINT').label);
  });

  it('builds encoded deep links', () => {
    expect(evidenceHref('Entities', 'ent/1 x')).toBe('/evidence/Entities/ent%2F1%20x');
  });

  it('only canonical producer rows get an evidence reference', () => {
    expect(canonicalEvidenceRef({ entity_id: 'ent_1', _producers: ['aguayluz-pr'] })).toEqual({ collection: 'Entities', id: 'ent_1' });
    expect(canonicalEvidenceRef({ observation_id: 'obs_1', entity_id: 'ent_1', _producers: ['ovnis-pr'] })).toEqual({ collection: 'Observations', id: 'obs_1' });
    expect(canonicalEvidenceRef({ relationship_id: 'rel_1', _producers: ['x'] }).collection).toBe('Relationships');
    expect(canonicalEvidenceRef({ alert_id: 'alt_1', _producers: ['x'] }).collection).toBe('Alerts');
    expect(canonicalEvidenceRef({ source_id: 'src_1', source_name: 'S', _producers: ['x'] })).toEqual({ collection: 'Sources', id: 'src_1' });
    expect(canonicalEvidenceRef({ entity_id: 'local-1' })).toBeNull();
    expect(canonicalEvidenceRef({ entity_id: 'x', _producers: [] })).toBeNull();
    expect(canonicalEvidenceRef({ source_id: 'src_1', _producers: ['x'] })).toBeNull();
    expect(canonicalEvidenceRef(null)).toBeNull();
  });
});
