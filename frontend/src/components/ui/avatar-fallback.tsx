import { cn } from "@/lib/utils";
import { getInitials } from "@/lib/format";

interface AvatarFallbackProps {
  name: string | null | undefined;
  className?: string;
}

export function AvatarFallback({ name, className }: AvatarFallbackProps) {
  return (
    <div
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 font-medium text-slate-600",
        className,
      )}
      aria-hidden="true"
    >
      {getInitials(name)}
    </div>
  );
}
