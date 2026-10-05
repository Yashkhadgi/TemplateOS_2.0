import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  ListTodo,
  Loader2,
  Plus,
  Save,
  Trash2,
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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

import { useAuth } from "@/context/auth-context";
import { AiSuggestionsPanel } from "@/components/fields/AiSuggestionsPanel";
import {
  ApiError,
  templatesApi,
  type FieldSuggestion,
  type TemplateField,
  type TemplateResponse,
} from "@/lib/api";

const TOKEN_KEY = "templateos_access_token";

const FIELD_TYPE_OPTIONS = [
  { label: "Text", value: "text" },
  { label: "Long text", value: "textarea" },
  { label: "Date", value: "date" },
  { label: "Number", value: "number" },
  { label: "List", value: "list" },
  { label: "Signature", value: "signature" },
] as const;

const FIELD_NAME_PATTERN = /^[a-z][a-z0-9_]*$/;

type FieldTypeValue = (typeof FIELD_TYPE_OPTIONS)[number]["value"];

function isFieldType(value: string): value is FieldTypeValue {
  return FIELD_TYPE_OPTIONS.some((opt) => opt.value === value);
}

// Form value for one field row. `rowId` carries the DB id for existing
// fields (renamed away from `id` because useFieldArray injects its own
// `id` on every item); undefined means "new field" on save.
interface FieldFormValue {
  rowId?: number;
  field_name: string;
  field_label: string;
  field_type: FieldTypeValue;
  is_required: boolean;
  ai_enabled: boolean;
  description: string;
  example_value: string;
  validation_rule: string;
  section: string;
}

const fieldRowSchema = z.object({
  rowId: z.number().optional(),
  field_name: z
    .string()
    .min(1, "Field key is required")
    .max(100, "Field key must be 100 characters or fewer")
    .regex(
      FIELD_NAME_PATTERN,
      "lowercase letters, numbers, underscores; start with a letter",
    ),
  field_label: z.string().max(150, "Label must be 150 characters or fewer"),
  field_type: z.enum(["text", "textarea", "date", "number", "list", "signature"], {
    errorMap: () => ({ message: "Please select a field type" }),
  }),
  is_required: z.boolean(),
  ai_enabled: z.boolean(),
  description: z.string(),
  example_value: z.string().max(255, "Example must be 255 characters or fewer"),
  validation_rule: z
    .string()
    .max(255, "Validation rule must be 255 characters or fewer"),
  section: z.string().max(100, "Section must be 100 characters or fewer"),
});

const fieldSetupSchema = z.object({
  fields: z.array(fieldRowSchema).superRefine((fields, ctx) => {
    const seen = new Set<string>();
    for (const [index, field] of fields.entries()) {
      if (seen.has(field.field_name)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: [index, "field_name"],
          message: `Duplicate field key "${field.field_name}" — keys must be unique`,
        });
      }
      seen.add(field.field_name);
    }
  }),
});

type FieldSetupValues = z.infer<typeof fieldSetupSchema>;

function seedField(field: TemplateField): FieldFormValue {
  return {
    rowId: field.id,
    field_name: field.field_name,
    field_label: field.field_label ?? "",
    field_type: isFieldType(field.field_type) ? field.field_type : "text",
    is_required: field.is_required,
    ai_enabled: field.ai_enabled,
    description: field.description ?? "",
    example_value: field.example_value ?? "",
    validation_rule: field.validation_rule ?? "",
    section: field.section ?? "",
  };
}

function blankField(): FieldFormValue {
  return {
    field_name: "",
    field_label: "",
    field_type: "text",
    is_required: true,
    ai_enabled: false,
    description: "",
    example_value: "",
    validation_rule: "",
    section: "",
  };
}

function MonoKey({ name }: { name: string }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
      {`{{${name || "key"}}}`}
    </code>
  );
}

function mapSaveError(err: ApiError): string {
  if (err.status === 403) return err.message;
  if (err.status === 409) return `Duplicate field key: ${err.message}`;
  if (err.status === 422) return err.message;
  if (err.status === 401) return "Your session has expired. Please log in again.";
  return err.message || "Could not save fields. Please try again.";
}

