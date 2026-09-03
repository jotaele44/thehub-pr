function arrayLikeLength(value) {
  if (Array.isArray(value) || ArrayBuffer.isView(value)) return value.length;
  return 0;
}

export function inspectCogStructure(fileDirectory = {}) {
  const tileWidth = Number(fileDirectory.TileWidth);
  const tileLength = Number(fileDirectory.TileLength);
  const tileOffsets = fileDirectory.TileOffsets;
  const tileByteCounts = fileDirectory.TileByteCounts;
  const stripOffsets = fileDirectory.StripOffsets;
  const stripByteCounts = fileDirectory.StripByteCounts;

  const tiled = Number.isFinite(tileWidth) && tileWidth > 0
    && Number.isFinite(tileLength) && tileLength > 0
    && arrayLikeLength(tileOffsets) > 0
    && arrayLikeLength(tileByteCounts) === arrayLikeLength(tileOffsets);
  const stripped = arrayLikeLength(stripOffsets) > 0 || arrayLikeLength(stripByteCounts) > 0;

  let status = 'UNRESOLVED_TIFF_LAYOUT';
  if (stripped && !tiled) status = 'NOT_COG_STRIP_LAYOUT';
  else if (tiled) status = 'COG_CANDIDATE_REQUIRES_BYTE_LAYOUT_VALIDATOR';

  return Object.freeze({
    status,
    tiled,
    stripped,
    tileWidth: Number.isFinite(tileWidth) ? tileWidth : null,
    tileLength: Number.isFinite(tileLength) ? tileLength : null,
    tileCount: arrayLikeLength(tileOffsets),
    cogCertified: false,
  });
}

export function certifyCogFromValidatorReceipt(structure, receipt) {
  if (structure?.status !== 'COG_CANDIDATE_REQUIRES_BYTE_LAYOUT_VALIDATOR') {
    throw new Error(`COG certification requires a tiled candidate, got ${structure?.status || 'UNRESOLVED'}`);
  }
  if (receipt?.status !== 'PASS' || receipt?.validator !== 'GDAL_COG_VALIDATOR') {
    throw new Error('COG certification requires an independent GDAL_COG_VALIDATOR PASS receipt');
  }
  if (!/^[a-f0-9]{64}$/i.test(receipt.fullAssetSha256 || '')) {
    throw new Error('COG certification requires whole-asset SHA256');
  }
  return Object.freeze({
    ...structure,
    status: 'COG_PASS_BOUNDED',
    cogCertified: true,
    validator: receipt.validator,
    validatorVersion: receipt.validatorVersion || null,
    fullAssetSha256: receipt.fullAssetSha256.toLowerCase(),
  });
}
