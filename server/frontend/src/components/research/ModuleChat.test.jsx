import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ModuleChat from "./ModuleChat";

const mocks = vi.hoisted(() => ({
  authMe: vi.fn(),
  chatFilter: vi.fn(),
  chatCreate: vi.fn(),
  memoryFilter: vi.fn(),
  invokeLlm: vi.fn(),
}));

vi.mock("@/api/federationClient", () => ({
  federation: {
    auth: { me: mocks.authMe },
    entities: {
      ResearchChat: { filter: mocks.chatFilter, create: mocks.chatCreate },
      ResearchMemory: { filter: mocks.memoryFilter },
    },
    integrations: { Core: { InvokeLLM: mocks.invokeLlm } },
  },
  requireImplementedResponse: (result, feature) => {
    if (result?.status === "not_implemented" || result?.implemented === false) {
      throw new Error(result.reason || `${feature} is unavailable.`);
    }
    return result;
  },
}));

describe("ModuleChat", () => {
  beforeEach(() => {
    HTMLElement.prototype.scrollTo = vi.fn();
    mocks.authMe.mockResolvedValue(null);
    mocks.chatFilter.mockResolvedValue([]);
    mocks.memoryFilter.mockResolvedValue([]);
    mocks.chatCreate.mockResolvedValue({ id: "message-1" });
    mocks.invokeLlm.mockReset();
  });

  it("surfaces an unavailable LLM instead of saving a diagnostic stub as an assistant reply", async () => {
    const reason = "External integration services are not provisioned.";
    mocks.invokeLlm.mockResolvedValue({
      status: "not_implemented",
      implemented: false,
      reason,
    });
    render(
      <ModuleChat
        module="Hub"
        scopeLine="the Hub"
        webGrounded={false}
      />,
    );

    const input = screen.getByPlaceholderText("Message the Hub assistant…");
    await waitFor(() => expect(mocks.chatFilter).toHaveBeenCalled());
    fireEvent.change(input, { target: { value: "Find a lead" } });
    fireEvent.click(screen.getAllByRole("button").at(-1));

    expect(await screen.findByRole("alert")).toHaveTextContent(reason);
    expect(mocks.chatCreate).not.toHaveBeenCalled();
    expect(input).toHaveValue("Find a lead");
  });
});
