"use client";

import { ExternalLink, FlaskConical } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { WorkflowOutput, ReportCitation, PhDAnnotations } from "@/lib/types";

interface ReportViewerProps {
  output: WorkflowOutput;
}

export function ReportViewer({ output }: ReportViewerProps) {
  const { title, introduction, content, word_count, citations } = output;
  const { body_sections, synthesis, conclusion, phd_annotations } = content;

  return (
    <article className="mx-auto max-w-3xl space-y-8 pb-16 animate-in fade-in duration-500">

      {/* ---- Title + meta ---- */}
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        <p className="text-xs text-muted-foreground">
          {word_count.toLocaleString()} words ·{" "}
          {citations.length} source{citations.length !== 1 ? "s" : ""}
          {phd_annotations && (
            <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700">
              <FlaskConical className="h-2.5 w-2.5" />
              PhD Mode
            </span>
          )}
        </p>
      </header>

      <Separator />

      {/* ---- Introduction ---- */}
      <Section heading="Introduction">
        <Prose text={introduction} />
      </Section>

      <Separator />

      {/* ---- Body Sections ---- */}
      {body_sections.length > 0 && (
        <>
          <section className="space-y-6">
            <h2 className="text-base font-semibold tracking-tight">Literature Review</h2>
            {body_sections.map((section, i) => (
              <div key={i} className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">
                  {section.heading}
                  {section.citation_numbers.length > 0 && (
                    <span className="ml-2 inline-flex gap-0.5">
                      {section.citation_numbers.map((n) => (
                        <CitationLink key={n} number={n} />
                      ))}
                    </span>
                  )}
                </h3>
                <p className="text-sm leading-7 text-foreground/90">
                  <InlineBody text={section.body} />
                </p>
              </div>
            ))}
          </section>
          <Separator />
        </>
      )}

      {/* ---- Synthesis ---- */}
      {synthesis && (
        <>
          <Section heading="Synthesis">
            <Prose text={synthesis} />
          </Section>
          <Separator />
        </>
      )}

      {/* ---- Conclusion ---- */}
      {conclusion && (
        <>
          <Section heading="Conclusion">
            <Prose text={conclusion} />
          </Section>
          <Separator />
        </>
      )}

      {/* ---- PhD Annotations ---- */}
      {phd_annotations && (
        <>
          <PhDAnnotationsBlock annotations={phd_annotations} />
          <Separator />
        </>
      )}

      {/* ---- References ---- */}
      <Section heading="References">
        <ReferenceList citations={citations} />
      </Section>
    </article>
  );
}

// ---------------------------------------------------------------------------
// PhD Annotations block
// ---------------------------------------------------------------------------

function PhDAnnotationsBlock({ annotations }: { annotations: PhDAnnotations }) {
  const items: Array<{ label: string; key: keyof PhDAnnotations }> = [
    { label: "State-of-the-Art Analysis",   key: "state_of_art_analysis" },
    { label: "Future Possibilities",         key: "future_possibilities" },
    { label: "Topic Overlap & Inform",       key: "topic_overlap_and_inform" },
    { label: "Novelty Assessment",           key: "novelty_assessment" },
    { label: "Current Researchers",          key: "current_researchers" },
  ];

  return (
    <section className="space-y-5">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold tracking-tight">PhD Research Notes</h2>
        <Badge variant="secondary" className="bg-violet-100 text-violet-700 text-[10px]">
          <FlaskConical className="mr-1 h-2.5 w-2.5" />
          PhD Mode
        </Badge>
      </div>
      <div className="rounded-lg border border-violet-200 bg-violet-50/50 divide-y divide-violet-100">
        {items.map(({ label, key }) => (
          <div key={key} className="px-4 py-4 space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-violet-600">
              {label}
            </h3>
            <p className="text-sm leading-7 text-foreground/90 whitespace-pre-line">
              {annotations[key]}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Section({
  heading,
  children,
}: {
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3" id={heading.toLowerCase().replace(/\s+/g, "-")}>
      <h2 className="text-base font-semibold tracking-tight">{heading}</h2>
      {children}
    </section>
  );
}

function Prose({ text }: { text: string }) {
  return (
    <p className="text-sm leading-7 text-foreground/90">
      <InlineBody text={text} />
    </p>
  );
}

function CitationLink({ number }: { number: number }) {
  return (
    <a
      href={`#ref-${number}`}
      className="inline-flex h-4 min-w-[1rem] items-center justify-center rounded bg-muted px-1 text-[10px] font-semibold text-muted-foreground hover:bg-primary hover:text-primary-foreground transition-colors no-underline"
    >
      {number}
    </a>
  );
}

function InlineBody({ text }: { text: string }) {
  const parts = text.split(/(\[\d{1,3}\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d{1,3})\]$/);
        if (match) {
          return <CitationLink key={i} number={parseInt(match[1], 10)} />;
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

function ReferenceList({ citations }: { citations: ReportCitation[] }) {
  return (
    <ol className="space-y-2">
      {citations.map((c) => (
        <li
          key={c.number}
          id={`ref-${c.number}`}
          className="flex items-start gap-3 scroll-mt-4"
        >
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-muted text-[10px] font-bold text-muted-foreground">
            {c.number}
          </span>

          <div className="flex flex-1 items-center gap-2 min-w-0">
            <a
              href={c.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="truncate text-xs text-primary underline underline-offset-2 hover:text-primary/80"
              title={c.source_url}
            >
              {c.source_url}
            </a>
            <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground" />
            <Badge
              variant="secondary"
              className={cn(
                "shrink-0 text-[10px]",
                c.source_type === "rag" && "bg-violet-100 text-violet-700",
              )}
            >
              {c.source_type}
            </Badge>
          </div>
        </li>
      ))}
    </ol>
  );
}
