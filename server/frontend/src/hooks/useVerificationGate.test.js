import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { federation } from "@/api/federationClient";
import { useEntityData } from "@/hooks/useEntityData";
import { useVerificationGate } from "@/hooks/useVerificationGate";

vi.mock("@/api/federationClient", () => ({
  federation: { auth: { me: vi.fn() } },
}));

vi.mock("@/hooks/useEntityData", () => ({
  useEntityData: vi.fn(),
}));

describe("useVerificationGate", () => {
  const item = { id: "feed-1", verification_note: "existing note" };
  let update;

  beforeEach(() => {
    update = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useEntityData).mockReturnValue({
      rows: [],
      isLoading: false,
      update,
      saving: false,
    });
  });

  it("does not verify a record if reviewer identity cannot be resolved", async () => {
    vi.mocked(federation.auth.me).mockRejectedValue(new Error("Authentication unavailable"));
    const { result } = renderHook(() => useVerificationGate());

    await expect(act(() => result.current.verify(item))).rejects.toThrow("Authentication unavailable");

    expect(update).not.toHaveBeenCalled();
  });

  it("records the authenticated reviewer with the verification update", async () => {
    vi.mocked(federation.auth.me).mockResolvedValue({ email: "analyst@example.test" });
    const { result } = renderHook(() => useVerificationGate());

    await act(() => result.current.verify(item, "Reviewed source"));

    expect(update).toHaveBeenCalledWith("feed-1", expect.objectContaining({
      sync_status: "Verified",
      verified_by: "analyst@example.test",
      verification_note: "Reviewed source",
    }));
  });
});
