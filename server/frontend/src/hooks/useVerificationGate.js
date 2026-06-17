import { useMemo } from "react";
import { federation } from "@/api/federationClient";
import { useEntityData } from "@/hooks/useEntityData";

// Statuses that still require an analyst verification decision before promotion.
const PENDING = ["New", "Updated", "NeedsReview"];
const GATE_MODULES = ["MoneySweep-PR", "AguaYLuz-PR"];

// Federation verification gate: surfaces incoming MoneySweep/AguaYLuz feed
// items awaiting analyst sign-off before they can be promoted to the ledger.
export function useVerificationGate() {
  const { rows, isLoading, update, saving } = useEntityData("LiveFeedItems", "-created_date");

  const pending = useMemo(
    () => rows.filter((i) => GATE_MODULES.includes(i.module) && PENDING.includes(i.sync_status)),
    [rows]
  );

  const verified = useMemo(
    () => rows.filter((i) => GATE_MODULES.includes(i.module) && i.sync_status === "Verified"),
    [rows]
  );

  const counts = useMemo(() => ({
    moneysweep: pending.filter((i) => i.module === "MoneySweep-PR").length,
    aguayluz: pending.filter((i) => i.module === "AguaYLuz-PR").length,
    verifiedReady: verified.length,
  }), [pending, verified]);

  // Mark an item Verified — stamps reviewer + timestamp so the gate is auditable.
  async function verify(item, note) {
    let reviewer = null;
    try { reviewer = (await federation.auth.me())?.email || null; } catch { reviewer = null; }
    await update(item.id, {
      sync_status: "Verified",
      verified_by: reviewer,
      verified_at: new Date().toISOString(),
      verification_note: note || item.verification_note || "",
    });
  }

  async function reject(item) {
    await update(item.id, { sync_status: "NeedsReview" });
  }

  return { pending, verified, counts, isLoading, saving, verify, reject };
}