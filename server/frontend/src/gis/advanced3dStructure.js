function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

export function validateTilesetStructure(tileset) {
  if (!tileset || typeof tileset !== 'object') throw new Error('3D Tiles fixture must be an object');
  if (tileset?.asset?.version !== '1.1') throw new Error('3D Tiles fixture must declare asset.version 1.1');
  if (!finiteNumber(tileset.geometricError) || tileset.geometricError < 0) throw new Error('tileset geometricError must be finite and non-negative');
  const root = tileset.root;
  if (!root || typeof root !== 'object') throw new Error('3D Tiles fixture requires root');
  if (!finiteNumber(root.geometricError) || root.geometricError < 0) throw new Error('root geometricError must be finite and non-negative');
  const box = root?.boundingVolume?.box;
  if (!Array.isArray(box) || box.length !== 12 || !box.every(finiteNumber)) throw new Error('root boundingVolume.box must contain 12 finite numbers');
  const uri = root?.content?.uri;
  if (typeof uri !== 'string' || !uri || uri.includes('..') || uri.startsWith('/')) throw new Error('3D Tiles content URI must be bounded and relative');
  return Object.freeze({
    status: 'PASS_STRUCTURAL_3D_TILES_1_1',
    contentUri: uri,
    boundingVolumeType: 'box',
    canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
    spatialIdentityCertified: false,
  });
}

export function validatePointCloudFixture({ rows, crs, verticalDatum, verticalDatumStatus }) {
  if (!Array.isArray(rows) || rows.length === 0) throw new Error('point-cloud fixture requires rows');
  if (!crs) return Object.freeze({ status: 'OPEN_CRS', spatialIdentityCertified: false });
  const parsed = rows.map((row) => String(row).trim().split(/\s+/).map(Number));
  if (parsed.some((row) => row.length < 3 || row.slice(0, 3).some((value) => !Number.isFinite(value)))) {
    throw new Error('point-cloud fixture rows require finite X Y Z values');
  }
  if (!verticalDatum || verticalDatum === 'UNRESOLVED' || verticalDatumStatus !== 'UNIFORM_BOUND') {
    return Object.freeze({
      status: 'OPEN_VERTICAL_DATUM',
      crs,
      pointCount: parsed.length,
      spatialIdentityCertified: false,
      canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
    });
  }
  return Object.freeze({
    status: 'READY_FOR_RUNTIME_BINDING',
    crs,
    verticalDatum,
    pointCount: parsed.length,
    spatialIdentityCertified: false,
    canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
  });
}
