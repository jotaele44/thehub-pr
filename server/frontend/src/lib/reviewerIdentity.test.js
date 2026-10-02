import { describe, expect, it, vi } from "vitest";
import { federation } from "@/api/federationClient";
import { requireReviewerEmail } from "@/lib/reviewerIdentity";

vi.mock("@/api/federationClient", () => ({
  federation: { auth: { me: vi.fn() } },
}));

describe("requireReviewerEmail", () => {
  it("returns the authenticated reviewer email without surrounding whitespace", async () => {
    vi.mocked(federation.auth.me).mockResolvedValue({ email: " analyst@example.test " });

    await expect(requireReviewerEmail()).resolves.toBe("analyst@example.test");
  });

  it("fails when the authenticated user has no email identity", async () => {
    vi.mocked(federation.auth.me).mockResolvedValue({ email: "  " });

    await expect(requireReviewerEmail()).rejects.toThrow(
      "Signed-in reviewer identity unavailable; verification was not recorded."
    );
  });

  it("propagates reviewer lookup errors so callers do not record an unattributed verification", async () => {
    vi.mocked(federation.auth.me).mockRejectedValue(new Error("Authentication unavailable"));

    await expect(requireReviewerEmail()).rejects.toThrow("Authentication unavailable");
  });
});
