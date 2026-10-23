import { federation } from "@/api/federationClient";

async function existingPromotedRecord(entityName, recordId, feedItemId, idField) {
  let existing;
  try {
    existing = await federation.entities[entityName].get(recordId);
  } catch (error) {
    if (error?.status !== 404) throw error;
    const matches = await federation.entities[entityName].filter(
      { [idField]: recordId },
      "-created_date",
      2
    );
    if (!Array.isArray(matches)) {
      throw new Error(`Could not verify whether ${entityName}/${recordId} already exists`);
    }
    if (matches.length > 1) {
      throw new Error(`Multiple ${entityName} records match ${idField} ${recordId}`);
    }
    existing = matches[0];
    if (!existing) return null;
  }

  if (String(existing.promoted_from_feed_item) !== feedItemId) {
    throw new Error(`${entityName}/${recordId} is already linked to a different feed item`);
  }
  return existing;
}

async function createOrReusePromotedRecord(entityName, recordId, feedItemId, payload, idField) {
  const existing = await existingPromotedRecord(entityName, recordId, feedItemId, idField);
  if (existing) return existing[idField] || existing.id || recordId;

  try {
    const created = await federation.entities[entityName].create(payload);
    return created?.[idField] || created?.id || recordId;
  } catch (error) {
    if (error?.status !== 409) throw error;
    const raced = await existingPromotedRecord(entityName, recordId, feedItemId, idField);
    if (!raced) throw error;
    return raced[idField] || raced.id || recordId;
  }
}

// Promote a verified live-feed item into its module's canonical ledger.
// MoneySweep-PR items become Contracts; AguaYLuz-PR items become
// InfrastructureAssets. Returns the promoted record's id.
export async function promoteFeedItem(item) {
  if (!item) throw new Error("No feed item to promote");
  const feedItemId = String(item.item_id || item.id || "").trim();
  if (!feedItemId) throw new Error("Feed item has no stable identity to promote");
  const nowIso = new Date().toISOString();

  if (item.module === "MoneySweep-PR") {
    const contractId = item.external_id ? `con-${item.external_id}` : `con-feed-${feedItemId}`;
    return createOrReusePromotedRecord("Contracts", contractId, feedItemId, {
      id: contractId,
      contract_id: contractId,
      title: item.title || item.summary || "Promoted feed award",
      agency: item.agency || item.agency_name || item.awarding_agency || null,
      vendor_name: item.vendor_name || null,
      amount: item.amount ?? null,
      award_date: item.award_date || item.published_at || null,
      municipality: item.municipality || null,
      source_url: item.url || item.source_url || null,
      status: "New",
      sensitivity: item.sensitivity || "Public",
      created_from: "LiveFeed",
      promoted_from_feed_item: feedItemId,
      promoted_at: nowIso,
    }, "contract_id");
  }

  if (item.module === "AguaYLuz-PR") {
    const assetId = item.external_id ? `asset-${item.external_id}` : `asset-feed-${feedItemId}`;
    return createOrReusePromotedRecord("InfrastructureAssets", assetId, feedItemId, {
      id: assetId,
      asset_id: assetId,
      name: item.title || item.summary || "Promoted feed asset",
      asset_type: item.asset_type || "Other",
      municipality: item.municipality || null,
      latitude: item.latitude ?? null,
      longitude: item.longitude ?? null,
      status: "New",
      sensitivity: item.sensitivity || "Public",
      source_url: item.url || item.source_url || null,
      created_from: "LiveFeed",
      promoted_from_feed_item: feedItemId,
      promoted_at: nowIso,
    }, "asset_id");
  }

  throw new Error(`No promotion target configured for module ${item.module || "(unknown)"}`);
}
