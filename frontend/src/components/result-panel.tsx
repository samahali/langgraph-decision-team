import { ExternalLink } from "lucide-react";

import { MarkdownArticle } from "@/components/markdown-article";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkflowState } from "@/types/workflow";

export function ResultPanel({ result }: { result: WorkflowState }) {
  const approved = result.status === "approved";

  return (
    <Card className="border-t-4 border-t-primary">
      <CardHeader>
        <p className="eyebrow">{approved ? "Approved answer" : "Workflow cancelled"}</p>
        <CardTitle>{approved ? "Recommendation" : "Reviewed answer"}</CardTitle>
      </CardHeader>
      <CardContent>
        <MarkdownArticle>{result.final_answer}</MarkdownArticle>
      </CardContent>
      <CardFooter className="flex-col items-start justify-between gap-4 border-t pt-5 text-xs text-muted-foreground sm:flex-row">
        <span>
          {result.iteration} critic {result.iteration === 1 ? "pass" : "passes"} · {result.human_revision_count} human revisions
        </span>
        <div className="flex flex-wrap gap-2">
          {result.sources.map((source) => (
            <Badge key={source.url} variant="outline">
              <a className="inline-flex items-center gap-1 hover:text-primary" href={source.url} target="_blank" rel="noreferrer">
                {source.title}<ExternalLink className="size-3" aria-hidden="true" />
              </a>
            </Badge>
          ))}
        </div>
      </CardFooter>
    </Card>
  );
}
