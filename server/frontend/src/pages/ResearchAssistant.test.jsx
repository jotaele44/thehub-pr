import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ResearchAssistant from "./ResearchAssistant";

const mocks = vi.hoisted(() => ({
  invokeLlm: vi.fn(),
}));

vi.mock("@/api/federationClient", () => ({
  federation: { integrations: { Core: { InvokeLLM: mocks.invokeLlm } } },
  requireImplementedResponse: (result, feature) => {
    if (result?.status === "not_implemented" || result?.implemented === false) {
      throw new Error(result.reason || `${feature} is unavailable.`);
    }
    return result;
  },
}));

vi.mock("@/components/research/ModuleChat", () => ({ default: () => null }));
vi.mock("@/components/research/OperatorChat", () => ({ default: () => null }));

describe("ResearchAssistant", () => {
  beforeEach(() => {
    mocks.invokeLlm.mockReset();
  });

  it("shows an unavailable provider error instead of an empty research result", async () => {
    const reason = "External integration services are not provisioned.";
    mocks.invokeLlm.mockResolvedValue({
      status: "not_implemented",
      implemented: false,
      reason,
    });
    render(<ResearchAssistant />);

    const researchTab = screen.getByRole("tab", { name: "Structured Research" });
    fireEvent.mouseDown(researchTab, { button: 0 });
    await waitFor(() => expect(researchTab).toHaveAttribute("aria-selected", "true"));
    fireEvent.change(
      screen.getByPlaceholderText(/Describe what to research/),
      { target: { value: "Recent public works contracts" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Run Research" }));

    await waitFor(() => expect(mocks.invokeLlm).toHaveBeenCalled());
    expect(await screen.findByRole("alert")).toHaveTextContent(reason);
    expect(screen.queryByText("No leads returned")).not.toBeInTheDocument();
  });
});
