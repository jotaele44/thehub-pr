const ALLOWED_KINDS = new Set(['terrain', '3d-tiles', 'point-cloud']);

export function certifyAdvanced3dSource(candidate) {
  if (!candidate || !ALLOWED_KINDS.has(candidate.kind)) throw new Error('unsupported advanced 3D source kind');
  if (!candidate.sourceId || !candidate.hrefManifestation) throw new Error('advanced 3D source requires stable sourceId and href manifestation');
  if (candidate.kind === 'terrain' && !candidate.verticalDatum) {
    return Object.freeze({ ...candidate, status: 'OPEN_VERTICAL_DATUM', canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY' });
  }
  if (candidate.kind === 'point-cloud' && !candidate.crs) {
    return Object.freeze({ ...candidate, status: 'OPEN_CRS', canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY' });
  }
  return Object.freeze({
    ...candidate,
    status: 'READY_FOR_RUNTIME_BINDING',
    canonicalIdentityStatus: candidate.canonicalIdentityStatus || 'CANDIDATE_NOT_IDENTITY',
  });
}

export const ADVANCED_3D_KINDS = Object.freeze([...ALLOWED_KINDS]);
