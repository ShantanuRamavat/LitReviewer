import { Check, Circle, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentStep } from "@/lib/types";

interface AgentActivityFeedProps {
  steps: AgentStep[];
}

const STATUS_ICON: Record<AgentStep["status"], React.ReactNode> = {
  pending: <Circle className="h-4 w-4 text-muted-foreground/40" />,
  running: <Loader2 className="h-4 w-4 animate-spin text-primary" />,
  complete: <Check className="h-4 w-4 text-emerald-600" />,
  failed: <X className="h-4 w-4 text-destructive" />,
};

export function AgentActivityFeed({ steps }: AgentActivityFeedProps) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Agent Activity
      </p>

      <ol className="space-y-2">
        {steps.map((step, i) => (
          <li key={step.name} className="flex items-center gap-2.5">
            {/* Vertical connector line */}
            <div className="flex flex-col items-center">
              <span className="flex h-5 w-5 items-center justify-center">
                {STATUS_ICON[step.status]}
              </span>
              {i < steps.length - 1 && (
                <div
                  className={cn(
                    "mt-0.5 h-4 w-px",
                    step.status === "complete"
                      ? "bg-emerald-200"
                      : "bg-border",
                  )}
                />
              )}
            </div>

            <span
              className={cn(
                "text-sm",
                step.status === "pending" && "text-muted-foreground/60",
                step.status === "running" && "font-medium text-foreground",
                step.status === "complete" && "text-foreground",
                step.status === "failed" && "text-destructive",
              )}
            >
              {step.label}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
