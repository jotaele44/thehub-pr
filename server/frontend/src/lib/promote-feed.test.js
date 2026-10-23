import { beforeEach, describe, expect, it, vi } from "vitest";
import { federation } from "@/api/federationClient";
import { promoteFeedItem } from "@/lib/promote-feed";

vi.mock("@/api/federationClient", () => ({
  federation: {
    entities: {
      Contracts: { get: vi.fn(), filter: vi.fn(), create: vi.fn() },
      InfrastructureAssets: { get: vi.fn(), filter: vi.fn(), create: vi.fn() },
    },
  },
}));

const notFound = () => Object.assign(new Error("not found"), { status: 404 });
const conflict = () => Object.assign(new Error("already exists"), { status: 409 });

describe("promoteFeedItem", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(federation.entities.Contracts.filter).mockResolvedValue([]);
    vi.mocked(federation.entities.InfrastructureAssets.filter).mockResolvedValue([]);
  });

  it("creates a stable MoneySweep record when no external ID is present", async () => {
    vi.mocked(federation.entities.Contracts.get).mockRejectedValue(notFound());
    vi.mocked(federation.entities.Contracts.create).mockResolvedValue({ contract_id: "con-feed-feed-7" });

    await expect(promoteFeedItem({
      id: "feed-7",
      module: "MoneySweep-PR",
      title: "Award",
    })).resolves.toBe("con-feed-feed-7");

    expect(federation.entities.Contracts.create).toHaveBeenCalledWith(expect.objectContaining({
      id: "con-feed-feed-7",
      contract_id: "con-feed-feed-7",
      promoted_from_feed_item: "feed-7",
    }));
  });

  it("reuses a prior creation after a feed-status update can be retried", async () => {
    vi.mocked(federation.entities.Contracts.get)
      .mockRejectedValueOnce(notFound())
      .mockResolvedValueOnce({
        contract_id: "con-award-17",
        promoted_from_feed_item: "feed-17",
      });
    vi.mocked(federation.entities.Contracts.create).mockResolvedValue({ contract_id: "con-award-17" });
    const item = { id: "feed-17", external_id: "award-17", module: "MoneySweep-PR" };

    await expect(promoteFeedItem(item)).resolves.toBe("con-award-17");
    await expect(promoteFeedItem(item)).resolves.toBe("con-award-17");

    expect(federation.entities.Contracts.create).toHaveBeenCalledTimes(1);
  });

  it("recovers safely from a concurrent duplicate-create conflict", async () => {
    vi.mocked(federation.entities.Contracts.get)
      .mockRejectedValueOnce(notFound())
      .mockResolvedValueOnce({
        contract_id: "con-award-18",
        promoted_from_feed_item: "feed-18",
      });
    vi.mocked(federation.entities.Contracts.create).mockRejectedValue(conflict());

    await expect(promoteFeedItem({
      id: "feed-18",
      external_id: "award-18",
      module: "MoneySweep-PR",
    })).resolves.toBe("con-award-18");
  });

  it("refuses to reuse a ledger record linked to another feed item", async () => {
    vi.mocked(federation.entities.Contracts.get).mockResolvedValue({
      contract_id: "con-award-19",
      promoted_from_feed_item: "different-feed-item",
    });

    await expect(promoteFeedItem({
      id: "feed-19",
      external_id: "award-19",
      module: "MoneySweep-PR",
    })).rejects.toThrow("is already linked to a different feed item");

    expect(federation.entities.Contracts.create).not.toHaveBeenCalled();
  });

  it("uses the feed identity as the stable fallback for AguaYLuz assets", async () => {
    vi.mocked(federation.entities.InfrastructureAssets.get).mockRejectedValue(notFound());
    vi.mocked(federation.entities.InfrastructureAssets.create).mockResolvedValue({
      asset_id: "asset-feed-feed-20",
    });

    await expect(promoteFeedItem({
      item_id: "feed-20",
      module: "AguaYLuz-PR",
      title: "Water pump",
    })).resolves.toBe("asset-feed-feed-20");

    expect(federation.entities.InfrastructureAssets.create).toHaveBeenCalledWith(expect.objectContaining({
      id: "asset-feed-feed-20",
      asset_id: "asset-feed-feed-20",
      promoted_from_feed_item: "feed-20",
    }));
  });

  it("reuses legacy AguaYLuz records whose storage ID differs from their asset ID", async () => {
    vi.mocked(federation.entities.InfrastructureAssets.get).mockRejectedValue(notFound());
    vi.mocked(federation.entities.InfrastructureAssets.filter).mockResolvedValue([{
      id: "legacy-random-id",
      asset_id: "asset-21",
      promoted_from_feed_item: "feed-21",
    }]);

    await expect(promoteFeedItem({
      id: "feed-21",
      external_id: "21",
      module: "AguaYLuz-PR",
    })).resolves.toBe("asset-21");

    expect(federation.entities.InfrastructureAssets.create).not.toHaveBeenCalled();
  });

  it("requires a stable feed identity before promotion", async () => {
    await expect(promoteFeedItem({ module: "MoneySweep-PR" })).rejects.toThrow(
      "Feed item has no stable identity to promote"
    );
  });
});
