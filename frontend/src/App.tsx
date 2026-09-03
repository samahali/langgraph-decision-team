import { type SubmitEvent, useState } from "react";

import { ResultPanel } from "@/components/result-panel";
import { ReviewPanel } from "@/components/review-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { WorkflowProgress } from "@/components/workflow-progress";
import { useDecisionWorkflow } from "@/hooks/use-decision-workflow";

export default function App() {
  const [question, setQuestion] = useState("");
  const workflow = useDecisionWorkflow();

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = question.trim();
    if (value) await workflow.start(value);
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-4 pb-20 sm:px-6">
      <header className="flex h-20 items-center justify-between border-b">
        <a className="flex items-center gap-3 font-display font-bold" href="/" aria-label="Decision Team home">
          <span className="grid size-9 place-items-center rounded-full bg-primary text-xs tracking-wider text-primary-foreground">DT</span>
          Decision Team
        </a>
        <span className="hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
          <i className="size-2 rounded-full bg-emerald-500 ring-4 ring-emerald-500/10" />
          Human-controlled AI
        </span>
      </header>

      <section className="grid items-end gap-10 py-14 lg:grid-cols-[1.15fr_.85fr] lg:gap-20 lg:py-24">
        <div>
          <p className="eyebrow">Evidence first. You decide.</p>
          <h1 className="max-w-3xl font-display text-5xl font-semibold leading-[1.02] tracking-[-.055em] sm:text-6xl lg:text-7xl">
            Turn hard questions into <em className="not-italic text-primary">defensible decisions.</em>
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-7 text-muted-foreground">
            A focused AI team plans, researches live sources, challenges its draft, then waits for your approval.
          </p>
        </div>

        <Card className="shadow-xl shadow-foreground/5">
          <CardContent className="p-6">
            <form onSubmit={submit} className="space-y-3" aria-busy={workflow.isRunning}>
              <label className="block text-sm font-semibold" htmlFor="question">Decision or question</label>
              <Textarea
                id="question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Should we build, buy, or partner for our analytics platform?"
                rows={5}
                disabled={workflow.isRunning}
              />
              <Button className="w-full" size="lg" disabled={workflow.isRunning || !question.trim()}>
                {workflow.isRunning ? "Team working…" : "Start decision workflow"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </section>

      <div className="space-y-5">
        {(workflow.completedNodes.length > 0 || workflow.isRunning) && (
          <WorkflowProgress
            completedNodes={workflow.completedNodes}
            isRunning={workflow.isRunning}
            threadId={workflow.threadId}
          />
        )}

        {workflow.review && (
          <ReviewPanel
            key={workflow.review.final_answer}
            isRunning={workflow.isRunning}
            onDecision={workflow.decide}
            review={workflow.review}
          />
        )}

        {workflow.result && <ResultPanel result={workflow.result} />}

        {workflow.error && (
          <p className="sticky bottom-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" role="alert">
            {workflow.error}
          </p>
        )}
      </div>
    </main>
  );
}
