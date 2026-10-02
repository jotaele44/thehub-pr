import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "@/components/ui/use-toast";
import { useVerificationGate } from "@/hooks/useVerificationGate";
import VerificationGatePanel from "@/components/dashboard/VerificationGatePanel";

vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
}));

vi.mock("@/hooks/useVerificationGate", () => ({
  useVerificationGate: vi.fn(),
}));

describe("VerificationGatePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useVerificationGate).mockReturnValue({
      pending: [{
        id: "feed-1",
        module: "MoneySweep-PR",
        sync_status: "New",
        title: "Award",
        feed_item_id: "award-1",
      }],
      counts: { moneysweep: 1, aguayluz: 0, verifiedReady: 0 },
      isLoading: false,
      saving: false,
      verify: vi.fn().mockRejectedValue(new Error("Reviewer identity unavailable")),
      reject: vi.fn(),
    });
  });

  it("shows a visible failure when reviewer attribution prevents verification", async () => {
    render(<VerificationGatePanel />);
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() => {
      expect(toast).toHaveBeenCalledWith({
        title: "Verification failed: Reviewer identity unavailable",
        variant: "destructive",
      });
    });
  });
});
