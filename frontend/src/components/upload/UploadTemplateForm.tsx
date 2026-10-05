import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { Badge } from "@/components/ui/badge";

import { ApiError, templatesApi, type TemplateResponse } from "@/lib/api";
import { UploadZone } from "./UploadZone";

const TOKEN_KEY = "templateos_access_token";

const CATEGORY_OPTIONS = [
  { label: "Notice", value: "notice" },
  { label: "Minutes of Meeting", value: "mom" },
  { label: "Report", value: "report" },
  { label: "Application", value: "application" },
  { label: "Letter", value: "letter" },
  { label: "Certificate", value: "certificate" },
  { label: "Proposal", value: "proposal" },
  { label: "Invoice", value: "invoice" },
  { label: "Custom", value: "custom" },
] as const;

const VISIBILITY_OPTIONS = [
  { label: "Private", value: "private" },
  { label: "Public", value: "public" },
  { label: "Organization", value: "organization" },
  { label: "Department", value: "department" },
  { label: "Group", value: "group" },
] as const;

const uploadTemplateSchema = z.object({
  name: z.string().min(1, "Template name is required").max(100, "Template name must be 100 characters or fewer"),
  description: z.string().max(500, "Description must be 500 characters or fewer").optional(),
  category: z.enum([
    "notice", "mom", "report", "application", "letter", "certificate", "proposal", "invoice", "custom"
  ], { required_error: "Please select a category" }),
  visibility: z.enum([
    "private", "public", "organization", "department", "group"
  ], { required_error: "Please select a visibility" }),
  file: z.instanceof(File, { message: "Please select a .docx file to upload" }),
});

type UploadTemplateValues = z.infer<typeof uploadTemplateSchema>;

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function mapApiError(err: ApiError): string {
  const msg = err.message;
  if (err.status === 400 && msg.includes("DOCX"))
    return "Only .docx files are accepted. Please check your file.";
  if (err.status === 400 && (msg.includes("10 MB") || msg.toLowerCase().includes("size")))
    return "Your file is too large. Maximum size is 10 MB.";
  if (err.status === 401)
    return "Your session has expired. Please log in again.";
  if (err.status === 500)
    return "The server could not save your file. Please try again.";
  return msg;
}

interface UploadTemplateFormProps {
  onUploadStart?: () => void;
  onUploadSuccess?: () => void;
}

export function UploadTemplateForm({ onUploadStart, onUploadSuccess }: UploadTemplateFormProps) {
  const navigate = useNavigate();

  const [error, setError] = useState("");
  const [success, setSuccess] = useState<TemplateResponse | null>(null);

  const form = useForm<UploadTemplateValues>({
    resolver: zodResolver(uploadTemplateSchema),
    mode: "onBlur",
    defaultValues: {
      name: "",
      description: "",
    },
  });

  const { isSubmitting } = form.formState;

  const resetForm = () => {
    form.reset();
    setError("");
    setSuccess(null);
  };

  const onSubmit = async (values: UploadTemplateValues) => {
    setError("");

    const token = localStorage.getItem(TOKEN_KEY) ?? "";
    try {
      onUploadStart?.();
      const result = await templatesApi.upload(token, {
        file: values.file,
        name: values.name.trim(),
        description: values.description?.trim() || undefined,
        category: values.category,
        visibility: values.visibility,
      });
      setSuccess(result);
      onUploadSuccess?.();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? mapApiError(caught) : "Upload failed. Please try again.",
      );
    }
  };

  // ── Success view ──────────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="space-y-4">
        <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">
          ✓ &ldquo;{success.name}&rdquo; uploaded successfully.
        </p>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="capitalize">{success.category}</Badge>
          <span className="text-sm text-slate-500">{formatBytes(success.file_size_bytes ?? 0)}</span>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button
            type="button"
            variant="default"
            onClick={() => navigate(`/templates/${success.id}`)}
          >
            View Template
          </Button>
          <Button type="button" variant="outline" onClick={resetForm}>
            Upload Another
          </Button>
        </div>
      </div>
    );
  }

  // ── Form view ─────────────────────────────────────────────────────────────
  return (
    <Form {...form}>
      <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        {/* Template Name */}
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                Template Name <span className="text-red-500">*</span>
              </FormLabel>
              <FormControl>
                <Input placeholder="e.g. Q3 Project Proposal" maxLength={100} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Description */}
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                Description <span className="font-normal text-slate-500">(optional)</span>
              </FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Briefly describe this template…"
                  className="resize-none"
                  rows={3}
                  maxLength={500}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Category */}
        <FormField
          control={form.control}
          name="category"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                Category <span className="text-red-500">*</span>
              </FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a category" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {CATEGORY_OPTIONS.map((opt) => (
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

        {/* Visibility */}
        <FormField
          control={form.control}
          name="visibility"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                Visibility <span className="text-red-500">*</span>
              </FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select visibility" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {VISIBILITY_OPTIONS.map((opt) => (
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

        {/* File Upload */}
        <FormField
          control={form.control}
          name="file"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                DOCX File <span className="text-red-500">*</span>
              </FormLabel>
              <FormControl>
                <UploadZone
                  file={field.value}
                  onChange={field.onChange}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Error banner */}
        {error && (
          <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>
        )}

        {/* Submit */}
        <Button className="w-full" type="submit" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Uploading…
            </>
          ) : (
            "Upload Template"
          )}
        </Button>
      </form>
    </Form>
  );
}
