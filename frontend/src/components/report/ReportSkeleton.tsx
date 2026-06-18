import { Skeleton } from "@/components/ui/skeleton";

export function ReportSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 animate-in fade-in duration-300">
      {/* Title */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-4 w-1/3" />
      </div>

      {/* Executive Summary */}
      <section className="space-y-3">
        <Skeleton className="h-5 w-44" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      </section>

      {/* Key Findings */}
      <section className="space-y-3">
        <Skeleton className="h-5 w-36" />
        <div className="space-y-2.5">
          {[80, 92, 70, 85, 65].map((w, i) => (
            <div key={i} className="flex items-start gap-2">
              <Skeleton className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" />
              <Skeleton className="h-4" style={{ width: `${w}%` }} />
            </div>
          ))}
        </div>
      </section>

      {/* Supporting Evidence */}
      <section className="space-y-4">
        <Skeleton className="h-5 w-48" />
        {[1, 2].map((s) => (
          <div key={s} className="space-y-2">
            <Skeleton className="h-4 w-56" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ))}
      </section>
    </div>
  );
}
