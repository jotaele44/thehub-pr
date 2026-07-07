import { federation } from "@/api/federationClient";

// Promote a verified live-feed item into its module's canonical ledger.
// MoneySweep-PR items become Contracts; AguaYLuz-PR items become
// InfrastructureAssets. Returns the promoted record's id.
export async function promoteFeedItem(item) {
  if (!item) throw new Error("No feed item to promote");
  const nowIso = new Date().toISOString();

  if (item.module === "MoneySweep-PR") {
    const contractId = item.external_id ? `con-${item.external_id}` : `con-feed-${Date.now()}`;
    const created = await federation.entities.Contracts.create({
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
      promoted_from_feed_item: item.item_id || item.id,
      promoted_at: nowIso,
    });
    return created?.contract_id || created?.id || contractId;
  }

  if (item.module === "AguaYLuz-PR") {
    const assetId = item.external_id ? `asset-${item.external_id}` : `asset-feed-${Date.now()}`;
    const created = await federation.entities.InfrastructureAssets.create({
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
      promoted_from_feed_item: item.item_id || item.id,
      promoted_at: nowIso,
    });
    return created?.asset_id || created?.id || assetId;
  }

  throw new Error(`No promotion target configured for module ${item.module || "(unknown)"}`);
}
