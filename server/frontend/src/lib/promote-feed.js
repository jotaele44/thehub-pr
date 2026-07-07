import { federation } from "@/api/federationClient";

// Maps a staged LiveFeedItem into a durable ledger record, then marks
// the feed item Promoted with a link back to the created record.
// Preserves provenance: source_url, evidence_tier, lineage repo, feed id.

const LINEAGE = "thehub-pr";

// --- MoneySweep: feed item -> Vendor (find/create) + Contract ---
async function promoteMoneySweep(item) {
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
        review_status: "Unreviewed",
      });
      vendorId = newVendorId;
    }
  }

  const contractId = `con-${item.feed_item_id}`;
  await federation.entities.Contracts.create({
    contract_id: contractId,
    title: item.title,
    agency: item.agency_name || "Unknown",
    municipality: item.municipality,
    vendor_id: vendorId,
    award_amount: item.amount,
    award_date: item.date_awarded,
    procurement_type: "Unknown",
    funding_source: item.funding_stream,
    source_url: item.source_url,
    status: "New",
    summary: item.summary || `Promoted from live feed ${item.feed_item_id} (${LINEAGE}).`,
  });
  return contractId;
}

// --- AguaYLuz: feed item -> InfrastructureAsset ---
async function promoteAguaYLuz(item) {
  const assetId = `ast-${item.feed_item_id}`;
  await federation.entities.InfrastructureAssets.create({
    asset_id: assetId,
    name: item.facility_name || item.title,
    asset_type: "Other",
    municipality: item.municipality,
    latitude: item.latitude,
    longitude: item.longitude,
    status: "UnderReview",
    sensitivity: "Internal",
    summary: item.summary || `Promoted from live feed ${item.feed_item_id} (${LINEAGE}). ${item.event_type || ""}`.trim(),
  });
  return assetId;
}

// Returns the id of the durable record created.
// Validation gate: an item must be analyst-Verified before it can hit the ledger.
export async function promoteFeedItem(item) {
  if (item.sync_status !== "Verified") {
    throw new Error("Item must be verified by an analyst before promotion to the ledger.");
  }
  if (item.module === "MoneySweep-PR") return promoteMoneySweep(item);
  if (item.module === "AguaYLuz-PR") return promoteAguaYLuz(item);
  throw new Error(`No promotion mapping for module ${item.module}`);
}