import type { StreamEvent } from "@/types/workflow";

const API_URL = (
  import.meta.env.VITE_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export async function consumeWorkflowStream(
  path: string,
  body: Record<string, unknown>,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
  threadToken?: string,
): Promise<void> {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(`${API_URL}${normalizedPath}`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      ...(threadToken ? { "X-Thread-Token": threadToken } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  if (!response.body) {
    throw new Error("The server returned an empty response stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const emit = (frame: string) => {
    const data = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data) return;

    let event: StreamEvent;
    try {
      event = JSON.parse(data) as StreamEvent;
    } catch {
      throw new Error("Invalid workflow stream event.");
    }
    onEvent(event);
  };

  let finished = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        finished = true;
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";

      for (const frame of frames) emit(frame);
    }

    if (buffer.trim()) emit(buffer);
  } finally {
    if (!finished) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
