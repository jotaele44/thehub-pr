// What a person sees is the refracted sky. The geometric directions the engines compute for satellites and aircraft are
// lifted by standard atmospheric refraction under the same rule the Sun, Moon and planets use in astronomy.js: for a
// geometric elevation above -1 degree the apparent elevation is the geometric one plus standard refraction (34
// arcminutes at the horizon, 5 at 10 degrees, about 1 at 45); deeper below the horizon there is no apparent position
// to lift. Standard refraction is for 1010 hPa and 10 C: a real atmosphere differs by tenths of a degree at the horizon.
import { Refraction } from 'astronomy-engine';

export const REFRACTION_FLOOR_DEGREES = -1;

export function apparentElevation(geometricElevation) {
  if (!Number.isFinite(geometricElevation)) throw new RangeError(`Elevation is not a number: ${String(geometricElevation)}`);
  return geometricElevation > REFRACTION_FLOOR_DEGREES ? geometricElevation + Refraction('normal', geometricElevation) : geometricElevation;
}
