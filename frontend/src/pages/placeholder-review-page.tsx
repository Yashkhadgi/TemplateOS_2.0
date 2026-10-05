import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  templatesApi,
  type DetectionWarnings,
  type PlaceholderDetectionResponse,
  type TemplateField,
  type TemplateResponse,
} from "@/lib/api";
import { useAuth } from "@/context/auth-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { AlertTriangle, ArrowLeft, ArrowRight, Braces, Eraser, RefreshCw, ScanSearch } from "lucide-react";

function MonoKey({ name }: { name: string }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
      {`{{${name}}}`}
    </code>
  );
}

function DetectedFieldsList({ fields }: { fields: TemplateField[] }) {
  const sorted = [...fields].sort((a, b) => a.display_order - b.display_order);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Detected fields</CardTitle>
        <CardDescription>
          Placeholders found in the original DOCX, in document order. Duplicate occurrences map to a single field.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <ol className="divide-y divide-slate-100">
          {sorted.map((field) => (
            <li key={field.id} className="flex items-start gap-4 px-4 py-4 sm:px-6">
              <span className="mt-1 w-6 shrink-0 text-center font-mono text-xs text-slate-400">
                {field.display_order}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-slate-900">
                    {field.field_label || field.field_name}
                  </span>
                  {field.is_required && (
                    <Badge variant="outline" className="border-red-200 bg-red-50 text-red-700">
                      Required
                    </Badge>
                  )}
                </div>
                <div className="mt-1.5">
                  <MonoKey name={field.field_name} />
                </div>
              </div>
              <Badge variant="outline" className="shrink-0 bg-slate-50 capitalize">
                {field.field_type}
              </Badge>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function WarningsPanel({ warnings }: { warnings: DetectionWarnings }) {
  const hasDuplicates = warnings.duplicates.length > 0;
  const hasInvalid = warnings.invalid_names.length > 0;
  const hasParseError = Boolean(warnings.parse_error);
  if (!hasDuplicates && !hasInvalid && !hasParseError) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          Detection warnings
        </CardTitle>
        <CardDescription>
          Issues found while scanning the document. Detection still succeeded.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {hasParseError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <p className="font-semibold">
              Some placeholders couldn't be parsed for document generation.
            </p>
            <p className="mt-1">
              Fix the invalid names above via Template Cleaning so the template will fill
              correctly. Detection still succeeded via a text-scan fallback.
            </p>
          </div>
        )}
        {hasDuplicates && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            <ul className="space-y-1">
              {warnings.duplicates.map((duplicate) => (
                <li key={duplicate.key}>
                  <MonoKey name={duplicate.key} /> appears {duplicate.count}{" "}
                  {duplicate.count === 1 ? "time" : "times"} — mapped to one field.
                </li>
              ))}
            </ul>
          </div>
        )}
        {hasInvalid && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <ul className="space-y-1">
              {warnings.invalid_names.map((invalid) => (
                <li key={invalid.raw}>
                  <MonoKey name={invalid.raw} /> is not a valid key ({invalid.reason}). Suggested:{" "}
                  <MonoKey name={invalid.suggested_key} />.
                </li>
              ))}
            </ul>
            <p className="mt-2">
              These placeholders were skipped and not added as fields. Fix them in the DOCX or
              convert them via Template Cleaning.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function PlaceholderReviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const templateId = Number(id);

  const [template, setTemplate] = useState<TemplateResponse | null>(null);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [detection, setDetection] = useState<PlaceholderDetectionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDetecting, setIsDetecting] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const token = localStorage.getItem("templateos_access_token") || "";
        const [templateData, fieldData] = await Promise.all([
          templatesApi.getTemplateDetail(token, templateId),
          templatesApi.getFields(token, templateId),
        ]);
        if (!active) return;
        setTemplate(templateData);
        setFields(fieldData);
      } catch (err: any) {
        if (!active) return;
        setError({ message: err.message || "Failed to load template", status: err.status });
      } finally {
        if (active) setIsLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [templateId]);

  const handleDetect = async (force: boolean) => {
    setConfirmOpen(false);
    setIsDetecting(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const token = localStorage.getItem("templateos_access_token") || "";
      const result = await templatesApi.detectPlaceholders(token, templateId, force);
      setDetection(result);
      setFields(result.detected_fields);
      setTemplate((prev) => (prev ? { ...prev, status: result.status || prev.status } : prev));
      const count = result.detected_fields.length;
      setActionMessage(
        count > 0
          ? `Placeholder detection complete — ${count} ${count === 1 ? "field" : "fields"} detected.`
          : "Placeholder detection complete — no placeholders were found.",
      );
    } catch (err: any) {
      setActionError(err.message || "Failed to detect placeholders. Please try again.");
    } finally {
      setIsDetecting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl space-y-8">
        <Skeleton className="h-9 w-44" />
        <Skeleton className="h-5 w-72" />
        <Skeleton className="h-72 w-full rounded-2xl" />
        <Skeleton className="h-24 w-full rounded-2xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl space-y-6 text-center py-20">
        <h2 className="text-2xl font-semibold">
          {error.status === 404
            ? "Template not found"
            : error.status === 403
              ? "You do not have access to this template"
              : "Something went wrong"}
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
            <Button onClick={() => navigate(0)}>Retry</Button>
          )}
        </div>
      </div>
    );
  }

  if (!template) return null;

  const isOwner = template.uploaded_by === user?.id;
  const hasRunDetection = detection !== null || template.status !== "uploaded";
  const showEmptyState = hasRunDetection && fields.length === 0;
  const fieldCount = fields.length;
  const invalidCount = detection ? detection.summary.invalid_count : 0;

  return (
    <div className="max-w-4xl space-y-8 pb-10">
      <Button
        variant="ghost"
        onClick={() => navigate(`/templates/${template.id}`)}
        className="-ml-4 text-slate-600"
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Template
      </Button>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Placeholder Review</h1>
          <p className="mt-2 text-sm text-slate-600">
            {template.name} · Detected {fieldCount} {fieldCount === 1 ? "field" : "fields"}
            {invalidCount > 0
              ? ` · ${invalidCount} invalid ${invalidCount === 1 ? "name" : "names"} skipped`
              : ""}
          </p>
        </div>
        {isOwner && hasRunDetection && (
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => setConfirmOpen(true)}
            disabled={isDetecting}
          >
            <RefreshCw className={`h-4 w-4 ${isDetecting ? "animate-spin" : ""}`} />
            Re-detect
          </Button>
        )}
      </div>

      {actionError && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{actionError}</div>
      )}
      {actionMessage && !actionError && (
        <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{actionMessage}</div>
      )}
      {isDetecting && (
        <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          Scanning the document for placeholders…
        </div>
      )}

      {fieldCount > 0 ? (
        <>
          <DetectedFieldsList fields={fields} />
          {detection && <WarningsPanel warnings={detection.warnings} />}
        </>
      ) : showEmptyState ? (
        <EmptyState
          icon={Braces}
          title="No placeholders found"
          description="This DOCX doesn't contain any {{placeholders}} yet. Use Template Cleaning to convert its sample text into reusable placeholders."
          actionLabel="Clean This Template"
          onAction={
            isOwner
              ? () => navigate(`/templates/${template.id}/clean`)
              : undefined
          }
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ScanSearch className="h-5 w-5 text-slate-500" />
              Detect placeholders
            </CardTitle>
            <CardDescription>
              Scan the original DOCX for <span className="font-mono text-xs">{"{{placeholder}}"}</span>{" "}
              tokens. Each valid placeholder becomes a form field you can configure.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isOwner ? (
              <Button className="gap-2" onClick={() => handleDetect(false)} disabled={isDetecting}>
                <ScanSearch className="h-4 w-4" />
                {isDetecting ? "Detecting…" : "Detect Placeholders"}
              </Button>
            ) : (
              <p className="text-sm text-slate-600">
                Only the template owner can run placeholder detection.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-4 border-t pt-6">
        {fieldCount > 0 && (
          <Button className="gap-2" onClick={() => navigate(`/templates/${template.id}/fields`)}>
            Continue to Field Setup
            <ArrowRight className="h-4 w-4" />
          </Button>
        )}
        {isOwner && (
          <Button
            variant={fieldCount > 0 ? "outline" : "default"}
            className="gap-2"
            onClick={() => navigate(`/templates/${template.id}/clean`)}
          >
            <Eraser className="h-4 w-4" />
            Clean Template
          </Button>
        )}
        <Button variant="outline" onClick={() => navigate(`/templates/${template.id}`)}>
          Back to Template
        </Button>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Re-detect placeholders?</DialogTitle>
            <DialogDescription>
              This replaces the current {fieldCount} {fieldCount === 1 ? "field" : "fields"} with a
              fresh scan of the original DOCX. Existing field configuration will be lost.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={isDetecting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => handleDetect(true)} disabled={isDetecting}>
              {isDetecting ? "Detecting…" : "Re-detect"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
