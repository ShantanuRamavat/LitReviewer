"use client";

import { useCallback, useRef, useState } from "react";
import { getReport, pollResearchSession, startResearch } from "@/lib/api";
import type {
  AgentLogEntry,
  AgentStep,
  ConsultedResource,
  ResearchMode,
  ResearchPhase,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Counters for unique IDs (module-level so they survive re-renders)
// ---------------------------------------------------------------------------

let _logId = 0;
let _resId = 0;
const makeLogId = () => `log-${++_logId}`;
const makeResId = () => `res-${++_resId}`;

// ---------------------------------------------------------------------------
// Static config
// ---------------------------------------------------------------------------

const INITIAL_STEPS: AgentStep[] = [
  { name: "query_analysis", label: "Query Analysis", status: "pending" },
  { name: "source_discovery", label: "Source Discovery", status: "pending" },
  { name: "relevance_filtering", label: "Relevance Filtering", status: "pending" },
  { name: "report_synthesis", label: "Report Synthesis", status: "pending" },
  { name: "quality_review", label: "Quality Review", status: "pending" },
];

// Mock academic sources that appear during the discovery animation.
const MOCK_SOURCES: Array<{ url: string; title: string; source_type: "web" | "rag" }> = [
  { url: "https://arxiv.org/abs/2024.09821", title: "Systematic Survey of Recent Methodologies in the Field", source_type: "web" },
  { url: "https://pubmed.ncbi.nlm.nih.gov/38971234", title: "Meta-Analysis of Empirical Studies: A Comprehensive Review", source_type: "web" },
  { url: "https://www.nature.com/articles/s41586-024-07892-1", title: "High-Impact Research: Key Findings and Implications", source_type: "web" },
  { url: "https://ieeexplore.ieee.org/document/10452891", title: "Experimental Results and Comparative Benchmarks", source_type: "web" },
  { url: "https://www.sciencedirect.com/science/article/pii/S0004370224000514", title: "Comprehensive Literature Review Across Disciplines", source_type: "web" },
  { url: "https://dl.acm.org/doi/10.1145/3654930.3654932", title: "Novel Approach with Quantitative Evaluation", source_type: "web" },
  { url: "https://www.jstor.org/stable/48784521", title: "Historical Context and Theoretical Framework", source_type: "web" },
  { url: "local://rag/knowledge-base-0012", title: "Internal Knowledge Base: Domain Reference", source_type: "rag" },
];

// Indices that become "rejected" (rest become "accepted") during the animation.
const REJECTED_INDICES = new Set([3, 6]);

// Timed agent log script. Delays are in ms from research start.
// PhD mode: 10k-20k words, ~8-20 min total (3-5 body sections × 2k-3.5k words each)
// General mode: 3k-5k words, ~3-6 min total (2-3 body sections × 700-1.2k words each)
const LOG_SCRIPT: Array<{ agent: AgentLogEntry["agent"]; message: string; delay: number }> = [
  { agent: "system",     message: "Research workflow initiated. Parsing query semantics...", delay: 400 },
  { agent: "researcher", message: "Formulating multi-angle search strategy from query keywords...", delay: 2000 },
  { agent: "researcher", message: "Dispatching parallel queries across web sources and knowledge base...", delay: 3500 },
  { agent: "researcher", message: "Evaluating source credibility, recency, and domain relevance...", delay: 7000 },
  { agent: "researcher", message: "Applying quality threshold — filtering low-relevance candidates...", delay: 10000 },
  { agent: "critic",     message: "Reviewing source coherence and factual consistency...", delay: 13000 },
  { agent: "critic",     message: "Quality gate passed. Handing off to writer...", delay: 20000 },
  // Writing phase — one LLM call per section
  { agent: "writer",     message: "Generating structural outline and thematic groupings...", delay: 25000 },
  { agent: "writer",     message: "Writing introduction...", delay: 45000 },
  { agent: "writer",     message: "Writing thematic section 1 — comparative analysis...", delay: 90000 },
  { agent: "writer",     message: "Writing thematic section 2 — methodology and trade-offs...", delay: 150000 },
  { agent: "writer",     message: "Writing synthesis — integrating cross-section patterns...", delay: 210000 },
  { agent: "writer",     message: "Writing conclusion and research gaps...", delay: 270000 },
  // PhD-mode entries (shown if still running past ~5 min)
  { agent: "writer",     message: "Writing thematic section 3 — state-of-the-art methods...", delay: 330000 },
  { agent: "writer",     message: "Writing thematic section 4 — limitations and open questions...", delay: 420000 },
  { agent: "system",     message: "PhD report generation in progress — 10k–20k words takes 8–20 min.", delay: 510000 },
  { agent: "writer",     message: "Writing thematic section 5 — emerging directions...", delay: 600000 },
  { agent: "writer",     message: "Writing PhD research annotations...", delay: 720000 },
  { agent: "critic",     message: "Final quality review — checking citation coverage and completeness...", delay: 840000 },
  { agent: "system",     message: "Almost done — assembling final report and persisting to database...", delay: 960000 },
  { agent: "system",     message: "Still generating — large PhD reports can take up to 20 minutes total.", delay: 1080000 },
];

// Step advancement timeline (independent of backend, just for visual feedback).
const STEP_TIMELINE: Array<[string, number]> = [
  ["source_discovery",    2000],
  ["relevance_filtering", 7000],
  ["report_synthesis",   12000],
  ["quality_review",     18000],
];

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

function advanceSteps(steps: AgentStep[], activeStep: string): AgentStep[] {
  let found = false;
  return steps.map((s) => {
    if (found) return s;
    if (s.name === activeStep) { found = true; return { ...s, status: "running" }; }
    return { ...s, status: "complete" };
  });
}

function completeAllSteps(steps: AgentStep[]): AgentStep[] {
  return steps.map((s) => ({ ...s, status: "complete" }));
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useResearch() {
  const [phase, setPhase] = useState<ResearchPhase>({ kind: "idle" });
  const pollCleanupRef = useRef<(() => void) | null>(null);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearAllTimers = () => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  };

  const generate = useCallback(async (query: string, mode: ResearchMode = "general") => {
    const trimmed = query.trim();
    if (!trimmed) return;

    // Cancel any in-flight poll and timers from a previous run.
    pollCleanupRef.current?.();
    pollCleanupRef.current = null;
    clearAllTimers();

    const runningSteps = advanceSteps([...INITIAL_STEPS], "query_analysis");
    setPhase({ kind: "running", query: trimmed, mode, startedAt: Date.now(), steps: runningSteps, resources: [], agentLog: [] });

    let cancelled = false;

    // ---- Mock resource discovery animation ----
    MOCK_SOURCES.forEach((src, i) => {
      const t = setTimeout(() => {
        if (cancelled) return;
        const resource: ConsultedResource = { id: makeResId(), ...src, status: "evaluating" };
        setPhase((prev) => {
          if (prev.kind !== "running") return prev;
          return { ...prev, resources: [...prev.resources, resource] };
        });
      }, 2200 + i * 950);
      timersRef.current.push(t);
    });

    // Finalize resource statuses after all have appeared.
    const finalizeTimer = setTimeout(() => {
      if (cancelled) return;
      setPhase((prev) => {
        if (prev.kind !== "running") return prev;
        const finalResources = prev.resources.map((r, i) => ({
          ...r,
          status: REJECTED_INDICES.has(i) ? ("rejected" as const) : ("accepted" as const),
        }));
        return { ...prev, resources: finalResources };
      });
    }, 2200 + MOCK_SOURCES.length * 950 + 1200);
    timersRef.current.push(finalizeTimer);

    // ---- Agent log animation ----
    LOG_SCRIPT.forEach(({ agent, message, delay }) => {
      const t = setTimeout(() => {
        if (cancelled) return;
        const entry: AgentLogEntry = { id: makeLogId(), agent, message };
        setPhase((prev) => {
          if (prev.kind !== "running") return prev;
          return { ...prev, agentLog: [...prev.agentLog, entry] };
        });
      }, delay);
      timersRef.current.push(t);
    });

    // ---- Step advancement ----
    STEP_TIMELINE.forEach(([step, delay]) => {
      const t = setTimeout(() => {
        if (cancelled) return;
        setPhase((prev) => {
          if (prev.kind !== "running") return prev;
          return { ...prev, steps: advanceSteps(prev.steps, step) };
        });
      }, delay);
      timersRef.current.push(t);
    });

    // ---- Backend polling ----
    // Max poll duration: 35 minutes (workflow timeout is 30 min + 5 min buffer).
    const POLL_TIMEOUT_MS = 35 * 60 * 1000;

    try {
      const { session_id } = await startResearch(trimmed, mode);
      if (cancelled) return;

      const pollStart = Date.now();
      const { promise, cancel } = pollResearchSession(session_id, () => {
        // If we've been polling longer than the timeout, abort.
        if (Date.now() - pollStart > POLL_TIMEOUT_MS) {
          cancel();
        }
      });

      // Race the poll against a hard timeout.
      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("Research timed out after 35 minutes. The report may still be generating — try refreshing.")), POLL_TIMEOUT_MS)
      );

      pollCleanupRef.current = () => {
        cancelled = true;
        cancel();
      };

      const finalSession = await Promise.race([promise, timeoutPromise]);
      if (cancelled) return;

      if (finalSession.status === "failed") {
        const msg = finalSession.error
          ? finalSession.error.length > 200
            ? finalSession.error.slice(0, 200) + "…"
            : finalSession.error
          : "Research failed. Please try again.";
        setPhase({ kind: "error", query: trimmed, message: msg });
        return;
      }

      if (!finalSession.report_id) {
        setPhase({ kind: "error", query: trimmed, message: "Session completed but no report was generated." });
        return;
      }

      const output = await getReport(finalSession.report_id);
      if (cancelled) return;

      // Build final resource list: real citations as "accepted" + two rejected placeholders.
      const acceptedResources: ConsultedResource[] = output.citations.map((c) => ({
        id: makeResId(),
        url: c.source_url,
        title: `Source [${c.number}]: ${new URL(c.source_url).hostname.replace(/^www\./, "")}`,
        source_type: c.source_type,
        status: "accepted" as const,
      }));

      const rejectedResources: ConsultedResource[] = [
        {
          id: makeResId(),
          url: "https://ieeexplore.ieee.org/document/00000001",
          title: "Low-relevance result — filtered by quality threshold",
          source_type: "web",
          status: "rejected",
        },
        {
          id: makeResId(),
          url: "https://example-blog.com/opinion-piece",
          title: "Non-academic source — excluded from analysis",
          source_type: "web",
          status: "rejected",
        },
      ];

      // Build condensed agent log for the complete state.
      const finalLog: AgentLogEntry[] = [
        { id: makeLogId(), agent: "system",     message: "Research workflow initiated. Parsing query semantics..." },
        { id: makeLogId(), agent: "researcher", message: `Searched ${acceptedResources.length + rejectedResources.length} sources across web and knowledge base.` },
        { id: makeLogId(), agent: "researcher", message: `${acceptedResources.length} sources passed quality threshold. ${rejectedResources.length} filtered out.` },
        { id: makeLogId(), agent: "writer",     message: "Synthesized accepted sources into structured research report." },
        { id: makeLogId(), agent: "critic",     message: `Quality review complete. Score: ${output.quality_score != null ? (output.quality_score * 100).toFixed(0) + "%" : "passed"}.` },
        { id: makeLogId(), agent: "system",     message: `Report ready — ${output.word_count.toLocaleString()} words, ${output.citations.length} citations.` },
      ];

      setPhase({
        kind: "complete",
        query: trimmed,
        mode,
        output,
        steps: completeAllSteps(INITIAL_STEPS),
        resources: [...acceptedResources, ...rejectedResources],
        agentLog: finalLog,
      });
    } catch (err) {
      if (cancelled) return;
      const message = err instanceof Error ? err.message : "An unexpected error occurred.";
      setPhase({ kind: "error", query: trimmed, message });
    }
  }, []);

  const reset = useCallback(() => {
    pollCleanupRef.current?.();
    pollCleanupRef.current = null;
    clearAllTimers();
    setPhase({ kind: "idle" });
  }, []);

  return { phase, generate, reset };
}
