import { useCallback, useEffect, useRef, useState } from "react";

import { consumeWorkflowStream } from "@/lib/api";
import type { HumanAction, Review, StreamEvent, WorkflowState } from "@/types/workflow";

export function useDecisionWorkflow() {
  const [threadId, setThreadId] = useState("");
  const [threadToken, setThreadToken] = useState("");
  const [completedNodes, setCompletedNodes] = useState<string[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const [result, setResult] = useState<WorkflowState | null>(null);
  const [error, setError] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const handleEvent = useCallback((event: StreamEvent) => {
    if (event.type === "started") {
      setThreadId(event.thread_id);
      setThreadToken(event.thread_token);
    } else if (event.type === "node") {
      setCompletedNodes((current) => [...new Set([...current, event.node])]);
    } else if (event.type === "approval_required") {
      setThreadId(event.thread_id);
      setReview(event.review);
      setCompletedNodes((current) => [...new Set([...current, "human_review"])]);
    } else if (event.type === "complete") {
      setThreadId(event.thread_id);
      setReview(null);
      setResult(event.state);
    } else {
      setError(event.message);
    }
  }, []);

  const execute = useCallback(
    async (path: string, body: Record<string, unknown>, token?: string) => {
      controller.current?.abort();
      const requestController = new AbortController();
      controller.current = requestController;
      setIsRunning(true);
      setError("");

      try {
        await consumeWorkflowStream(path, body, handleEvent, requestController.signal, token);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Unexpected workflow error.");
      } finally {
        if (controller.current === requestController) {
          setIsRunning(false);
          controller.current = null;
        }
      }
    },
    [handleEvent],
  );

  const start = useCallback(
    async (question: string) => {
      setCompletedNodes([]);
      setReview(null);
      setResult(null);
      setThreadToken("");
      await execute("/runs", { question });
    },
    [execute],
  );

  const decide = useCallback(
    async (action: HumanAction, feedback = "") => {
      if (!threadId || !threadToken) return;
      await execute(`/runs/${encodeURIComponent(threadId)}/approval`, {
        action,
        feedback,
      }, threadToken);
    },
    [execute, threadId, threadToken],
  );

  return {
    completedNodes,
    decide,
    error,
    isRunning,
    result,
    review,
    start,
    threadId,
  };
}
