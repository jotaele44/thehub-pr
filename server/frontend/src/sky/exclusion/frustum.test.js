import { describe, expect, it } from 'vitest';
import { angularSeparation } from './geometry';
import { cameraAngles, frustumContains, frustumMargin, frustumOutline, frustumRadius, validateFrustum } from './frustum';

const near = (value, expected, digits = 6) => expect(value).toBeCloseTo(expected, digits);
const wide = validateFrustum({ horizontalFovDegrees: 60, verticalFovDegrees: 40 });

// The direction that is `h` degrees to the right and `v` degrees up of the optical axis, in the camera's own frame
// (built independently of frustum.js from the pinhole definition, for a camera on the horizon looking along azimuth `az`).
function atCameraAngles(az, h, v) {
  const x = Math.tan((h * Math.PI) / 180);
  const y = Math.tan((v * Math.PI) / 180);
  const a = (az * Math.PI) / 180;
  const e = Math.sin(a) + x * Math.cos(a);
  const n = Math.cos(a) - x * Math.sin(a);
  const u = y;
  const length = Math.hypot(e, n, u);
  return { azimuth: ((Math.atan2(e, n) * 180) / Math.PI + 360) % 360, elevation: (Math.asin(u / length) * 180) / Math.PI };
}

describe('validateFrustum', () => {
  it('accepts a camera and defaults the roll to 0', () => {
    expect(wide).toEqual({ horizontalFovDegrees: 60, verticalFovDegrees: 40, rollDegrees: 0 });
    expect(Object.isFrozen(wide)).toBe(true);
  });

  it('refuses fields of view that are not between 0 and 180 degrees, and a roll that is not a number', () => {
    expect(() => validateFrustum({ horizontalFovDegrees: 0, verticalFovDegrees: 40 })).toThrow(/horizontal/i);
    expect(() => validateFrustum({ horizontalFovDegrees: 60, verticalFovDegrees: 180 })).toThrow(/vertical/i);
    expect(() => validateFrustum({ horizontalFovDegrees: 60 })).toThrow(/vertical/i);
    expect(() => validateFrustum({ horizontalFovDegrees: 60, verticalFovDegrees: 40, rollDegrees: 'a lot' })).toThrow(/roll/i);
  });
});

describe('frustumContains', () => {
  const centre = { azimuth: 135, elevation: 0 };

  it('contains the centre and the edges to the half field of view, and nothing beyond', () => {
    expect(frustumContains(wide, centre, 135, 0)).toBe(true);
    for (const [h, v, inside] of [[29.9, 0, true], [30.1, 0, false], [0, 19.9, true], [0, 20.1, false], [-29.9, -19.9, true], [29.9, 20.1, false]]) {
      const d = atCameraAngles(135, h, v);
      expect(frustumContains(wide, centre, d.azimuth, d.elevation), `h=${h} v=${v}`).toBe(inside);
    }
  });

  it('reports the angles in the camera\'s frame, and nothing for a direction behind the camera', () => {
    const d = atCameraAngles(135, 12, -7);
    const angles = cameraAngles(wide, centre, d.azimuth, d.elevation);
    near(angles.horizontalDegrees, 12, 9); near(angles.verticalDegrees, -7, 9);
    expect(cameraAngles(wide, centre, 315, 0)).toBeNull();
    expect(frustumContains(wide, centre, 315, 0)).toBe(false);
    expect(frustumMargin(wide, centre, 315, 0)).toBeNull();
  });

  it('turns a field of view on its side with 90 degrees of roll', () => {
    const rolled = validateFrustum({ horizontalFovDegrees: 60, verticalFovDegrees: 40, rollDegrees: 90 });
    // 25 degrees up is outside the 40-degree height of the level camera (20 each way) and inside the rolled one's 60-degree extent.
    expect(frustumContains(wide, centre, 135, 25)).toBe(false);
    expect(frustumContains(rolled, centre, 135, 25)).toBe(true);
    expect(frustumContains(rolled, centre, 135 + 25, 0)).toBe(false);
  });

  it('works for a camera pointed high in the sky, where azimuth steps are short', () => {
    const high = { azimuth: 40, elevation: 80 };
    expect(frustumContains(wide, high, 40, 80)).toBe(true);
    // 25 degrees of azimuth at 80 degrees elevation is only about 4 degrees of sky: inside the 60-degree-wide view.
    expect(frustumContains(wide, high, 65, 80)).toBe(true);
    expect(frustumContains(wide, high, 40, 20)).toBe(false);
  });

  it('gives the margin to the nearer edge when inside (negative) and the overshoot when outside (positive)', () => {
    const inside = atCameraAngles(135, 10, 0);
    near(frustumMargin(wide, centre, inside.azimuth, inside.elevation), -20, 6);
    const outside = atCameraAngles(135, 35, 0);
    near(frustumMargin(wide, centre, outside.azimuth, outside.elevation), 5, 6);
  });
});

describe('frustumOutline and frustumRadius', () => {
  it('traces the boundary: every outline point is on the edge of the field of view, and none is outside it', () => {
    const centre = { azimuth: 250, elevation: 35 };
    const rolled = validateFrustum({ horizontalFovDegrees: 50, verticalFovDegrees: 30, rollDegrees: 20 });
    const outline = frustumOutline(rolled, centre, 6);
    expect(outline).toHaveLength(24);
    for (const p of outline) {
      const angles = cameraAngles(rolled, centre, p.azimuth, p.elevation);
      const onEdge = Math.abs(Math.abs(angles.horizontalDegrees) - 25) < 1e-6 || Math.abs(Math.abs(angles.verticalDegrees) - 15) < 1e-6;
      expect(onEdge).toBe(true);
      expect(Math.abs(angles.horizontalDegrees)).toBeLessThanOrEqual(25 + 1e-6);
      expect(Math.abs(angles.verticalDegrees)).toBeLessThanOrEqual(15 + 1e-6);
    }
  });

  it('bounds every direction inside with the radius to the farthest corner', () => {
    const radius = frustumRadius(wide);
    const corner = atCameraAngles(0, 30, 20);
    near(angularSeparation(0, 0, corner.azimuth, corner.elevation), radius, 9);
    expect(radius).toBeGreaterThan(30);
    expect(radius).toBeLessThan(50);
  });
});
