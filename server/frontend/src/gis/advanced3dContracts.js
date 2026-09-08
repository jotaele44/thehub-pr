const ALLOWED_KINDS = new Set(['terrain', '3d-tiles', 'point-cloud']);
const VERTICAL_DATUM_READY = 'UNIFORM_BOUND';

export function certifyAdvanced3dSource(candidate) {
  if (!candidate || !ALLOWED_KINDS.has(candidate.kind)) throw new Error('unsupported advanced 3D source kind');
  if (!candidate.sourceId || !candidate.hrefManifestation) throw new Error('advanced 3D source requires stable sourceId and href manifestation');

  if (candidate.kind === 'terrain') {
    if (!candidate.verticalDatum || candidate.verticalDatumStatus !== VERTICAL_DATUM_READY) {
      return Object.freeze({
        ...candidate,
        status: 'OPEN_VERTICAL_DATUM',
        canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
      });
    }
  }

  if (candidate.kind === 'point-cloud') {
    if (!candidate.crs) {
      return Object.freeze({ ...candidate, status: 'OPEN_CRS', canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY' });
    }
    if (!candidate.verticalDatum || candidate.verticalDatum === 'UNRESOLVED' || candidate.verticalDatumStatus !== VERTICAL_DATUM_READY) {
      return Object.freeze({ ...candidate, status: 'OPEN_VERTICAL_DATUM', canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY' });
    }
  }

  return Object.freeze({
    ...candidate,
    status: 'READY_FOR_RUNTIME_BINDING',
    canonicalIdentityStatus: candidate.canonicalIdentityStatus || 'CANDIDATE_NOT_IDENTITY',
  });
}

export const ADVANCED_3D_KINDS = Object.freeze([...ALLOWED_KINDS]);
export const TERRAIN_VERTICAL_DATUM_READY_STATUS = VERTICAL_DATUM_READY;
export const POINT_CLOUD_VERTICAL_DATUM_READY_STATUS = VERTICAL_DATUM_READY;
