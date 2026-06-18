"use client";

import { useEffect, useRef, useState } from "react";
import { AppHeader } from "@/components/layout/AppHeader";
import { ProcessPanel } from "@/components/research/ProcessPanel";
import { ResearchInput } from "@/components/research/ResearchInput";
import { ResourceMap } from "@/components/research/ResourceMap";
import { ReportViewer } from "@/components/report/ReportViewer";
import { useResearch } from "@/hooks/useResearch";
import { cn } from "@/lib/utils";

type ActiveTab = "map" | "report";

function useElapsed(startedAt: number | null): string {
  const [elapsed, setElapsed] = useState(0);
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (startedAt === null) { setElapsed(0); return; }
    ref.current = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => { if (ref.current) clearInterval(ref.current); };
  }, [startedAt]);

  if (elapsed < 60) return `${elapsed}s`;
  const m = Math.floor(elapsed / 60), s = elapsed % 60;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export default function HomePage() {
  const { phase, generate, reset } = useResearch();
  const [activeTab, setActiveTab] = useState<ActiveTab>("map");
  const elapsed = useElapsed(phase.kind === "running" ? phase.startedAt : null);

  const isIdle     = phase.kind === "idle";
  const isRunning  = phase.kind === "running";
  const isComplete = phase.kind === "complete";
  const isError    = phase.kind === "error";

  // When a new research starts, reset to the resource map tab.
  useEffect(() => {
    if (phase.kind === "running") setActiveTab("map");
  }, [phase.kind]);

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <AppHeader onNew={isComplete || isError ? reset : undefined} />

      {/* ---- Idle: centred input ---- */}
      {isIdle && (
        <main className="flex flex-1 items-center justify-center px-4 py-16">
          <div className="w-full max-w-2xl">
            <ResearchInput onSubmit={(q, m) => generate(q, m)} isLoading={false} />
          </div>
        </main>
      )}

      {/* ---- Active: query bar + two-column layout ---- */}
      {(isRunning || isComplete || isError) && (
        <main className="flex flex-1 flex-col overflow-hidden">
          {/* Query bar */}
          <div className="border-b bg-muted/40 px-6 py-3 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <ResearchInput
                onSubmit={(q, m) => generate(q, m)}
                isLoading={isRunning}
                defaultValue={
                  phase.kind === "running" || phase.kind === "complete" || phase.kind === "error"
                    ? phase.query
                    : ""
                }
                compact
              />
            </div>
            {isRunning && (
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {elapsed}
              </span>
            )}
          </div>

          {/* Two-column layout */}
          <div className="flex flex-1 overflow-hidden">

            {/* ---- Left sidebar: process + agent log + sources ---- */}
            <aside className="flex w-80 shrink-0 flex-col overflow-hidden border-r bg-muted/20">
              {(isRunning || isComplete) &&
                (phase.kind === "running" || phase.kind === "complete") && (
                  <ProcessPanel
                    steps={phase.steps}
                    agentLog={phase.agentLog}
                    citations={
                      phase.kind === "complete"
                        ? phase.output.citations
                        : undefined
                    }
                  />
                )}

              {isError && (
                <div className="p-4">
                  <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                    {phase.message}
                  </div>
                </div>
              )}
            </aside>

            {/* ---- Main area ---- */}
            <div className="flex flex-1 flex-col overflow-hidden">

              {/* Tab bar (only when complete) */}
              {isComplete && (
                <div className="flex shrink-0 border-b bg-muted/10 px-2">
                  {(["map", "report"] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={cn(
                        "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors capitalize",
                        activeTab === tab
                          ? "border-primary text-foreground"
                          : "border-transparent text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {tab === "map" ? "Resource Map" : "Report"}
                    </button>
                  ))}
                </div>
              )}

              {/* Scrollable content */}
              <div className="flex-1 overflow-y-auto">

                {/* Running: resource map */}
                {isRunning && phase.kind === "running" && (
                  <ResourceMap
                    query={phase.query}
                    resources={phase.resources}
                    isRunning
                  />
                )}

                {/* Complete: tabbed between map and report */}
                {isComplete && phase.kind === "complete" && (
                  <>
                    {activeTab === "map" && (
                      <ResourceMap
                        query={phase.query}
                        resources={phase.resources}
                        isRunning={false}
                      />
                    )}
                    {activeTab === "report" && (
                      <div className="px-8 py-6">
                        <ReportViewer output={phase.output} />
                      </div>
                    )}
                  </>
                )}

                {/* Error */}
                {isError && (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    Research could not be completed. Try a different query.
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      )}
    </div>
  );
}
