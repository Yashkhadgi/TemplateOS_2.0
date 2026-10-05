import React, { useEffect, useState } from "react";
import { useForm, FormProvider } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2, Save, AlertCircle, CheckCircle, ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Label } from "@/components/ui/label";
import { DynamicField } from "@/components/forms/DynamicField";
import { templatesApi, documentsApi, TemplateField, Document, DocumentFormValues, ApiError } from "@/lib/api";
import { buildFormSchema } from "@/lib/validation";

export function CreateDocumentPage() {
  const navigate = useNavigate();
  const { id: templateIdParam } = useParams<{ id: string }>();
  const templateId = templateIdParam ? parseInt(templateIdParam, 10) : 0;

  const [template, setTemplate] = useState<any>(null);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const token = localStorage.getItem("templateos_access_token") || "";

  useEffect(() => {
    if (!templateId) {
      navigate("/templates");
      return;
    }
    async function fetchData() {
      try {
        const [templateData, fieldsData] = await Promise.all([
          templatesApi.getTemplateDetail(token, templateId),
          templatesApi.getFields(token, templateId),
        ]);
        setTemplate(templateData);
        setFields(fieldsData);
      } catch (err) {
        console.error("Failed to load template:", err);
        setSaveError("Failed to load template. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [templateId, token]);

  const schema = React.useMemo(() => buildFormSchema(fields), [fields]);
  const form = useForm<DocumentFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {},
    mode: "onBlur",
  });

  useEffect(() => {
    if (fields.length > 0) {
      const defaultValues: Record<string, any> = {};
      fields.forEach(f => {
        if (f.field_type === "list" && f.default_value) {
          try {
            defaultValues[f.field_name] = JSON.parse(f.default_value);
          } catch {
            defaultValues[f.field_name] = [];
          }
        } else {
          defaultValues[f.field_name] = f.default_value || "";
        }
      });
      form.reset(defaultValues);
    }
  }, [fields, form]);

  const handleSaveDraft = async (formData: DocumentFormValues) => {
    if (!templateId) return;

    setSaving(true);
    setSaveError(null);

    try {
      // Step 1: Create document
      const doc = await documentsApi.createDocument(token, { template_id: templateId });

      // Step 2: Prepare values (stringify lists)
      const values = fields.map((field) => {
        const value = formData[field.field_name];
        const stringValue = Array.isArray(value) ? JSON.stringify(value) : String(value ?? "");
        return {
          field_name: field.field_name,
          value: stringValue,
        };
      });

      // Step 3: Save values
      await documentsApi.saveValues(token, doc.id, { values });

      setSaveSuccess(true);
      setTimeout(() => {
        navigate(`/documents/${doc.id}/edit`);
      }, 1500);
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 422 && err.detail) {
        // Field-specific validation errors from backend
        const errors: Record<string, string> = {};
        for (const e of err.detail as Array<{ field_name: string; error: string }>) {
          errors[e.field_name] = e.error;
        }
        // Set form errors for inline display
        Object.entries(errors).forEach(([fieldName, message]) => {
          form.setError(fieldName, { message, type: "server" });
        });
      } else {
        setSaveError(err?.message || "Failed to save draft. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="h-8 bg-slate-100 rounded animate-pulse" />
        <div className="h-64 bg-slate-100 rounded animate-pulse" />
      </div>
    );
  }

  if (!template) {
    return (
      <div className="mx-auto max-w-3xl text-center py-12">
        <AlertCircle className="h-12 w-12 text-slate-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-slate-900">Template not found</h2>
        <p className="mt-2 text-slate-500">The template you're looking for doesn't exist or you don't have access to it.</p>
        <Button asChild className="mt-6">
          <a href="/templates">Browse Templates</a>
        </Button>
      </div>
    );
  }

  const groupedFields = fields.reduce((acc, field) => {
    const section = field.section || "General";
    if (!acc[section]) acc[section] = [];
    acc[section].push(field);
    return acc;
  }, {} as Record<string, TemplateField[]>);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="h-8 w-8">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-2xl font-bold text-slate-900">{template.name}</h1>
          <p className="text-sm text-slate-500 mt-1">{template.description || "No description"}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 text-xs font-medium bg-slate-100 text-slate-700 rounded">
            {template.category}
          </span>
          <span className={`px-2 py-1 text-xs font-medium rounded ${
            template.status === "draft" ? "bg-yellow-100 text-yellow-700" :
            template.status === "active" ? "bg-green-100 text-green-700" :
            "bg-blue-100 text-blue-700"
          }`}>
            {template.status.replace("_", " ")}
          </span>
        </div>
      </div>

      {/* Save Success Banner */}
      {saveSuccess && (
        <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <div>
            <p className="font-medium text-green-800">Draft saved successfully!</p>
            <p className="text-sm text-green-700">Redirecting to editor...</p>
          </div>
        </div>
      )}

      {/* Save Error Banner */}
      {saveError && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <p className="text-red-800">{saveError}</p>
        </div>
      )}

      {/* Form */}
      <FormProvider {...form}>
        <form onSubmit={form.handleSubmit(handleSaveDraft)} className="space-y-6">
          <Card>
          <CardHeader>
            <CardTitle>Fill in the Form</CardTitle>
            <CardDescription>
              All fields are driven by the template configuration. Required fields are marked.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {Object.entries(groupedFields).map(([sectionName, sectionFields]) => (
              <div key={sectionName} className="space-y-4">
                {sectionName !== "General" && (
                  <div className="flex items-center gap-2">
                    <Separator />
                    <span className="px-3 py-1 text-sm font-medium text-slate-600 bg-slate-50 rounded">
                      {sectionName}
                    </span>
                    <Separator />
                  </div>
                )}
                <div className="grid gap-4 sm:grid-cols-2">
                  {sectionFields.map((field) => (
                    <div key={field.field_name} className={sectionFields.length === 1 ? "sm:col-span-2" : ""}>
                      <Label htmlFor={field.field_name} className="block text-sm font-medium text-slate-700 mb-1.5">
                        {field.field_label || field.field_name}
                        {field.is_required && <span className="text-red-500 ml-1">*</span>}
                      </Label>
                      <DynamicField field={field} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
          <CardFooter className="flex justify-end gap-3 border-t bg-slate-50">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate(-1)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving || saveSuccess}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : saveSuccess ? (
                <>
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Saved!
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save Draft
                </>
              )}
            </Button>
          </CardFooter>
        </Card>
        </form>
      </FormProvider>
    </div>
  );
}