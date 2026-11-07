import { describe, expect, it } from 'vitest';
import { apparentElevation } from './refraction';

describe('apparentElevation', () => {
  it('lifts by standard refraction: about half a degree at the horizon, 0.17 at 5 degrees, 0.02 at 45', () => {
    expect(apparentElevation(0) - 0).toBeGreaterThan(0.45);
    expect(apparentElevation(0) - 0).toBeLessThan(0.6);
    expect(apparentElevation(5) - 5).toBeGreaterThan(0.15);
    expect(apparentElevation(5) - 5).toBeLessThan(0.19);
    expect(apparentElevation(45) - 45).toBeGreaterThan(0.012);
    expect(apparentElevation(45) - 45).toBeLessThan(0.02);
    expect(apparentElevation(90) - 90).toBeLessThan(1e-6);
  });

  it('leaves a direction deeper than a degree below the horizon alone, where there is no apparent position to lift', () => {
    expect(apparentElevation(-1)).toBe(-1);
    expect(apparentElevation(-30)).toBe(-30);
    expect(apparentElevation(-0.5)).toBeGreaterThan(-0.5);
  });

  it('refuses an elevation that is not a number', () => {
    expect(() => apparentElevation(Number.NaN)).toThrow(RangeError);
  });
});
