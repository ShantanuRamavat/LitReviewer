import { Check, FileText, Globe, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConsultedResource } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// ---------------------------------------------------------------------------
// Resource card
// ---------------------------------------------------------------------------

function ResourceCard({ resource, index }: { resource: ConsultedResource; index: number }) {
  const isAccepted  = resource.status === "accepted";
  const isRejected  = resource.status === "rejected";
  const isEvaluating = resource.status === "evaluating" || resource.status === "discovering";

  return (
    <div
      className={cn(
        "rounded-lg border p-3 space-y-2 transition-all duration-500",
        "animate-in fade-in slide-in-from-bottom-3",
        isAccepted  && "border-emerald-200 bg-emerald-50/60 dark:border-emerald-800 dark:bg-emerald-950/30",
        isRejected  && "border-border bg-muted/20 opacity-50",
        isEvaluating && "border-amber-200 bg-amber-50/40 dark:border-amber-800 dark:bg-amber-950/20",
      )}
      style={{ animationDelay: `${index * 90}ms`, animationFillMode: "both" }}
    >
      {/* Header row: source type + domain + status badge */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          {resource.source_type === "web" ? (
            <Globe className="h-3 w-3 shrink-0 text-muted-foreground" />
          ) : (
            <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
          )}
          <span className="text-[11px] text-muted-foreground truncate">{hostnameOf(resource.url)}</span>
        </div>

        {isAccepted && (
          <span className="inline-flex items-center gap-0.5 rounded-full border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400 shrink-0">
            <Check className="h-2.5 w-2.5" /> Used
          </span>
        )}
        {isRejected && (
          <span className="inline-flex items-center gap-0.5 rounded-full border border-border px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground shrink-0">
            <X className="h-2.5 w-2.5" /> Filtered
          </span>
        )}
        {isEvaluating && (
          <span className="inline-flex items-center gap-0.5 rounded-full border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-400 shrink-0">
            <Loader2 className="h-2.5 w-2.5 animate-spin" /> Evaluating
          </span>
        )}
      </div>

      {/* Title */}
      <p className="text-xs font-medium leading-relaxed line-clamp-2">{resource.title}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Connector arrow (CSS-only)
// ---------------------------------------------------------------------------

function Arrow() {
  return (
    <div className="flex justify-center">
      <div className="flex flex-col items-center">
        <div className="h-6 w-px bg-border" />
        <div className="h-0 w-0 border-l-[5px] border-r-[5px] border-t-[7px] border-l-transparent border-r-transparent border-t-border" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ResourceMapProps {
  query: string;
  resources: ConsultedResource[];
  isRunning: boolean;
}

export function ResourceMap({ query, resources, isRunning }: ResourceMapProps) {
  const accepted   = resources.filter((r) => r.status === "accepted");
  const rejected   = resources.filter((r) => r.status === "rejected");
  const evaluating = resources.filter((r) => r.status === "evaluating" || r.status === "discovering");

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      {/* ---- Section label ---- */}
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Resource Discovery Flow
      </p>

      {/* ---- Query node ---- */}
      <div className="flex justify-center">
        <div className="w-full max-w-lg rounded-xl border border-primary/25 bg-primary/5 px-5 py-3.5 text-center shadow-sm">
          <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-primary/60">
            Research Query
          </p>
          <p className="text-sm font-semibold leading-snug text-foreground line-clamp-2">{query}</p>
        </div>
      </div>

      <Arrow />

      {/* ---- Resource grid ---- */}
      {resources.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 py-14 text-muted-foreground">
          {isRunning ? (
            <>
              <Loader2 className="h-8 w-8 animate-spin opacity-30" />
              <p className="text-sm">Searching for sources&hellip;</p>
            </>
          ) : (
            <p className="text-sm">No sources found.</p>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {resources.map((resource, i) => (
            <ResourceCard key={resource.id} resource={resource} index={i} />
          ))}
        </div>
      )}

      {/* ---- Summary node ---- */}
      {resources.length > 0 && (
        <>
          <Arrow />

          <div className="flex justify-center">
            <div className="inline-flex items-center gap-5 rounded-xl border bg-muted/40 px-6 py-3 text-sm shadow-sm">
              <span className="flex items-center gap-1.5 font-semibold text-emerald-700 dark:text-emerald-400">
                <Check className="h-4 w-4" />
                {accepted.length} accepted
              </span>

              <div className="h-4 w-px bg-border" />

              <span className="flex items-center gap-1.5 text-muted-foreground">
                <X className="h-4 w-4" />
                {rejected.length} filtered out
              </span>

              {evaluating.length > 0 && (
                <>
                  <div className="h-4 w-px bg-border" />
                  <span className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {evaluating.length} evaluating
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Show "feeds into report" only when research is complete */}
          {!isRunning && accepted.length > 0 && (
            <>
              <Arrow />
              <div className="flex justify-center">
                <div className="rounded-xl border border-primary/20 bg-primary/5 px-5 py-2.5 text-center">
                  <p className="text-xs font-semibold text-primary/70">
                    {accepted.length} source{accepted.length !== 1 ? "s" : ""} synthesised into report
                  </p>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
