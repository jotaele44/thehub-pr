import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OperatorChat from "./OperatorChat";

const mocks = vi.hoisted(() => ({
  createConversation: vi.fn(),
  subscribeToConversation: vi.fn(),
}));

vi.mock("@/api/federationClient", () => ({
  federation: {
    agents: {
      createConversation: mocks.createConversation,
      subscribeToConversation: mocks.subscribeToConversation,
    },
  },
  requireImplementedResponse: (result, feature) => {
    if (result?.status === "not_implemented" || result?.implemented === false) {
      throw new Error(result.reason || `${feature} is unavailable.`);
    }
    return result;
  },
}));

describe("OperatorChat", () => {
  beforeEach(() => {
    HTMLElement.prototype.scrollTo = vi.fn();
    mocks.createConversation.mockReset();
    mocks.subscribeToConversation.mockReset();
    mocks.subscribeToConversation.mockReturnValue(vi.fn());
  });

  it("shows the diagnostic blocker and does not open a fake conversation", async () => {
    const reason = "The agent backend is not provisioned.";
    mocks.createConversation.mockResolvedValue({
      id: "compatibility-id",
      status: "not_implemented",
      implemented: false,
      reason,
    });
    render(<OperatorChat />);

    expect(await screen.findByRole("alert")).toHaveTextContent(reason);
    expect(mocks.subscribeToConversation).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText("Message the Research Operator…")).toBeDisabled();
    expect(screen.getByTitle("Attach files for the operator to read")).toBeDisabled();
  });

  it("re-subscribes after starting a new configured conversation", async () => {
    mocks.createConversation.mockResolvedValue({
      id: "conversation-1",
      messages: [],
    });
    render(<OperatorChat />);

    await waitFor(() => expect(mocks.subscribeToConversation).toHaveBeenCalledTimes(1));
    const oldUnsubscribe = mocks.subscribeToConversation.mock.results[0].value;

    fireEvent.click(screen.getByRole("button", { name: "New session" }));

    await waitFor(() => expect(mocks.createConversation).toHaveBeenCalledTimes(2));
    expect(mocks.subscribeToConversation).toHaveBeenCalledTimes(2);
    expect(oldUnsubscribe).toHaveBeenCalledOnce();
  });
});
