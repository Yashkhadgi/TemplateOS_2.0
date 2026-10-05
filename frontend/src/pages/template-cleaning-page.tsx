import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eraser,
  Plus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  templatesApi,
  type CleanResponse,
  type DocSegment,
  type PlaceholderReplacement,
  type TemplateContent,
  type TemplateResponse,
} from "@/lib/api";
import { useAuth } from "@/context/auth-context";

const TOKEN_KEY = "templateos_access_token";

const FIELD_TYPE_OPTIONS = [
  { label: "Text", value: "text" },
  { label: "Long text", value: "textarea" },
  { label: "Date", value: "date" },
  { label: "Number", value: "number" },
  { label: "List", value: "list" },
  { label: "Signature", value: "signature" },
] as const;

const LOCATION_ORDER: DocSegment["location"][] = ["body", "table", "header", "footer"];

const KEY_RULE_MESSAGE =
  "Use lowercase letters, numbers, underscores; must start with a letter";

const convertSchema = z.object({
  placeholder_key: z
    .string()
    .min(1, "Placeholder key is required")
    .max(100, "Placeholder key must be 100 characters or fewer")
    .regex(/^[a-z][a-z0-9_]*$/, KEY_RULE_MESSAGE),
  field_label: z.string().max(150, "Label must be 150 characters or fewer").optional(),
  field_type: z.enum(["text", "textarea", "date", "number", "list", "signature"]),
  section: z.string().max(100, "Section must be 100 characters or fewer").optional(),
});

type ConvertValues = z.infer<typeof convertSchema>;

/** Mirror of the backend's suggest_key: normalized snake_case from sample text. */
function suggestKey(raw: string): string {
  let key = raw.trim().toLowerCase();
  key = key.replace(/[\s-]+/g, "_");
  key = key.replace(/[^a-z0-9_]/g, "");
  key = key.replace(/_{2,}/g, "_").replace(/^_+|_+$/g, "");
  if (!key) return "";
  if (!/^[a-z]/.test(key)) key = `field_${key}`;
  return key;
}

function MonoKey({ name }: { name: string }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
      {`{{${name}}}`}
    </code>
  );
}

interface StagedReplacement extends PlaceholderReplacement {
  id: string;
}

