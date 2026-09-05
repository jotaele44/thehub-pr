import { acquireOnlineSource as acquireProtocolSource, acquireRasterAsset } from './remoteAcquisition';
import { getOnlineSourceDefinition } from './sourceRegistry';
import { toStacInterval } from './stacTime';

export { acquireRasterAsset };

export async function acquireOnlineSource(sourceId, options = {}) {
  const source = getOnlineSourceDefinition(sourceId);
  if (source.protocol !== 'stac') return acquireProtocolSource(sourceId, options);
  const interval = toStacInterval(options.start || null, options.end || null);
  return acquireProtocolSource(sourceId, {
    ...options,
    start: interval.start,
    end: interval.end,
    requestedStart: interval.requestedStart,
    requestedEnd: interval.requestedEnd,
  });
}
