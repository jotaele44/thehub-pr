import { federation } from '@/api/federationClient';

const LINEAGE = 'thehub-pr';

async function currentActor() {
  try { return (await federation.auth.me())?.email || null; } catch { return null; }
}

async function writeAuditLog({ module, action, entity_name, record_id, summary, actor }) {
  try {
    await federation.entities.AuditLog.create({
      log_id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      module,
      action,
      entity_name,
      record_id,
      summary,
      actor: actor || await currentActor(),
      occurred_at: new Date().toISOString(),
      source_repo: LINEAGE,
      test_record: false,
    });
  } catch (error) {
    // Promotion must not silently lose provenance. Surface this as a hard failure.
    throw new Error(`AuditLog write failed for ${entity_name}:${record_id} — ${error.message}`);
  }
}

async function promoteMoneySweep(item, actor) {
  let vendorId = item.linked_vendor_id;

  if (!vendorId && item.vendor_name) {
    const normalized = item.vendor_name.trim().toLowerCase();
    const existing = await federation.entities.Vendors.filter({ normalized_name: normalized });
    if (existing.length) {
      vendorId = existing[0].vendor_id;
    } else {
      const newVendorId = `ven-${item.feed_item_id}`;
      await federation.entities.Vendors.create({
        vendor_id: newVendorId,
        name: item.vendor_name,
        normalized_name: normalized,
        municipality: item.municipality,
        review_status: 'Unreviewed',
      });
      await writeAuditLog({
        module: 'MoneySweep-PR',
        action: 'Promote',
        entity_name: 'Vendors',
        record_id: newVendorId,
        actor,
        summary: `Created vendor from verified live feed item ${item.feed_item_id}.`,
      });
      vendorId = newVendorId;
    }
  }

  const contractId = `con-${item.feed_item_id}`;
  await federation.entities.Contracts.create({
    contract_id: contractId,
    title: item.title,
    agency: item.agency_name || 'Unknown',
    municipality: item.municipality,
    vendor_id: vendorId,
    award_amount: item.amount,
    award_date: item.date_awarded,
    procurement_type: 'Unknown',
    funding_source: item.funding_stream,
    source_url: item.source_url,
    status: 'New',
    summary: item.summary || `Promoted from live feed ${item.feed_item_id} (${LINEAGE}).`,
  });
  await writeAuditLog({
    module: 'MoneySweep-PR',
    action: 'Promote',
    entity_name: 'Contracts',
    record_id: contractId,
    actor,
    summary: `Created contract from verified live feed item ${item.feed_item_id}.`,
  });
  return contractId;
}

async function promoteAguaYLuz(item, actor) {
  const assetId = `ast-${item.feed_item_id}`;
  await federation.entities.InfrastructureAssets.create({
    asset_id: assetId,
    name: item.facility_name || item.title,
    asset_type: 'Other',
    municipality: item.municipality,
    latitude: item.latitude,
    longitude: item.longitude,
    status: 'UnderReview',
    sensitivity: 'Internal',
    summary: item.summary || `Promoted from live feed ${item.feed_item_id} (${LINEAGE}). ${item.event_type || ''}`.trim(),
  });
  await writeAuditLog({
    module: 'AguaYLuz-PR',
    action: 'Promote',
    entity_name: 'InfrastructureAssets',
    record_id: assetId,
    actor,
    summary: `Created infrastructure asset from verified live feed item ${item.feed_item_id}.`,
  });
  return assetId;
}

export async function promoteFeedItem(item) {
  if (item.sync_status !== 'Verified') {
    throw new Error('Item must be verified by an analyst before promotion to the ledger.');
  }
  const actor = await currentActor();
  if (item.module === 'MoneySweep-PR') return promoteMoneySweep(item, actor);
  if (item.module === 'AguaYLuz-PR') return promoteAguaYLuz(item, actor);
  throw new Error(`No promotion mapping for module ${item.module}`);
}
