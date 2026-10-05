import { TemplateListItem } from "@/lib/api";
import { TemplateCard } from "./TemplateCard";
import { Skeleton } from "@/components/ui/skeleton";
import { FileSearch } from "lucide-react";

interface TemplateGridProps {
  templates: TemplateListItem[];
  onCardClick: (id: number) => void;
  isLoading: boolean;
  emptyMessage?: string;
}

export function TemplateGrid({
  templates,
  onCardClick,
  isLoading,
  emptyMessage = "No templates found",
}: TemplateGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex flex-col min-h-[160px] p-5 border rounded-xl shadow-sm bg-card">
            <div className="flex justify-between items-start mb-3 gap-4">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-2 w-2 rounded-full mt-1.5 shrink-0" />
            </div>
            <Skeleton className="h-5 w-1/2 mb-6" />
            <div className="mt-auto space-y-3">
              <div className="flex items-center gap-2">
                <Skeleton className="h-5 w-16 rounded-full" />
                <Skeleton className="h-4 w-12" />
              </div>
              <Skeleton className="h-3 w-32" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (templates.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="h-20 w-20 bg-slate-100 rounded-full flex items-center justify-center mb-6">
          <FileSearch className="h-10 w-10 text-slate-400" />
        </div>
        <h3 className="text-lg font-semibold text-slate-900 mb-2">{emptyMessage}</h3>
        {emptyMessage === "No templates found" && (
          <p className="text-slate-500 max-w-sm">
            Try adjusting your search or filters to find what you're looking for.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {templates.map((template) => (
        <TemplateCard
          key={template.id}
          template={template}
          onClick={onCardClick}
        />
      ))}
    </div>
  );
}
