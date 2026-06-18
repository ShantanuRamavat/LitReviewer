import { ExternalLink } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import type { ReportCitation } from "@/lib/types";

interface SourceListProps {
  citations: ReportCitation[];
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function SourceList({ citations }: SourceListProps) {
  if (citations.length === 0) return null;

  return (
    <div className="space-y-2">
      <Separator />
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Sources ({citations.length})
      </p>

      <ol className="space-y-1.5">
        {citations.map((c) => (
          <li key={c.number} className="flex items-start gap-2">
            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-sm bg-muted text-[10px] font-bold text-muted-foreground">
              {c.number}
            </span>

            <a
              href={c.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex flex-1 items-center gap-1 truncate text-xs text-muted-foreground hover:text-foreground"
              title={c.source_url}
            >
              <span className="truncate">{hostnameOf(c.source_url)}</span>
              <ExternalLink className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
            </a>
          </li>
        ))}
      </ol>
    </div>
  );
}
