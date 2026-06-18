import { Bot, Check, Circle, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { SourceList } from "@/components/research/SourceList";
import type { AgentLogEntry, AgentStep, ReportCitation } from "@/lib/types";

const STEP_ICON: Record<AgentStep["status"], React.ReactNode> = {
  pending:  <Circle   className="h-3.5 w-3.5 text-muted-foreground/30" />,
  running:  <Loader2  className="h-3.5 w-3.5 animate-spin text-primary" />,
  complete: <Check    className="h-3.5 w-3.5 text-emerald-600" />,
  failed:   <X        className="h-3.5 w-3.5 text-destructive" />,
};

const AGENT_COLOR: Record<AgentLogEntry["agent"], string> = {
  researcher: "text-blue-600  dark:text-blue-400",
  writer:     "text-violet-600 dark:text-violet-400",
  critic:     "text-amber-600  dark:text-amber-400",
  system:     "text-muted-foreground",
};

const AGENT_LABEL: Record<AgentLogEntry["agent"], string> = {
  researcher: "Researcher",
  writer:     "Writer",
  critic:     "Critic",
  system:     "System",
};

interface ProcessPanelProps {
  steps: AgentStep[];
  agentLog: AgentLogEntry[];
  citations?: ReportCitation[];
}

export function ProcessPanel({ steps, agentLog, citations }: ProcessPanelProps) {
  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* ---- Process steps ---- */}
      <div className="p-4 shrink-0">
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Process
        </p>
        <ol className="space-y-3">
          {steps.map((step, i) => (
            <li key={step.name} className="flex items-start gap-2.5">
              <div className="flex flex-col items-center">
                <span className="flex h-5 w-5 items-center justify-center">
                  {STEP_ICON[step.status]}
                </span>
                {i < steps.length - 1 && (
                  <div
                    className={cn(
                      "mt-0.5 h-5 w-px",
                      step.status === "complete" ? "bg-emerald-200 dark:bg-emerald-900" : "bg-border",
                    )}
                  />
                )}
              </div>
              <span
                className={cn(
                  "pt-0.5 text-sm leading-snug",
                  step.status === "pending"  && "text-muted-foreground/50",
                  step.status === "running"  && "font-medium text-foreground",
                  step.status === "complete" && "text-foreground",
                  step.status === "failed"   && "text-destructive",
                )}
              >
                {step.label}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <Separator />

      {/* ---- Agent log ---- */}
      <div className="flex-1 min-h-0 p-4">
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Agent Log
        </p>

        {agentLog.length === 0 ? (
          <p className="text-xs italic text-muted-foreground/50">Waiting for agents...</p>
        ) : (
          <div className="space-y-3">
            {agentLog.map((entry) => (
              <div
                key={entry.id}
                className="flex items-start gap-2 animate-in fade-in slide-in-from-bottom-1 duration-300"
              >
                <Bot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/60" />
                <div className="flex-1 min-w-0">
                  <span className={cn("text-[10px] font-bold uppercase tracking-wide", AGENT_COLOR[entry.agent])}>
                    {AGENT_LABEL[entry.agent]}
                  </span>
                  <p className="mt-0.5 text-xs leading-relaxed text-foreground/75">{entry.message}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---- Citations (shown when research is complete) ---- */}
      {citations && citations.length > 0 && (
        <>
          <Separator />
          <div className="p-4 shrink-0">
            <SourceList citations={citations} />
          </div>
        </>
      )}
    </div>
  );
}