export function FieldSetupPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const templateId = Number(id);

  const [template, setTemplate] = useState<TemplateResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<{
    message: string;
    status?: number;
  } | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [deleteIndex, setDeleteIndex] = useState<number | null>(null);

  const form = useForm<FieldSetupValues>({
    resolver: zodResolver(fieldSetupSchema),
    mode: "onBlur",
    defaultValues: { fields: [] },
  });

  const { fields, append, remove, move } = useFieldArray({
    control: form.control,
    name: "fields",
  });

  const { isSubmitting } = form.formState;

  // Live field keys (kept current so the AI panel can block duplicate
  // accepts even after in-editor renames). useFieldArray's `fields` alone
  // does not reflect input edits.
  const watchedFields = useWatch({ control: form.control, name: "fields" });
  const existingKeys = (watchedFields ?? [])
    .map((field) => field?.field_name?.trim())
    .filter((name): name is string => Boolean(name));

  // Keys accepted from the AI panel but not saved yet — used only for the
  // visual "AI suggestion" highlight; cleared on successful save.
  const [aiStagedKeys, setAiStagedKeys] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      const token = localStorage.getItem(TOKEN_KEY) ?? "";
      try {
        const [templateData, fieldData] = await Promise.all([
          templatesApi.getTemplateDetail(token, templateId),
          templatesApi.getFields(token, templateId),
        ]);
        if (!active) return;
        setTemplate(templateData);
        form.reset({
          fields: [...fieldData]
            .sort((a, b) => a.display_order - b.display_order)
            .map(seedField),
        });
      } catch (caught) {
        if (!active) return;
        if (caught instanceof ApiError) {
          setLoadError({ message: caught.message, status: caught.status });
        } else {
          setLoadError({ message: "Could not load the field setup page." });
        }
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
  const isLocked = template?.status === "locked";

  const onSubmit = async (values: FieldSetupValues) => {
    if (!template) return;
    setSaveError(null);
    setSaveSuccess(false);
    const token = localStorage.getItem(TOKEN_KEY) ?? "";
    try {
      const saved = await templatesApi.saveFields(token, templateId, {
        fields: values.fields.map((field) => ({
          id: field.rowId,
          field_name: field.field_name.trim(),
          field_label: field.field_label.trim() || undefined,
          field_type: field.field_type,
          is_required: field.is_required,
          description: field.description.trim() || undefined,
          example_value: field.example_value.trim() || undefined,
          validation_rule: field.validation_rule.trim() || undefined,
          section: field.section.trim() || undefined,
          ai_enabled: field.ai_enabled,
        })),
        mark_configured: true,
      });
      // Reseed from the response so ids/rows stay in sync with the server.
      form.reset({ fields: saved.map(seedField) });
      setAiStagedKeys([]);
      // Reflect the configured status immediately (forward-only server-side;
      // active templates stay active).
      if (template.status !== "active" && template.status !== "field_configured") {
        setTemplate({ ...template, status: "field_configured" });
      }
      setSaveSuccess(true);
    } catch (caught) {
      setSaveError(
        caught instanceof ApiError
          ? mapSaveError(caught)
          : "Could not save fields. Please try again.",
      );
    }
  };

  // Accept an AI proposal: stage it as a NEW field row (no rowId — Save all
  // creates it server-side). This is the ONLY effect of accepting; no second
  // persistence path exists.
  const handleAcceptSuggestion = (suggestion: FieldSuggestion) => {
    append({
      field_name: suggestion.field_name,
      field_label: suggestion.field_label ?? "",
      field_type: isFieldType(suggestion.field_type)
        ? suggestion.field_type
        : "text",
      is_required: suggestion.is_required,
      ai_enabled: true,
      description: suggestion.reason ?? "",
      example_value: suggestion.example_value ?? "",
      validation_rule: "",
      section: suggestion.section ?? "",
    });
    setAiStagedKeys((keys) => [...keys, suggestion.field_name]);
    setSaveSuccess(false);
  };

  const confirmDelete = () => {
    if (deleteIndex === null) return;
    const removedKey = fields[deleteIndex]?.field_name;
    remove(deleteIndex);
    if (removedKey) {
      setAiStagedKeys((keys) => keys.filter((key) => key !== removedKey));
    }
    setDeleteIndex(null);
    setSaveSuccess(false);
  };

  // ── Loading view ────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-4xl space-y-8 pb-10">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-6 w-96" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  // ── Error view ──────────────────────────────────────────────────────
  if (loadError || !template) {
    return (
      <div className="max-w-4xl space-y-6 py-20 text-center">
        <h2 className="text-2xl font-semibold">
          {loadError?.status === 404
            ? "Template not found"
            : loadError?.status === 403
              ? "You do not have access to this template"
              : "Something went wrong"}
        </h2>
        <p className="text-sm text-slate-600">
          {loadError?.message ?? "Please try again."}
        </p>
        <div className="flex justify-center gap-3">
          <Button variant="outline" onClick={() => navigate("/templates")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Library
          </Button>
          <Button variant="outline" onClick={() => navigate(0)}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  // ── Non-owner view ──────────────────────────────────────────────────
  if (!isOwner) {
    return (
      <div className="max-w-4xl space-y-6 py-20 text-center">
        <h2 className="text-2xl font-semibold">
          Only the template owner can edit fields
        </h2>
        <p className="text-sm text-slate-600">
          Field setup configures the form spec for this template, so it is
          restricted to the owner.
        </p>
        <div className="flex justify-center">
          <Button
            variant="outline"
            onClick={() => navigate(`/templates/${template.id}`)}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Template
          </Button>
        </div>
      </div>
    );
  }

  const statusBadgeClass =
    template.status === "field_configured"
      ? "border-violet-200 bg-violet-50 text-violet-700"
      : template.status === "active"
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-slate-200 bg-slate-50 text-slate-600";

  // ── Locked view (read-only) ─────────────────────────────────────────
  if (isLocked) {
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
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold">Field Setup</h1>
          <p className="text-sm text-slate-600">
            {template.name} ·{" "}
            <Badge variant="outline" className="capitalize">
              {template.status.replace(/_/g, " ")}
            </Badge>
          </p>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          This template is locked and cannot be edited. Field metadata is
          read-only.
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListTodo className="h-5 w-5" />
              Fields
            </CardTitle>
            <CardDescription>
              {fields.length} field(s), in display order.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ol className="divide-y divide-slate-100">
              {fields.map((field, index) => (
                <li
                  key={field.id}
                  className="flex flex-wrap items-center gap-3 px-4 py-4 sm:px-6"
                >
                  <span className="text-sm font-medium text-slate-400">
                    {index + 1}.
                  </span>
                  <span className="text-sm font-medium text-slate-900">
                    {field.field_label || field.field_name}
                  </span>
                  <MonoKey name={field.field_name} />
                  <Badge variant="outline" className="shrink-0 bg-slate-50 capitalize">
                    {field.field_type}
                  </Badge>
                  {field.is_required && (
                    <Badge
                      variant="outline"
                      className="shrink-0 border-red-200 bg-red-50 text-red-700"
                    >
                      required
                    </Badge>
                  )}
                  {field.ai_enabled && (
                    <Badge
                      variant="outline"
                      className="shrink-0 border-blue-200 bg-blue-50 text-blue-700"
                    >
                      AI
                    </Badge>
                  )}
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Editor ──────────────────────────────────────────────────────────
  return (
    <div className="max-w-6xl space-y-8 pb-10">
      <Button
        variant="ghost"
        onClick={() => navigate(`/templates/${template.id}`)}
        className="-ml-4 text-slate-600"
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Template
      </Button>

      <div className="space-y-2">
        <h1 className="text-3xl font-semibold">Field Setup</h1>
        <p className="text-sm text-slate-600">
          {template.name} ·{" "}
          <Badge variant="outline" className={`capitalize ${statusBadgeClass}`}>
            {template.status.replace(/_/g, " ")}
          </Badge>
        </p>
      </div>

      {saveError && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{saveError}</div>
      )}
      {saveSuccess && !saveError && (
        <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">
          Fields saved. Template configured.
        </div>
      )}

      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Form {...form}>
          <form
            className="space-y-6"
            onSubmit={form.handleSubmit(onSubmit)}
            noValidate
          >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-amber-800">
              Saving replaces the field set — removed rows are deleted.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button
                type="button"
                variant="outline"
                className="gap-2"
                onClick={() => {
                  append(blankField());
                  setSaveSuccess(false);
                }}
              >
                <Plus className="h-4 w-4" />
                Add field
              </Button>
              <Button type="submit" className="gap-2" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4" />
                    Save all
                  </>
                )}
              </Button>
            </div>
          </div>

          {fields.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
                <ListTodo className="h-10 w-10 text-slate-300" />
                <p className="text-sm text-slate-600">
                  No fields yet. Add the fields this template needs — they become
                  the smart form in the next step.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  className="gap-2"
                  onClick={() => append(blankField())}
                >
                  <Plus className="h-4 w-4" />
                  Add first field
                </Button>
              </CardContent>
            </Card>
          ) : (
            <ol className="space-y-4">
              {fields.map((field, index) => {
                // Live key (renames count) — drives the AI-staged highlight.
                const rowKey =
                  watchedFields?.[index]?.field_name ?? field.field_name;
                const isAiStaged = aiStagedKeys.includes(rowKey);
                return (
                <li key={field.id}>
                  <Card
                    className={
                      isAiStaged
                        ? "border-indigo-200 ring-1 ring-indigo-100"
                        : undefined
                    }
                  >
                    <CardHeader className="pb-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <CardTitle className="flex flex-wrap items-center gap-3 text-base">
                          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-600">
                            {index + 1}
                          </span>
                          <span className="text-slate-700">
                            {field.field_label || field.field_name || "New field"}
                          </span>
                          <MonoKey name={field.field_name} />
                          {isAiStaged && (
                            <Badge
                              variant="outline"
                              className="shrink-0 border-indigo-200 bg-indigo-50 text-indigo-700"
                            >
                              AI suggestion
                            </Badge>
                          )}
                        </CardTitle>
                        <div className="flex items-center gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            disabled={index === 0}
                            onClick={() => move(index, index - 1)}
                            aria-label="Move field up"
                          >
                            <ChevronUp className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            disabled={index === fields.length - 1}
                            onClick={() => move(index, index + 1)}
                            aria-label="Move field down"
                          >
                            <ChevronDown className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="text-red-600 hover:text-red-700"
                            onClick={() => setDeleteIndex(index)}
                            aria-label="Delete field"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      <CardDescription>
                        {!field.rowId && "New field — created when you save."}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name={`fields.${index}.field_name`}
                          render={({ field: input }) => (
                            <FormItem>
                              <FormLabel>
                                Field key <span className="text-red-500">*</span>
                              </FormLabel>
                              <FormControl>
                                <Input
                                  placeholder="e.g. meeting_date"
                                  className="font-mono"
                                  maxLength={100}
                                  {...input}
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name={`fields.${index}.field_label`}
                          render={({ field: input }) => (
                            <FormItem>
                              <FormLabel>
                                Label{" "}
                                <span className="font-normal text-slate-500">
                                  (optional)
                                </span>
                              </FormLabel>
                              <FormControl>
                                <Input
                                  placeholder="e.g. Meeting Date"
                                  maxLength={150}
                                  {...input}
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name={`fields.${index}.field_type`}
                          render={({ field: input }) => (
                            <FormItem>
                              <FormLabel>
                                Type <span className="text-red-500">*</span>
                              </FormLabel>
                              <Select
                                onValueChange={input.onChange}
                                value={input.value}
                              >
                                <FormControl>
                                  <SelectTrigger>
                                    <SelectValue placeholder="Select a type" />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {FIELD_TYPE_OPTIONS.map((opt) => (
                                    <SelectItem key={opt.value} value={opt.value}>
                                      {opt.label}
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
                          name={`fields.${index}.section`}
                          render={({ field: input }) => (
                            <FormItem>
                              <FormLabel>
                                Section{" "}
                                <span className="font-normal text-slate-500">
                                  (optional)
                                </span>
                              </FormLabel>
                              <FormControl>
                                <Input
                                  placeholder="e.g. Header, Attendees"
                                  maxLength={100}
                                  {...input}
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name={`fields.${index}.example_value`}
                          render={({ field: input }) => (
                            <FormItem>
                              <FormLabel>
                                Example{" "}
                                <span className="font-normal text-slate-500">
                                  (optional)
                                </span>
                              </FormLabel>
                              <FormControl>
                                <Input
                                  placeholder="e.g. 2026-10-01"
                                  maxLength={255}
                                  {...input}
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name={`fields.${index}.validation_rule`}
                          render={({ field: input }) => (
                            <FormItem>
                              <FormLabel>
                                Validation{" "}
                                <span className="font-normal text-slate-500">
                                  (optional)
                                </span>
                              </FormLabel>
                              <FormControl>
                                <Input
                                  placeholder="e.g. email, min:1"
                                  maxLength={255}
                                  {...input}
                                />
                              </FormControl>
                              <p className="text-xs text-slate-500">
                                Examples: email, min:1, max:200
                              </p>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      <FormField
                        control={form.control}
                        name={`fields.${index}.description`}
                        render={({ field: input }) => (
                          <FormItem>
                            <FormLabel>
                              Help text{" "}
                              <span className="font-normal text-slate-500">
                                (optional)
                              </span>
                            </FormLabel>
                            <FormControl>
                              <Textarea
                                placeholder="Shown under the field in the smart form…"
                                className="resize-none"
                                rows={2}
                                {...input}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <div className="grid grid-cols-1 gap-4 border-t pt-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name={`fields.${index}.is_required`}
                          render={({ field: input }) => (
                            <FormItem>
                              <div className="flex items-center gap-3">
                                <FormControl>
                                  <Switch
                                    checked={input.value}
                                    onCheckedChange={input.onChange}
                                  />
                                </FormControl>
                                <FormLabel className="!mt-0">Required</FormLabel>
                              </div>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name={`fields.${index}.ai_enabled`}
                          render={({ field: input }) => (
                            <FormItem>
                              <div className="flex items-center gap-3">
                                <FormControl>
                                  <Switch
                                    checked={input.value}
                                    onCheckedChange={input.onChange}
                                  />
                                </FormControl>
                                <FormLabel className="!mt-0">AI-enabled</FormLabel>
                              </div>
                              <p className="text-xs text-slate-500">
                                Enable AI for descriptive fields (agenda, summary);
                                disable for facts (date, amount).
                              </p>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>
                    </CardContent>
                  </Card>
                </li>
                );
              })}
            </ol>
          )}

          {fields.length > 0 && (
            <div className="flex justify-end border-t pt-6">
              <Button type="submit" className="gap-2" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4" />
                    Save all
                  </>
                )}
              </Button>
            </div>
          )}
        </form>
        </Form>

        {/* ── V1.3 Phase 4: AI Suggestions panel ─────────────────────────
            Owner-only (this whole view is owner-gated above; the locked
            read-only view returns earlier). Proposals only — accepted rows
            are staged in the editor and persisted by Save all. */}
        <aside id="ai-suggestions" className="lg:sticky lg:top-6">
          <AiSuggestionsPanel
            templateId={templateId}
            existingKeys={existingKeys}
            onAccept={handleAcceptSuggestion}
          />
        </aside>
      </div>

      <Dialog
        open={deleteIndex !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteIndex(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete field?</DialogTitle>
            <DialogDescription>
              {deleteIndex !== null && fields[deleteIndex] && (
                <>
                  &ldquo;
                  {fields[deleteIndex].field_label ||
                    fields[deleteIndex].field_name ||
                    "New field"}
                  &rdquo; will be removed now and deleted from the template when
                  you save.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteIndex(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              <Trash2 className="mr-2 h-4 w-4" />
              Remove field
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
