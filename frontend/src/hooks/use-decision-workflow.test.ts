import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useDecisionWorkflow } from "@/hooks/use-decision-workflow";
import { consumeWorkflowStream } from "@/lib/api";

vi.mock("@/lib/api", () => ({ consumeWorkflowStream: vi.fn() }));

const consumeMock = vi.mocked(consumeWorkflowStream);
const review = {
  type: "final_answer_review" as const,
  final_answer: "Reviewed answer",
  critic_score: 90,
  human_revision_count: 0,
  max_human_revisions: 2,
  status: "awaiting_human_review" as const,
};

beforeEach(() => consumeMock.mockReset());

describe("useDecisionWorkflow", () => {
  it("keeps review available when approval request fails", async () => {
    consumeMock.mockImplementationOnce(async (_path, _body, onEvent) => {
      onEvent({ type: "started", thread_id: "thread-1", thread_token: "token-1" });
      onEvent({ type: "approval_required", thread_id: "thread-1", review });
    });
    const { result } = renderHook(() => useDecisionWorkflow());

    await act(() => result.current.start("Question"));
    expect(result.current.review).toEqual(review);

    consumeMock.mockRejectedValueOnce(new Error("Network unavailable"));
    await act(() => result.current.decide("approve"));

    expect(result.current.review).toEqual(review);
    expect(result.current.error).toBe("Network unavailable");
    expect(consumeMock).toHaveBeenLastCalledWith(
      "/runs/thread-1/approval",
      { action: "approve", feedback: "" },
      expect.any(Function),
      expect.any(AbortSignal),
      "token-1",
    );
  });
});
