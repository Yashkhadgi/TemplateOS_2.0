import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { templatesApi, TemplateResponse } from "@/lib/api";
import { useAuth } from "@/context/auth-context";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { ArrowLeft, Download, Eraser, FileText, ListChecks, ScanSearch, Settings2, Trash2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const STATUS_BADGE_CLASSES: Record<string, string> = {
  uploaded: "bg-slate-100 text-slate-700",
  placeholder_detected: "bg-blue-50 text-blue-700",
  field_configured: "bg-violet-50 text-violet-700",
  active: "bg-emerald-50 text-emerald-700",
  archived: "bg-slate-100 text-slate-500",
  locked: "bg-amber-50 text-amber-700",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge
      variant="outline"
      className={cn("border-transparent", STATUS_BADGE_CLASSES[status] ?? "bg-slate-100 text-slate-700")}
    >
      <span className="capitalize">{status.replace(/_/g, " ")}</span>
    </Badge>
  );
}

interface ConfigAction {
  label: string;
  icon: LucideIcon;
  target: string;
}

function getConfigAction(templateId: number, status: string): ConfigAction {
  switch (status) {
    case "uploaded":
      return { label: "Detect Placeholders", icon: ScanSearch, target: `/templates/${templateId}/placeholders` };
    case "field_configured":
    case "active":
      return { label: "Edit Fields", icon: Settings2, target: `/templates/${templateId}/fields` };
    case "placeholder_detected":
    default:
      return { label: "Review Fields", icon: ListChecks, target: `/templates/${templateId}/fields` };
  }
}

export function TemplateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [template, setTemplate] = useState<TemplateResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    fetchTemplate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const fetchTemplate = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("templateos_access_token") || "";
      const data = await templatesApi.getTemplateDetail(token, Number(id));
      setTemplate(data);
    } catch (err: any) {
      setError({
        message: err.message || "Failed to load template",
        status: err.status,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formattedDate = template ? new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date(template.created_at)) : "";

  if (isLoading) {
    return (
      <div className="max-w-4xl space-y-8">
        <Skeleton className="h-10 w-32" />
        <div className="space-y-4">
          <Skeleton className="h-10 w-3/4" />
          <div className="flex gap-2">
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-6 w-20" />
          </div>
        </div>
        <Skeleton className="h-20 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl space-y-6 text-center py-20">
        <h2 className="text-2xl font-semibold">
          {error.status === 404 ? "Template not found" :
           error.status === 403 ? "You do not have access to this template" :
           "Something went wrong"}
        </h2>
        {error.status !== 404 && error.status !== 403 && (
          <p className="text-slate-600">{error.message}</p>
        )}
        <div className="flex justify-center gap-4 mt-6">
          <Button variant="outline" onClick={() => navigate("/templates")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Library
          </Button>
          {error.status !== 404 && error.status !== 403 && (
            <Button onClick={fetchTemplate}>Retry</Button>
          )}
        </div>
      </div>
    );
  }

  if (!template) return null;

  const isOwner = template.uploaded_by === user?.id;
  const isSuperAdmin = user?.role === "super_admin";
  const configAction = isOwner ? getConfigAction(template.id, template.status) : null;
  const canSubmitDelete = confirmText.trim().toLowerCase() === "confirm" && !isDeleting;

  const openDeleteDialog = () => {
    setConfirmText("");
    setDeleteError(null);
    setDeleteOpen(true);
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      const token = localStorage.getItem("templateos_access_token") || "";
      await templatesApi.deleteTemplate(token, template.id);
      setDeleteOpen(false);
      navigate("/templates");
    } catch (err: any) {
      setDeleteError(err.message || "Failed to delete the template. Please try again.");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-8 pb-10">
      <Button variant="ghost" onClick={() => navigate("/templates")} className="-ml-4 text-slate-600">
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Library
      </Button>

      <div>
        <h1 className="text-3xl font-semibold mb-4">{template.name}</h1>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={template.status} />
          <Badge variant="outline" className="bg-slate-50">
            Category: <span className="ml-1 capitalize">{template.category}</span>
          </Badge>
          <Badge variant="outline" className="bg-slate-50">
            Visibility: <span className="ml-1 capitalize">{template.visibility}</span>
          </Badge>
        </div>
      </div>

      {template.description && (
        <div className="prose prose-slate max-w-none">
          <p className="text-slate-700 leading-relaxed">{template.description}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 bg-slate-50 p-6 rounded-xl border">
        <div className="space-y-4">
          <div>
            <div className="text-sm font-medium text-slate-500">Original Filename</div>
            <div className="mt-1 text-slate-900">{template.original_filename || "N/A"}</div>
          </div>
          <div>
            <div className="text-sm font-medium text-slate-500">File Size</div>
            <div className="mt-1 text-slate-900">
              {template.file_size_bytes ? formatBytes(template.file_size_bytes) : "Unknown"}
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div>
            <div className="text-sm font-medium text-slate-500">Uploaded On</div>
            <div className="mt-1 text-slate-900">{formattedDate}</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm font-medium text-slate-500">Version</div>
              <div className="mt-1 text-slate-900">v{template.version}</div>
            </div>
            <div>
              <div className="text-sm font-medium text-slate-500">Template ID</div>
              <div className="mt-1 text-slate-900">{template.id}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-4 pt-4 border-t">
        {(template.status === "field_configured" || template.status === "active") && (
          <Button
            className="gap-2"
            onClick={() => navigate(`/documents/create/${template.id}`)}
          >
            <FileText className="h-4 w-4" />
            Use This Template
          </Button>
        )}
        {isOwner && configAction && (
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => navigate(configAction.target)}
          >
            <configAction.icon className="h-4 w-4" />
            {configAction.label}
          </Button>
        )}
        {isOwner && (
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => navigate(`/templates/${template.id}/clean`)}
          >
            <Eraser className="h-4 w-4" />
            Clean Template
          </Button>
        )}
        <Button variant="outline" disabled title="Coming soon" className="gap-2">
          <Download className="h-4 w-4" />
          Download Original
        </Button>
        {isSuperAdmin && (
          <Button
            variant="destructive"
            className="gap-2 sm:ml-auto"
            onClick={openDeleteDialog}
            disabled={isDeleting}
          >
            <Trash2 className="h-4 w-4" />
            Delete Template
          </Button>
        )}
      </div>

      <Dialog open={deleteOpen} onOpenChange={(open) => !isDeleting && setDeleteOpen(open)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this template permanently?</DialogTitle>
            <DialogDescription>
              This removes <span className="font-medium text-slate-900">{template.name}</span>,
              its detected fields, and the original and processed DOCX files from storage. This
              action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-sm text-slate-600">
              Type <span className="font-mono font-semibold text-red-600">confirm</span> to
              continue.
            </p>
            <Input
              value={confirmText}
              onChange={(event) => setConfirmText(event.target.value)}
              placeholder="confirm"
              autoComplete="off"
              disabled={isDeleting}
              onKeyDown={(event) => {
                if (event.key === "Enter" && canSubmitDelete) handleDelete();
              }}
            />
          </div>
          {deleteError && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{deleteError}</div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)} disabled={isDeleting}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={!canSubmitDelete}
            >
              {isDeleting ? "Deleting…" : "Delete permanently"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
