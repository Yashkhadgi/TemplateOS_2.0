import { useRef, useState } from "react";
import { CloudUpload, FileText, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface UploadZoneProps {
  file: File | null;
  onChange: (file: File | null) => void;
  error?: string;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadZone({ file, onChange, error: externalError }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [inlineError, setInlineError] = useState("");

  const validate = (selectedFile: File): boolean => {
    setInlineError("");
    if (!selectedFile.name.toLowerCase().endsWith(".docx")) {
      setInlineError("Only .docx files are accepted");
      onChange(null);
      return false;
    }
    if (selectedFile.size > MAX_FILE_SIZE) {
      setInlineError("File must be under 10 MB");
      onChange(null);
      return false;
    }
    return true;
  };

  const handleFile = (selectedFile: File | undefined | null) => {
    if (!selectedFile) return;
    if (validate(selectedFile)) {
      onChange(selectedFile);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    handleFile(dropped);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFile(e.target.files?.[0]);
    // Reset input so the same file can be re-selected after removal
    e.target.value = "";
  };

  const handleRemove = () => {
    setInlineError("");
    onChange(null);
  };

  const displayError = inlineError || externalError;
  const hasError = Boolean(displayError);

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept=".docx"
        className="hidden"
        onChange={handleInputChange}
        aria-label="Upload .docx file"
      />

      {file ? (
        /* ── File selected state ── */
        <div
          className={cn(
            "flex items-center gap-4 rounded-xl border border-slate-300 bg-white px-4 py-4",
          )}
        >
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
            <FileText className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-900">{file.name}</p>
            <p className="text-xs text-slate-500">{formatBytes(file.size)}</p>
          </div>
          <button
            type="button"
            onClick={handleRemove}
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
            aria-label="Remove file"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        /* ── Empty / drag state ── */
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={cn(
            "flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
            isDragging
              ? "border-slate-400 bg-slate-50"
              : hasError
                ? "border-red-300 bg-red-50"
                : "border-slate-300 bg-white hover:border-slate-400",
          )}
        >
          <div
            className={cn(
              "flex h-12 w-12 items-center justify-center rounded-full",
              hasError ? "bg-red-100 text-red-500" : "bg-slate-100 text-slate-500",
            )}
          >
            <CloudUpload className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-700">
              Drag &amp; drop your .docx file here
            </p>
            <p className="mt-1 text-xs text-slate-500">or click below to browse</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => inputRef.current?.click()}
          >
            Browse file
          </Button>
        </div>
      )}

      {displayError && (
        <p className="text-sm text-red-600">{displayError}</p>
      )}
    </div>
  );
}
