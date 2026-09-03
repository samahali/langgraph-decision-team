import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const nodes = ["planner", "researcher", "writer", "critic", "finalizer", "human_review"];

type WorkflowProgressProps = {
  completedNodes: string[];
  isRunning: boolean;
  threadId: string;
};

export function WorkflowProgress({ completedNodes, isRunning, threadId }: WorkflowProgressProps) {
  return (
    <Card aria-live="polite">
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <p className="eyebrow">Live workflow</p>
          <CardTitle>Decision room</CardTitle>
        </div>
        {threadId && <Badge variant="outline">{threadId.slice(0, 8)}</Badge>}
      </CardHeader>
      <CardContent>
        <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {nodes.map((node, index) => {
            const done = completedNodes.includes(node);
            const active =
              !done && nodes.slice(0, index).every((item) => completedNodes.includes(item));

            return (
              <li
                className={cn(
                  "flex min-h-20 flex-col gap-2 rounded-xl bg-muted p-3 text-xs capitalize text-muted-foreground",
                  done && "bg-primary/10 text-primary",
                  active && isRunning && "bg-accent text-accent-foreground",
                )}
                key={node}
              >
                <span
                  className={cn(
                    "grid size-6 place-items-center rounded-full border text-[10px]",
                    done && "border-primary bg-primary text-primary-foreground",
                    active && isRunning && "animate-pulse border-accent-foreground",
                  )}
                >
                  {done ? <Check className="size-3.5" aria-hidden="true" /> : index + 1}
                </span>
                {node.replace("_", " ")}
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}
