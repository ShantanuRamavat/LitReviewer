import { BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AppHeaderProps {
  onNew?: () => void;
}

export function AppHeader({ onNew }: AppHeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b bg-background px-6">
      <div className="flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-primary" />
        <span className="font-semibold tracking-tight">LitReviewer</span>
      </div>

      {onNew && (
        <Button variant="outline" size="sm" onClick={onNew}>
          New Research
        </Button>
      )}
    </header>
  );
}
