export type HumanAction = "approve" | "revise" | "cancel";

export type Source = { title: string; url: string };

export type Review = {
  type: "final_answer_review";
  final_answer: string;
  critic_score: number;
  human_revision_count: number;
  max_human_revisions: number;
  status: "awaiting_human_review" | "revision_limit_reached";
};

export type WorkflowState = {
  final_answer: string;
  iteration: number;
  human_revision_count: number;
  status: "approved" | "cancelled";
  sources: Source[];
};

export type StreamEvent =
  | { type: "started"; thread_id: string; thread_token: string }
  | { type: "node"; node: string; data: Record<string, unknown> }
  | { type: "approval_required"; thread_id: string; review: Review }
  | { type: "complete"; thread_id: string; state: WorkflowState }
  | { type: "error"; message: string };
