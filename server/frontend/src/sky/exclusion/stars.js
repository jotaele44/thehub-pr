// Bright stars for the celestial exclusion engine (FDX-034): where a catalogue star is in an observer's sky at a UTC
// instant. The catalogue (starCatalog.json) holds the stars brighter than V 3.5 with J2000 coordinates and the
// Hipparcos number of each; it is NOT every star, and it carries no proper motion, parallax or aberration. Those are
// small beside a sight line's tolerance (aberration up to 20 arcseconds, proper motion up to a few arcseconds a year for
// the brightest) but they are not applied, and the receipt says so. Positions are held to the US Naval Observatory's
// celestial-navigation service (usnoCelnavStars.json) by stars.test.js.
import { Horizon, MakeTime, Observer, RotateVector, Rotation_EQJ_EQD, Spherical, VectorFromSphere, EquatorFromVector } from 'astronomy-engine';
import { instantFrom } from '../astronomy.js';
import catalog from './starCatalog.json';

export const STAR_CATALOG = Object.freeze({
  contract: catalog.contract, source: Object.freeze(catalog.source), epoch: catalog.epoch, limit: Object.freeze(catalog.limit), notice: catalog.notice,
});

function labelOf(hip, name, bayer, constellation) {
  if (name) return name;
  if (bayer && constellation) return `${bayer} ${constellation}`;
  return `HIP ${hip}`;
}

export const STARS = Object.freeze(catalog.stars.map(([hip, ra, dec, magnitude, name, bayer, constellation]) => Object.freeze({
  hip, ra, dec, magnitude, name: name || null, bayer: bayer || null, constellation: constellation || null, label: labelOf(hip, name, bayer, constellation),
})));

// The star's azimuth (from north through east) and altitude: apparent (standard refraction, as a person sees it) and
// geometric (airless). The J2000 position is rotated to the true equator and equinox of date (precession and nutation),
// then turned into the horizon frame by the same routine the Sun, Moon and planets use.
export function starPosition(star, instant, observer) {
  const time = MakeTime(instantFrom(instant));
  const engine = new Observer(observer.lat, observer.lon, observer.elevation ?? observer.height ?? 0);
  const j2000 = VectorFromSphere(new Spherical(star.dec, star.ra, 1), time);
  const ofDate = EquatorFromVector(RotateVector(Rotation_EQJ_EQD(time), j2000));
  const apparent = Horizon(time, engine, ofDate.ra, ofDate.dec, 'normal');
  const airless = Horizon(time, engine, ofDate.ra, ofDate.dec, undefined);
  return { hip: star.hip, label: star.label, magnitude: star.magnitude, azimuth: apparent.azimuth, altitude: apparent.altitude, altitudeAirless: airless.altitude, azimuthAirless: airless.azimuth };
}
