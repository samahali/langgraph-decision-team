import { useState } from "react";

import { MarkdownArticle } from "@/components/markdown-article";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { HumanAction, Review } from "@/types/workflow";

type ReviewPanelProps = {
  isRunning: boolean;
  onDecision: (action: HumanAction, feedback?: string) => Promise<void>;
  review: Review;
};

export function ReviewPanel({ isRunning, onDecision, review }: ReviewPanelProps) {
  const [feedback, setFeedback] = useState("");
  const [feedbackError, setFeedbackError] = useState("");
  const limitReached = review.human_revision_count >= review.max_human_revisions;

  async function submit(action: HumanAction) {
    if (action === "revise" && !feedback.trim()) {
      setFeedbackError("Add revision feedback before requesting revision.");
      return;
    }
    setFeedbackError("");
    await onDecision(action, feedback.trim());
  }

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <p className="eyebrow">Approval required</p>
          <CardTitle>Review final answer</CardTitle>
        </div>
        <Badge>{review.critic_score}/100</Badge>
      </CardHeader>
      <CardContent className="space-y-5">
        {limitReached && (
          <p className="rounded-lg bg-accent px-4 py-3 text-sm text-accent-foreground">
            Human revision limit reached. Approve or cancel this answer.
          </p>
        )}
        <div className="max-h-96 overflow-auto rounded-xl border-l-4 border-accent-foreground bg-muted/60 p-5">
          <MarkdownArticle>{review.final_answer}</MarkdownArticle>
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="feedback">
            Revision feedback
          </label>
          <Textarea
            id="feedback"
            value={feedback}
            onChange={(event) => setFeedback(event.target.value)}
            placeholder="What should be changed?"
            rows={3}
            disabled={limitReached || isRunning}
            aria-invalid={Boolean(feedbackError)}
            aria-describedby={feedbackError ? "feedback-error" : undefined}
          />
          <div className="mt-2 flex items-center justify-between gap-4 text-xs text-muted-foreground">
            <span id="feedback-error" className="text-destructive">{feedbackError}</span>
            <span>Human revisions: {review.human_revision_count}/{review.max_human_revisions}</span>
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button variant="destructive" onClick={() => submit("cancel")} disabled={isRunning}>
            Cancel
          </Button>
          <div className="flex flex-1 flex-col justify-end gap-2 sm:flex-row">
            <Button variant="secondary" onClick={() => submit("revise")} disabled={limitReached || isRunning}>
              Request revision
            </Button>
            <Button onClick={() => submit("approve")} disabled={isRunning}>Approve answer</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
