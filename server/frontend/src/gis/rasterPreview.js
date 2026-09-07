import { fromUrl } from 'geotiff';

const MAX_PREVIEW_DIMENSION = 1024;

function previewDimensions(width, height) {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    throw new Error('raster preview requires positive image dimensions');
  }
  const scale = Math.min(1, MAX_PREVIEW_DIMENSION / Math.max(width, height));
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

function bboxCoordinates(bbox) {
  if (!Array.isArray(bbox) || bbox.length < 4 || bbox.some((value) => !Number.isFinite(Number(value)))) {
    throw new Error('raster preview requires a WGS84 STAC/source bbox');
  }
  const [west, south, east, north] = bbox.map(Number);
  if (west >= east || south >= north || west < -180 || east > 180 || south < -90 || north > 90) {
    throw new Error('raster preview bbox is not bounded WGS84');
  }
  return Object.freeze([
    Object.freeze([west, north]),
    Object.freeze([east, north]),
    Object.freeze([east, south]),
    Object.freeze([west, south]),
  ]);
}

function rgbToPngDataUrl(rgb, width, height) {
  if (typeof document === 'undefined') throw new Error('raster preview requires a browser canvas');
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { alpha: false });
  if (!context) throw new Error('2D canvas unavailable for raster preview');
  const rgba = new Uint8ClampedArray(width * height * 4);
  const pixelCount = width * height;
  const channels = Math.max(1, Math.floor(rgb.length / pixelCount));
  for (let pixel = 0; pixel < pixelCount; pixel += 1) {
    const source = pixel * channels;
    const target = pixel * 4;
    const r = rgb[source] ?? 0;
    const g = channels >= 2 ? rgb[source + 1] : r;
    const b = channels >= 3 ? rgb[source + 2] : r;
    rgba[target] = r;
    rgba[target + 1] = g;
    rgba[target + 2] = b;
    rgba[target + 3] = 255;
  }
  context.putImageData(new ImageData(rgba, width, height), 0, 0);
  return canvas.toDataURL('image/png');
}

export async function buildRasterPreview(rasterLayer, options = {}) {
  const href = rasterLayer?.sourceManifest?.hrefManifestation;
  if (!href) throw new Error('raster layer has no asset href manifestation');
  const coordinates = bboxCoordinates(rasterLayer.manifest?.bbox);
  const tiff = await fromUrl(href, { allowFullFile: false }, options.signal);
  const image = await tiff.getImage();
  const sourceWidth = image.getWidth();
  const sourceHeight = image.getHeight();
  const { width, height } = previewDimensions(sourceWidth, sourceHeight);
  const rgb = await image.readRGB({
    width,
    height,
    interleave: true,
    resampleMethod: 'bilinear',
    signal: options.signal,
  });
  const imageUrl = rgbToPngDataUrl(rgb, width, height);
  return Object.freeze({
    imageUrl,
    coordinates,
    sourceWidth,
    sourceHeight,
    previewWidth: width,
    previewHeight: height,
    assetClassification: rasterLayer.assetClassification || rasterLayer.manifest?.rawFormat || 'UNKNOWN_RASTER',
    alignmentStatus: 'STAC_BBOX_RECTIFIED_PREVIEW_NOT_PIXEL_GEOMETRY_CERTIFIED',
    byteIdentityStatus: rasterLayer.sourceManifest?.byteIdentityStatus || 'UNRESOLVED',
    fullAssetByteIdentity: 'OPEN',
    canonicalIdentityStatus: rasterLayer.sourceManifest?.canonicalIdentityStatus || 'CANDIDATE_NOT_IDENTITY',
  });
}

export const RASTER_PREVIEW_LIMITS = Object.freeze({ maxDimension: MAX_PREVIEW_DIMENSION });
