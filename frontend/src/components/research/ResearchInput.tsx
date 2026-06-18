"use client";

import { useEffect, useRef, useState } from "react";
import { GraduationCap, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { ResearchMode } from "@/lib/types";

const EXAMPLES = [
  "Latest advances in quantum error correction",
  "How does RLHF improve large language models?",
  "Impact of transformer architecture on NLP",
];

interface ResearchInputProps {
  onSubmit: (query: string, mode: ResearchMode) => void;
  isLoading: boolean;
  defaultValue?: string;
  /** When true, renders a compact single-line bar instead of the full card. */
  compact?: boolean;
}

export function ResearchInput({
  onSubmit,
  isLoading,
  defaultValue = "",
  compact = false,
}: ResearchInputProps) {
  const [value, setValue] = useState(defaultValue);
  const [mode, setMode] = useState<ResearchMode>("general");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setValue(defaultValue);
  }, [defaultValue]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim() || isLoading) return;
    onSubmit(value.trim(), mode);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  if (compact) {
    return (
      <form onSubmit={handleSubmit} className="flex items-center gap-3">
        <p className="flex-1 truncate text-sm font-medium text-foreground">
          {value}
        </p>
        {isLoading && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Generating…
          </div>
        )}
      </form>
    );
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-foreground">
            What do you want to research?
          </label>
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter a research query…"
            className="min-h-[100px] resize-none text-sm"
            disabled={isLoading}
            autoFocus
          />
          <p className="text-xs text-muted-foreground">
            Press Enter to submit · Shift+Enter for newline
          </p>
        </div>

        {/* Mode selector */}
        <div className="flex gap-2">
          <ModeButton
            active={mode === "general"}
            onClick={() => setMode("general")}
            icon={<Search className="h-3.5 w-3.5" />}
            label="General"
            description="Literature review"
          />
          <ModeButton
            active={mode === "phd"}
            onClick={() => setMode("phd")}
            icon={<GraduationCap className="h-3.5 w-3.5" />}
            label="PhD"
            description="+ SotA · Novelty · Researchers"
            accent
          />
        </div>

        <Button
          type="submit"
          disabled={!value.trim() || isLoading}
          className="w-full"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating report…
            </>
          ) : (
            <>
              {mode === "phd" ? (
                <GraduationCap className="h-4 w-4" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              Generate {mode === "phd" ? "PhD" : ""} Report
            </>
          )}
        </Button>
      </form>

      {/* Example queries */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Try an example
        </p>
        <div className="flex flex-col gap-1">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => {
                setValue(ex);
                textareaRef.current?.focus();
              }}
              className="text-left text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ModeButton({
  active,
  onClick,
  icon,
  label,
  description,
  accent = false,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  description: string;
  accent?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-1 items-start gap-2 rounded-lg border px-3 py-2.5 text-left transition-all",
        active && !accent && "border-primary bg-primary/5 ring-1 ring-primary/30",
        active && accent  && "border-violet-400 bg-violet-50 ring-1 ring-violet-300",
        !active && "border-border hover:border-muted-foreground/40 bg-background",
      )}
    >
      <span className={cn(
        "mt-0.5 shrink-0",
        active && !accent && "text-primary",
        active && accent  && "text-violet-600",
        !active && "text-muted-foreground",
      )}>
        {icon}
      </span>
      <div>
        <p className={cn(
          "text-xs font-semibold",
          active && !accent && "text-primary",
          active && accent  && "text-violet-700",
          !active && "text-foreground",
        )}>
          {label}
        </p>
        <p className="text-[10px] text-muted-foreground leading-tight mt-0.5">
          {description}
        </p>
      </div>
    </button>
  );
}
