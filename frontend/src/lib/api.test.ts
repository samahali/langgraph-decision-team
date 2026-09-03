import { afterEach, describe, expect, it, vi } from "vitest";

import { consumeWorkflowStream } from "@/lib/api";
import type { StreamEvent } from "@/types/workflow";

afterEach(() => vi.unstubAllGlobals());

describe("consumeWorkflowStream", () => {
  it("parses chunked CRLF and multiline SSE events", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"node",\r\n'));
        controller.enqueue(
          encoder.encode('data: "node":"planner","data":{}}\r\n\r\n'),
        );
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const events: StreamEvent[] = [];

    await consumeWorkflowStream(
      "runs/thread-1/approval",
      { action: "approve" },
      (event) => events.push(event),
      undefined,
      "token-1",
    );

    expect(events).toEqual([{ type: "node", node: "planner", data: {} }]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/runs/thread-1/approval",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "text/event-stream",
          "X-Thread-Token": "token-1",
        }),
      }),
    );
  });

  it("rejects malformed stream events", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("data: not-json\n\n"));
        controller.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream)));

    await expect(
      consumeWorkflowStream("/runs", {}, () => undefined),
    ).rejects.toThrow("Invalid workflow stream event.");
  });
});