export function TemplateCleaningPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const templateId = Number(id);

  const [template, setTemplate] = useState<TemplateResponse | null>(null);
  const [content, setContent] = useState<TemplateContent | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);

  const [staged, setStaged] = useState<StagedReplacement[]>([]);
  const [selectedText, setSelectedText] = useState("");
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState<number | undefined>(
    undefined,
  );
  const [convertOpen, setConvertOpen] = useState(false);
  const [applyOpen, setApplyOpen] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [result, setResult] = useState<CleanResponse | null>(null);
  const documentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const token = localStorage.getItem(TOKEN_KEY) || "";
        const [templateData, contentData] = await Promise.all([
          templatesApi.getTemplateDetail(token, templateId),
          templatesApi.getContent(token, templateId),
        ]);
        if (!active) return;
        setTemplate(templateData);
        setContent(contentData);
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

  const isOwner = template?.uploaded_by === user?.id;

  const segmentsByLocation = useMemo(() => {
    const grouped: Record<string, DocSegment[]> = {};
    for (const segment of content?.segments ?? []) {
      (grouped[segment.location] ??= []).push(segment);
    }
    return grouped;
  }, [content]);

  const handleSelection = () => {
    if (convertOpen) return;
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !selection.toString().trim()) {
      setSelectedText("");
      setSelectedSegmentIndex(undefined);
      return;
    }
    const text = selection.toString().trim();
    if (text.length > 255) {
      setSelectedText("");
      return;
    }
    // Scope hint: which segment contains the selection anchor?
    let segmentIndex: number | undefined;
    const anchorParent = selection.anchorNode?.parentElement ?? null;
    if (anchorParent && documentRef.current?.contains(anchorParent)) {
      const holder = anchorParent.closest(
        "[data-segment-index]",
      ) as HTMLElement | null;
      if (holder) segmentIndex = Number(holder.dataset.segmentIndex);
    }
    setSelectedText(text);
    setSelectedSegmentIndex(segmentIndex);
  };

  const form = useForm<ConvertValues>({
    resolver: zodResolver(convertSchema),
    defaultValues: {
      placeholder_key: "",
      field_label: "",
      field_type: "text",
      section: "",
    },
  });

  const openConvertDialog = () => {
    const suggestion = suggestKey(selectedText);
    form.reset({
      placeholder_key: suggestion,
      field_label: "",
      field_type: "text",
      section: "",
    });
    setConvertOpen(true);
  };

  const stageReplacement = (values: ConvertValues) => {
    const duplicate = staged.some((r) => r.placeholder_key === values.placeholder_key);
    if (duplicate) {
      form.setError("placeholder_key", {
        message: "This key is already staged for this cleaning",
      });
      return;
    }
    setStaged((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        sample_text: selectedText,
        placeholder_key: values.placeholder_key,
        field_label: values.field_label?.trim() || undefined,
        field_type: values.field_type,
        section: values.section?.trim() || undefined,
        segment_index: selectedSegmentIndex,
      },
    ]);
    setConvertOpen(false);
    setSelectedText("");
    setSelectedSegmentIndex(undefined);
    window.getSelection()?.removeAllRanges();
  };

  const removeStaged = (stagedId: string) => {
    setStaged((prev) => prev.filter((r) => r.id !== stagedId));
  };

  const applyCleaning = async () => {
    setApplyOpen(false);
    setIsApplying(true);
    setActionError(null);
    try {
      const token = localStorage.getItem(TOKEN_KEY) || "";
      const response = await templatesApi.cleanTemplate(token, templateId, {
        replacements: staged.map(({ id: _id, ...replacement }) => replacement),
        confirm: true,
      });
      setResult(response);
    } catch (err: any) {
      setActionError(err.message || "Cleaning failed. Please try again.");
    } finally {
      setIsApplying(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-6xl space-y-8">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-5 w-96" />
        <div className="grid gap-8 lg:grid-cols-2">
          <Skeleton className="h-96 w-full rounded-2xl" />
          <Skeleton className="h-96 w-full rounded-2xl" />
        </div>
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

  if (!template || !content) return null;

  if (!isOwner) {
    return (
      <div className="max-w-4xl space-y-6 py-20 text-center">
        <h2 className="text-2xl font-semibold">Only the template owner can clean this template</h2>
        <p className="text-sm text-slate-600">
          Template cleaning converts sample text into placeholders and is limited to the owner.
        </p>
        <div className="flex justify-center">
          <Button variant="outline" onClick={() => navigate(`/templates/${template.id}`)}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Template
          </Button>
        </div>
      </div>
    );
  }

  // ── Result view ────────────────────────────────────────────────────
  if (result) {
    const created = result.created_fields.length;
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

        <div>
          <h1 className="text-3xl font-semibold">Cleaning applied</h1>
          <p className="mt-2 text-sm text-slate-600">
            {template.name} · Processed copy saved · Status:{" "}
            <span className="font-medium capitalize">
              {result.status.replace(/_/g, " ")}
            </span>
          </p>
        </div>

        <div className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-700">
          <p className="flex items-center gap-2 font-semibold">
            <CheckCircle2 className="h-4 w-4" />
            Processed template saved. {created} {created === 1 ? "field" : "fields"} created.
          </p>
          <p className="mt-1">
            Your original file is preserved unchanged. The processed copy is what document
            generation will use.
          </p>
        </div>

        {created > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Created fields</CardTitle>
              <CardDescription>
                Each converted sample value became a template field (example value preserved).
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <ol className="divide-y divide-slate-100">
                {result.created_fields.map((field) => (
                  <li
                    key={field.id}
                    className="flex flex-wrap items-center gap-3 px-4 py-3 sm:px-6"
                  >
                    <span className="font-medium text-slate-900">
                      {field.field_label || field.field_name}
                    </span>
                    <MonoKey name={field.field_name} />
                    <Badge variant="outline" className="bg-slate-50 capitalize">
                      {field.field_type}
                    </Badge>
                    <span className="text-xs text-slate-500">
                      was: {field.example_value}
                    </span>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        )}

        {result.warnings.unmatched.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            <p className="font-semibold">Some sample text was not found</p>
            <ul className="mt-1 list-disc pl-5">
              {result.warnings.unmatched.map((sample) => (
                <li key={sample}>
                  <span className="font-mono text-xs">{sample}</span> — it may have been
                  edited or split differently in the document.
                </li>
              ))}
            </ul>
          </div>
        )}
        {result.warnings.invalid_keys.length > 0 && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <p className="font-semibold">Invalid keys skipped</p>
            <ul className="mt-1 list-disc pl-5">
              {result.warnings.invalid_keys.map((key) => (
                <li key={key}>
                  <MonoKey name={key} /> was rejected ({KEY_RULE_MESSAGE}).
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap gap-4 border-t pt-6">
          <Button className="gap-2" onClick={() => navigate(`/templates/${template.id}/fields`)}>
            Continue to Field Setup
            <ArrowRight className="h-4 w-4" />
          </Button>
          <Button variant="outline" onClick={() => navigate(`/templates/${template.id}`)}>
            Back to Template
          </Button>
        </div>
      </div>
    );
  }

  // ── Editor view ────────────────────────────────────────────────────
  return (
    <div className="max-w-6xl space-y-6 pb-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Button
            variant="ghost"
            onClick={() => navigate(`/templates/${template.id}`)}
            className="-ml-4 mb-2 text-slate-600"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Template
          </Button>
          <h1 className="text-3xl font-semibold">Template Cleaning</h1>
          <p className="mt-2 text-sm text-slate-600">
            {template.name} · Turn sample values into{" "}
            <span className="font-mono text-xs">{"{{placeholders}}"}</span>. A processed copy is
            created — your original file is preserved.
          </p>
        </div>
        {content.has_processed && (
          <Badge variant="outline" className="bg-blue-50 text-blue-700">
            Processed copy exists — re-applying replaces it
          </Badge>
        )}
      </div>

      {actionError && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{actionError}</div>
      )}
      {isApplying && (
        <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          Applying cleaning — generating the processed document…
        </div>
      )}

      <div
        ref={documentRef}
        className="grid items-start gap-6 lg:grid-cols-2"
        onMouseUp={handleSelection}
        onTouchEnd={handleSelection}
      >
        {/* LEFT — document text */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2">
              <Eraser className="h-5 w-5 text-slate-500" />
              Document text
            </CardTitle>
            <CardDescription>
              Select any sample value in the document, then click “Convert to placeholder”.
            </CardDescription>
            {selectedText ? (
              <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <span className="max-w-[55%] truncate text-sm font-medium text-slate-700">
                  {selectedText}
                </span>
                <Button size="sm" className="gap-1.5" onClick={openConvertDialog}>
                  <Plus className="h-3.5 w-3.5" />
                  Convert to placeholder
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={() => {
                    setSelectedText("");
                    window.getSelection()?.removeAllRanges();
                  }}
                >
                  <X className="h-4 w-4" />
                  <span className="sr-only">Clear selection</span>
                </Button>
              </div>
            ) : (
              <p className="mt-2 text-xs text-slate-400">
                No text selected — select a sample value (e.g. a name, date, or title) to begin.
              </p>
            )}
          </CardHeader>
          <CardContent className="max-h-[65vh] space-y-6 overflow-y-auto">
            {LOCATION_ORDER.filter((location) => segmentsByLocation[location]?.length).map(
              (location) => (
                <div key={location} className="space-y-2">
                  <Badge variant="outline" className="bg-slate-50 capitalize">
                    {location}
                  </Badge>
                  <div className="space-y-1">
                    {segmentsByLocation[location].map((segment) => (
                      <p
                        key={segment.index}
                        data-segment-index={segment.index}
                        className="whitespace-pre-wrap rounded-lg border border-transparent px-3 py-1.5 font-mono text-sm leading-relaxed text-slate-700 hover:border-slate-200 hover:bg-slate-50"
                      >
                        {segment.text}
                      </p>
                    ))}
                  </div>
                </div>
              ),
            )}
          </CardContent>
        </Card>

        {/* RIGHT — staged replacements */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-slate-500" />
              Pending replacements
            </CardTitle>
            <CardDescription>
              {staged.length === 0
                ? "Nothing staged yet. Select sample text on the left to add your first conversion."
                : `${staged.length} ${staged.length === 1 ? "replacement" : "replacements"} staged. Apply to generate the processed template.`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {staged.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-500">
                Sample values you convert will appear here with a before → after preview.
              </div>
            ) : (
              staged.map((item) => (
                <div
                  key={item.id}
                  className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <p className="truncate text-sm text-slate-500">
                        <span className="font-medium text-slate-700">From:</span>{" "}
                        {item.sample_text}
                      </p>
                      <p className="truncate text-sm">
                        <span className="font-medium text-slate-700">To:</span> <MonoKey name={item.placeholder_key} />
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant="outline" className="bg-slate-50 capitalize">
                        {item.field_type}
                      </Badge>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0 text-slate-400 hover:text-red-600"
                        onClick={() => removeStaged(item.id)}
                        disabled={isApplying}
                      >
                        <Trash2 className="h-4 w-4" />
                        <span className="sr-only">Remove</span>
                      </Button>
                    </div>
                  </div>
                  {item.field_label && (
                    <p className="mt-2 text-xs text-slate-500">Label: {item.field_label}</p>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Apply bar */}
      <div className="flex flex-col gap-4 border-t pt-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-600">
          Cleaning creates a processed copy of this document. The original is never modified.
        </p>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => navigate(`/templates/${template.id}`)}>
            Cancel
          </Button>
          <Button
            className="gap-2"
            disabled={staged.length === 0 || isApplying}
            onClick={() => setApplyOpen(true)}
          >
            <Eraser className="h-4 w-4" />
            Apply cleaning{staged.length > 0 ? ` (${staged.length})` : ""}
          </Button>
        </div>
      </div>

      {/* Convert dialog */}
      <Dialog open={convertOpen} onOpenChange={setConvertOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Convert selection to placeholder</DialogTitle>
            <DialogDescription>
              Choose the placeholder key and field details. The selected text will become the
              placeholder wherever it appears in the document.
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Selected text
            </p>
            <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-700">
              {selectedText}
            </p>
          </div>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(stageReplacement)} className="space-y-4">
              <FormField
                control={form.control}
                name="placeholder_key"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Placeholder key</FormLabel>
                    <FormControl>
                      <Input placeholder="meeting_title" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="field_label"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Label (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="Meeting Title" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="field_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Field type</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {FIELD_TYPE_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="section"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Section (optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="Details" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <DialogFooter className="pt-2">
                <Button type="button" variant="outline" onClick={() => setConvertOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit">Add to pending</Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Apply-confirm dialog */}
      <Dialog open={applyOpen} onOpenChange={setApplyOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apply cleaning?</DialogTitle>
            <DialogDescription>
              {staged.length} sample {staged.length === 1 ? "value will become" : "values will become"}{" "}
              placeholders in a processed copy of this document. Your original file is preserved.
              {content.has_processed
                ? " The existing processed copy will be replaced."
                : ""}
            </DialogDescription>
          </DialogHeader>
          <ul className="max-h-48 space-y-1.5 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
            {staged.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center gap-2">
                <span className="truncate text-slate-600">{item.sample_text}</span>
                <span className="text-slate-400">→</span>
                <MonoKey name={item.placeholder_key} />
              </li>
            ))}
          </ul>
          <DialogFooter>
            <Button variant="outline" onClick={() => setApplyOpen(false)} disabled={isApplying}>
              Cancel
            </Button>
            <Button onClick={applyCleaning} disabled={isApplying}>
              {isApplying ? "Applying…" : "Confirm and apply"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
