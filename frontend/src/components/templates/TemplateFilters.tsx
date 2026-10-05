import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

interface TemplateFiltersProps {
  category: string;
  visibility: string;
  onCategoryChange: (value: string) => void;
  onVisibilityChange: (value: string) => void;
  onClearAll: () => void;
}

export function TemplateFilters({
  category,
  visibility,
  onCategoryChange,
  onVisibilityChange,
  onClearAll,
}: TemplateFiltersProps) {
  const hasFilters = category !== "" || visibility !== "";

  return (
    <div className="flex flex-col sm:flex-row items-center gap-4">
      <Select value={category || "all"} onValueChange={(val) => onCategoryChange(val === "all" ? "" : val)}>
        <SelectTrigger className="w-full sm:w-[200px]">
          <SelectValue placeholder="All Categories" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Categories</SelectItem>
          <SelectItem value="notice">Notice</SelectItem>
          <SelectItem value="mom">Minutes of Meeting</SelectItem>
          <SelectItem value="report">Report</SelectItem>
          <SelectItem value="application">Application</SelectItem>
          <SelectItem value="letter">Letter</SelectItem>
          <SelectItem value="certificate">Certificate</SelectItem>
          <SelectItem value="proposal">Proposal</SelectItem>
          <SelectItem value="invoice">Invoice</SelectItem>
          <SelectItem value="custom">Custom</SelectItem>
        </SelectContent>
      </Select>

      <Select value={visibility || "all"} onValueChange={(val) => onVisibilityChange(val === "all" ? "" : val)}>
        <SelectTrigger className="w-full sm:w-[200px]">
          <SelectValue placeholder="All Visibility" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Visibility</SelectItem>
          <SelectItem value="private">Private</SelectItem>
          <SelectItem value="public">Public</SelectItem>
          <SelectItem value="organization">Organization</SelectItem>
          <SelectItem value="department">Department</SelectItem>
          <SelectItem value="group">Group</SelectItem>
        </SelectContent>
      </Select>

      {hasFilters && (
        <Button
          variant="ghost"
          onClick={onClearAll}
          className="text-slate-500 hover:text-slate-900 w-full sm:w-auto"
        >
          Clear Filters
        </Button>
      )}
    </div>
  );
}
